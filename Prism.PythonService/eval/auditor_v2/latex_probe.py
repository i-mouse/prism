"""Step P - arXiv LaTeX probe (decisions.md 2026-10-29, "Auditor v2 T1 result ...").

Free, facts only, no marks. Stdlib plus eval.auditor_v2.cell_parser. Subcommands:

    select-s-rows   apply the T2 S-row selection rule to dev_eval + dev_match_map
    fetch           download arXiv sources (fixed id list, rate limited) and extract safely
    scan            scan the LaTeX of every fetched paper (tables, macros, pin values)
    report          write the facts-only markdown report

    python -I eval/auditor_v2/latex_probe.py <subcommand>    (run from Prism.PythonService)

Network: only https://arxiv.org/e-print/<id> for ids in FETCH_LIST. Nothing else.
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import hashlib
import io
import json
import re
import sys
import tarfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import NamedTuple, Optional

_PY_ROOT = Path(__file__).resolve().parents[2]  # Prism.PythonService
if str(_PY_ROOT) not in sys.path:
    sys.path.insert(0, str(_PY_ROOT))

from eval.auditor_v2.cell_parser import parse_cell  # noqa: E402

REPO_ROOT = _PY_ROOT.parent
DEFAULT_ROOT = _PY_ROOT / "scratch" / "auditor_v2" / "latex_src"
DEV_EVAL = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
DEV_MATCH_MAP = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
PINS_FILE = REPO_ROOT / "docs" / "evals" / "auditor_rd" / "t1_pins_2026-10-28.json"
REPORT_FILE = REPO_ROOT / "docs" / "evals" / "auditor_rd" / "stepP_latex_probe_2026-10-29.md"

USER_AGENT = "Prism-eval-probe/1.0 (low-volume research)"
MIN_GAP_S = 5.0
RETRY_WAIT_S = 60.0
MAX_DOWNLOAD = 100 * 1024 * 1024
MAX_DECOMPRESSED = 300 * 1024 * 1024
MAX_MEMBERS = 20000

# The only ids that may be fetched (approved list: 12 dev papers + 3 golden arXiv papers).
DEV_PAPERS = {
    "P1": "2610.11519v1",
    "P2": "2610.11132v1",
    "P3": "2610.11135v1",
    "P4": "2610.10871v1",
    "P5": "2610.11291v1",
    "P6": "2610.11312v1",
    "P7": "2610.10590v1",
    "P8": "2610.12124v1",
    "P9": "2610.12375v1",
    "P10": "2610.12176v1",
    "P11": "2610.12114v1",
    "P12": "2610.12168v1",
}
GOLDEN_PAPERS = {
    "reflexion": "2303.11366v4",
    "cot": "2201.11903v6",
    "react": "2210.03629v3",
}
FETCH_LIST = tuple(DEV_PAPERS.values()) + tuple(GOLDEN_PAPERS.values())
_ID_RE = re.compile(r"^\d{4}\.\d{4,5}v\d+$")


def paper_label(pid: str) -> str:
    for k, v in {**DEV_PAPERS, **GOLDEN_PAPERS}.items():
        if v == pid:
            return k
    return pid


def is_dev(pid: str) -> bool:
    return pid in DEV_PAPERS.values()


# ----------------------------------------------------------------- small helpers

def load_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def dump_json(path: Path, obj) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")


def read_text(path: Path) -> str:
    return Path(path).read_bytes().decode("utf-8", errors="replace")


# ----------------------------------------------------------------- LaTeX text utilities

def strip_comments(text: str) -> str:
    """Drop everything from an unescaped % to end of line."""
    out = []
    for line in text.split("\n"):
        i, cut = 0, None
        while i < len(line):
            c = line[i]
            if c == "\\":
                i += 2
                continue
            if c == "%":
                cut = i
                break
            i += 1
        out.append(line if cut is None else line[:cut])
    return "\n".join(out)


_IF_TOKEN = re.compile(r"\\(if[A-Za-z]*|fi|else)(?![A-Za-z])")
_IFFALSE = re.compile(r"\\iffalse(?![A-Za-z])")
_NOT_OPENERS = {"iff", "ifthenelse"}


def strip_iffalse(text: str) -> str:
    """Remove \\iffalse ... \\fi blocks (nesting aware); a \\else branch stays."""
    out, i = [], 0
    while True:
        m = _IFFALSE.search(text, i)
        if not m:
            out.append(text[i:])
            break
        out.append(text[i:m.start()])
        depth, else_end, end = 1, None, None
        for t in _IF_TOKEN.finditer(text, m.end()):
            name = t.group(1)
            if name == "fi":
                depth -= 1
                if depth == 0:
                    end = t
                    break
            elif name == "else":
                if depth == 1 and else_end is None:
                    else_end = t.end()
            elif name not in _NOT_OPENERS:
                depth += 1
        if end is None:  # unterminated: TeX skips to end of file
            break
        if else_end is not None:
            out.append(text[else_end:end.start()])
        i = end.end()
    return "".join(out)


def read_group(text: str, pos: int, open_ch: str = "{", close_ch: str = "}"):
    """text[pos] must be open_ch. Returns (inner, index after the closing char) or None."""
    if pos >= len(text) or text[pos] != open_ch:
        return None
    depth, i = 0, pos
    while i < len(text):
        c = text[i]
        if c == "\\":
            i += 2
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return text[pos + 1:i], i + 1
        i += 1
    return None


def _skip_ws(text: str, i: int) -> int:
    while i < len(text) and text[i] in " \t\r\n":
        i += 1
    return i


def _read_args(text: str, pos: int, nargs: int):
    """Read nargs {..} groups after pos; an optional [..] before each is skipped."""
    args, i = [], pos
    for _ in range(nargs):
        i = _skip_ws(text, i)
        if i < len(text) and text[i] == "[":
            g = read_group(text, i, "[", "]")
            if g is None:
                return None
            i = _skip_ws(text, g[1])
        g = read_group(text, i)
        if g is None:
            return None
        args.append(g[0])
        i = g[1]
    return args, i


def replace_command(text: str, name: str, nargs: int, keep: Optional[int]) -> str:
    """Replace \\name(*)[opt]{a1}..{an} by argument `keep` (None = drop)."""
    pat = re.compile(r"\\" + re.escape(name) + r"\*?(?![A-Za-z])")
    for _ in range(6):
        out, i, changed = [], 0, False
        while True:
            m = pat.search(text, i)
            if not m:
                out.append(text[i:])
                break
            parsed = _read_args(text, m.end(), nargs)
            if parsed is None:
                out.append(text[i:m.end()])
                i = m.end()
                continue
            args, end = parsed
            out.append(text[i:m.start()])
            out.append(args[keep] if keep is not None else "")
            i, changed = end, True
        text = "".join(out)
        if not changed:
            break
    return text


# ----------------------------------------------------------------- \input resolution

_INPUT_RE = re.compile(r"\\(?:input|include)(?![A-Za-z])\s*(?:\{([^{}]*)\}|([^\s{}\\%]+))")
_MAX_INPUT_DEPTH = 20


def _find_tex(base: Path, name: str) -> Optional[Path]:
    name = name.strip()
    if not name:
        return None
    cands = [name] if name.lower().endswith(".tex") else [name + ".tex", name]
    base_r = Path(base).resolve()
    for c in cands:
        p = (base_r / c).resolve()
        try:
            p.relative_to(base_r)
        except ValueError:
            continue
        if p.is_file():
            return p
    return None


def load_resolved(path: Path, base: Path, stats: Optional[dict] = None, chain: tuple = ()) -> str:
    """File text with comments and \\iffalse blocks stripped, \\input/\\include inlined in order."""
    stats = stats if stats is not None else {"resolved": [], "unresolved": []}
    path = Path(path).resolve()
    text = strip_iffalse(strip_comments(read_text(path)))

    def repl(m):
        name = m.group(1) if m.group(1) is not None else m.group(2)
        if "#" in name:  # macro parameter inside a definition, not a file
            return m.group(0)
        target = _find_tex(base, name)
        if target is None or target in chain or len(chain) >= _MAX_INPUT_DEPTH:
            stats["unresolved"].append(name.strip())
            return ""
        stats["resolved"].append(name.strip())
        return "\n" + load_resolved(target, base, stats, chain + (path,)) + "\n"

    return _INPUT_RE.sub(repl, text)


_DOC_BEGIN = re.compile(r"\\begin\s*\{document\}")


def find_mains(src_dir: Path) -> list:
    src_dir = Path(src_dir)
    mains = []
    for p in sorted(src_dir.rglob("*.tex")):
        if p.is_file() and _DOC_BEGIN.search(strip_comments(read_text(p))):
            mains.append(p.relative_to(src_dir).as_posix())
    return mains


# ----------------------------------------------------------------- environments and tables

TABLE_ENV_NAMES = {
    "table", "table*", "longtable", "longtable*", "sidewaystable", "sidewaystable*",
    "wraptable", "wraptable*",
}
_BEGIN_END = re.compile(r"\\(begin|end)\s*\{([A-Za-z*]+)\}")


class Env(NamedTuple):
    name: str
    start: int
    end: int
    body_start: int
    body_end: int


def env_ranges(text: str) -> list:
    stack, out = [], []
    for m in _BEGIN_END.finditer(text):
        kind, name = m.group(1), m.group(2)
        if kind == "begin":
            stack.append((name, m.start(), m.end()))
            continue
        for k in range(len(stack) - 1, -1, -1):
            if stack[k][0] == name:
                n, s, bs = stack[k]
                del stack[k:]
                out.append(Env(n, s, m.end(), bs, m.start()))
                break
    return out


def _strip_leading_args(body: str, env: str) -> str:
    """Drop [placement] and, for wraptable, its two argument groups."""
    i = _skip_ws(body, 0)
    if i < len(body) and body[i] == "[":
        g = read_group(body, i, "[", "]")
        if g:
            i = g[1]
    if env.startswith("wraptable"):
        for _ in range(2):
            i = _skip_ws(body, i)
            g = read_group(body, i)
            if g:
                i = g[1]
    return body[i:]


def _main_caption(body: str) -> Optional[str]:
    """First \\caption{..} of a table environment, ignoring captions inside subtables."""
    masked = body
    for e in env_ranges(body):
        if e.name in ("subtable", "subfigure"):
            masked = masked[:e.start] + " " * (e.end - e.start) + masked[e.end:]
    for m in re.finditer(r"\\caption(?![A-Za-z])", masked):
        if masked[m.end():m.end() + 1] == "*":
            continue
        parsed = _read_args(masked, m.end(), 1)
        if parsed:
            return parsed[0][0]
    return None


def _count_subtables(body: str) -> int:
    n = sum(1 for e in env_ranges(body) if e.name == "subtable")
    return n + len(re.findall(r"\\(?:subfloat|subtable)(?![A-Za-z])", body))


_TABULAR_ARGS = {
    "tabular": 1, "tabular*": 2, "tabularx": 2, "tabulary": 2, "tabu": 1,
    "longtable": 1, "longtable*": 1, "longtabu": 1, "NiceTabular": 1, "NiceTabular*": 1, "array": 1,
}
_TABULAR_BEGIN = re.compile(
    r"\\begin\s*\{(" + "|".join(re.escape(k) for k in sorted(_TABULAR_ARGS, key=len, reverse=True)) + r")\}"
)

KNOWN_MACROS = frozenset("""
begin end hline toprule midrule bottomrule cline cmidrule specialrule addlinespace endhead endfirsthead
endfoot endlastfoot noalign multirow multicolumn multirowcell makecell thead shortstack tabularnewline
textbf textit textsc texttt textrm textsf textsl textnormal emph underline bf it rm sc tt em sl sf
bfseries itshape mdseries scshape ttfamily rmfamily sffamily upshape
scriptsize footnotesize small tiny normalsize large Large LARGE huge Huge
centering raggedright raggedleft noindent par newline linebreak hfill vfill hspace vspace quad qquad
phantom hphantom vphantom rule smallskip medskip bigskip
mathbf mathrm mathit mathcal mathsf mathtt mathbb mathbbm boldsymbol bm text mbox hbox
pm mp times div cdot ldots dots cdots vdots ddots circ bullet
uparrow downarrow rightarrow leftarrow Rightarrow Leftarrow leftrightarrow
approx sim leq geq le ge neq ne infty
alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi rho
sigma tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Upsilon Phi Psi Omega
dagger ddagger ast star S P textdagger textdaggerdbl textasteriskcentered checkmark
textcolor color cellcolor rowcolor columncolor colorbox includegraphics
renewcommand newcommand setlength tabcolsep arraystretch extrarowheight setcounter addtocounter
abovecaptionskip belowcaptionskip captionsetup newcolumntype cmidrulekern heavyrulewidth lightrulewidth
aboverulesep belowrulesep
ref cite citep citet citeauthor citeyear footnote tnote label caption captionof
resizebox scalebox adjustbox linewidth textwidth columnwidth arraybackslash
frac sqrt sum prod left right big Big bigg Bigg
""".split())

_MACRO_DEF_RE = re.compile(
    r"\\(?:(?:re)?newcommand|providecommand|DeclareRobustCommand|DeclareMathOperator)\*?\s*\{?\s*\\([A-Za-z]+)"
    r"|\\(?:g|e|x)?def\s*\\([A-Za-z]+)"
)


def defined_macros(text: str) -> set:
    return {m.group(1) or m.group(2) for m in _MACRO_DEF_RE.finditer(text)}


def clean_text(s: str) -> str:
    """Rough plain-text view of LaTeX (captions, labels): unwrap \\cmd{..}, drop math marks."""
    s = re.sub(r"\\label\{[^{}]*\}", " ", s)
    s = s.replace("~", " ")
    s = re.sub(r"\}\s*\{", "} {", s)
    for _ in range(20):
        t = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", s)
        if t == s:
            break
        s = t
    s = re.sub(r"\\[A-Za-z]+\*?", " ", s)
    s = re.sub(r"\\(.)", r"\1", s)
    s = s.replace("$", "").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", s).strip()


def remove_captions(body: str) -> str:
    body = replace_command(body, "captionof", 2, None)
    body = replace_command(body, "caption", 1, None)
    return replace_command(body, "label", 1, None)


def _used_macros(body: str) -> set:
    return set(re.findall(r"\\([A-Za-z]+)", remove_captions(body)))


def scan_tables(text: str) -> dict:
    """Tables in document order (see module docstring for the fixed rules)."""
    envs = env_ranges(text)
    table_envs = sorted((e for e in envs if e.name in TABLE_ENV_NAMES), key=lambda e: e.start)
    kept, nested = [], 0
    for e in table_envs:
        if kept and e.start < kept[-1].end:
            nested += 1
            continue
        kept.append(e)

    items = []
    for e in kept:
        body = _strip_leading_args(text[e.body_start:e.body_end], e.name)
        items.append({"start": e.start, "kind": "env", "env": e.name, "body": body,
                      "caption_src": _main_caption(body), "body_rule": "environment"})
    for m in re.finditer(r"\\captionof\s*\{table\}", text):
        p = m.start()
        if any(e.start <= p < e.end for e in kept):
            continue
        parsed = _read_args(text, m.end(), 1)
        cap = parsed[0][0] if parsed else None
        enclosing = [e for e in envs if e.start <= p < e.end and e.name != "document"]
        if enclosing:
            e = max(enclosing, key=lambda x: x.start)
            body, rule = text[e.body_start:e.body_end], f"enclosing:{e.name}"
        else:
            body, rule = text[p:p + 3000], "window-after-3000"
        items.append({"start": p, "kind": "captionof", "env": "captionof", "body": body,
                      "caption_src": cap, "body_rule": rule})
    items.sort(key=lambda x: x["start"])

    app = re.search(r"\\appendix(?![A-Za-z])|\\begin\s*\{appendices\}", text)
    app_pos = app.start() if app else None
    defs = defined_macros(text)

    tables, number = [], 0
    for idx, it in enumerate(items, 1):
        body = it["body"]
        cap = it["caption_src"]
        if cap is not None:
            number += 1
        used = _used_macros(body)
        custom = sorted(used - KNOWN_MACROS - {"multirow", "multicolumn"})
        tables.append({
            "index": idx,
            "caption_number": number if cap is not None else None,
            "caption_first80": clean_text(cap)[:80] if cap is not None else None,
            "env": it["env"],
            "body_rule": it["body_rule"],
            "has_multirow": bool(re.search(r"\\multirow(?:cell)?(?![A-Za-z])", body)),
            "has_multicolumn": bool(re.search(r"\\multicolumn(?![A-Za-z])", body)),
            "has_includegraphics": bool(re.search(r"\\includegraphics(?![A-Za-z])", body)),
            "has_tabular": bool(_TABULAR_BEGIN.search(body)),
            "subtables": _count_subtables(body),
            "custom_macros": custom,
            "custom_macros_defined_in_source": [c for c in custom if c in defs],
            "after_appendix": app_pos is not None and it["start"] > app_pos,
            "_body": body,
        })

    doubts = []
    if re.search(r"\\(?:re)?newcommand\*?\s*\{?\\thetable\b|\\def\s*\\thetable\b", text):
        doubts.append("\\thetable redefined: numbering style may differ from caption order")
    if re.search(r"\\(?:set|add)counter\s*\{table\}|\\(?:counterwithin|numberwithin)\*?\s*\{table\}", text):
        doubts.append("table counter changed (setcounter/addtocounter/counterwithin/numberwithin)")
    n_after = sum(1 for t in tables if t["after_appendix"] and t["caption_number"] is not None)
    if app_pos is not None:
        doubts.append(f"\\appendix present; {n_after} captioned table(s) after it, numbering taken as continuous")
    uncaptioned = [t["index"] for t in tables if t["caption_number"] is None]
    if uncaptioned:
        doubts.append(f"{len(uncaptioned)} table instance(s) without \\caption (not numbered): index {uncaptioned}")
    if nested:
        doubts.append(f"{nested} table environment(s) nested in another table (skipped)")
    return {"tables": tables, "doubts": doubts, "appendix": app_pos is not None}


# ----------------------------------------------------------------- cells and pin check

_RULE_DROPS = [
    ("hspace", 1), ("vspace", 1), ("phantom", 1), ("hphantom", 1), ("vphantom", 1),
    ("cellcolor", 1), ("rowcolor", 1), ("columncolor", 1), ("color", 1),
    ("footnote", 1), ("tnote", 1), ("cite", 1), ("citep", 1), ("citet", 1), ("ref", 1),
    ("label", 1), ("rule", 2), ("cmidrule", 1), ("cline", 1), ("specialrule", 3),
]
_RULE_KEEPS = [
    ("multicolumn", 3, 2), ("multirow", 3, 2), ("multirowcell", 2, 1), ("makecell", 1, 0),
    ("textcolor", 2, 1), ("colorbox", 2, 1), ("resizebox", 3, 2), ("scalebox", 2, 1),
    ("adjustbox", 2, 1),
]
_SYMBOLS = [
    (r"\\pm(?![A-Za-z])", "±"), (r"\\textpm(?![A-Za-z])", "±"), (r"\\times(?![A-Za-z])", "×"),
    (r"\\dagger(?![A-Za-z])", "†"), (r"\\ddagger(?![A-Za-z])", "‡"),
    (r"\\textdagger(?![A-Za-z])", "†"), (r"\\textdaggerdbl(?![A-Za-z])", "‡"),
    (r"\\(?:ast|star|textasteriskcentered)(?![A-Za-z])", "*"),
    (r"\\textminus(?![A-Za-z])", "-"), (r"---", "—"), (r"--", "–"),
]
_P_AMP, _P_DOLLAR = "\u0001", "\u0002"
_TOKEN_RE = re.compile(
    r"(?:(?<![A-Za-z0-9.])[+\-−–])?(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?|\.\d+)"
)


def clean_cell(s: str) -> str:
    s = s.replace("\\&", _P_AMP).replace("\\$", _P_DOLLAR).replace("\\%", "%").replace("\\_", "_")
    for name, nargs in _RULE_DROPS:
        s = replace_command(s, name, nargs, None)
    for name, nargs, keep in _RULE_KEEPS:
        s = replace_command(s, name, nargs, keep)
    for pat, rep in _SYMBOLS:
        s = re.sub(pat, rep, s)
    s = re.sub(r"\^\s*\{?\s*[*†‡a-z]+\s*\}?", "", s)
    s = s.replace("~", " ")
    s = re.sub(r"\}\s*\{", "} {", s)
    for _ in range(20):
        t = re.sub(r"\\[A-Za-z]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", s)
        if t == s:
            break
        s = t
    s = re.sub(r"\\[A-Za-z]+\*?", " ", s)
    s = re.sub(r"\\.", " ", s)
    s = s.replace("$", "").replace("{", "").replace("}", "")
    s = s.replace(_P_AMP, "&").replace(_P_DOLLAR, "$")
    return re.sub(r"\s+", " ", s).strip()


def _strip_tabular_wrappers(body: str) -> str:
    out, i = [], 0
    while True:
        m = _TABULAR_BEGIN.search(body, i)
        if not m:
            out.append(body[i:])
            break
        out.append(body[i:m.start()])
        parsed = _read_args(body, m.end(), _TABULAR_ARGS[m.group(1)])
        i = parsed[1] if parsed else m.end()
    s = "".join(out)
    return re.sub(r"\\(?:begin|end)\s*\{[^{}]*\}", " ", s)


_RULES_RE = re.compile(
    r"\\(?:hline|toprule|midrule|bottomrule|endhead|endfirsthead|endfoot|endlastfoot|noalign)(?![A-Za-z])"
    r"|\\addlinespace(?:\[[^\]]*\])?"
)
_ROW_SEP = re.compile(r"\\\\(?:\[[^\]]*\])?|\\tabularnewline(?![A-Za-z])")
_AMP_SPLIT = re.compile(r"(?<!\\)&")


def table_cells(body: str) -> list:
    """Cleaned cell strings of a table body, rows of cells."""
    s = remove_captions(body)
    s = _strip_tabular_wrappers(s)
    s = re.sub(r"\\cmidrule(?:\([^)]*\))?(?:\[[^\]]*\])?\{[^{}]*\}|\\cline\{[^{}]*\}", " ", s)
    s = _RULES_RE.sub(" ", s)
    rows = []
    for raw_row in _ROW_SEP.split(s):
        cells = [clean_cell(c) for c in _AMP_SPLIT.split(raw_row)]
        if any(cells):
            rows.append(cells)
    return rows


def numeric_view(rows: list) -> dict:
    """Decimals, parsed pairs and adjacent token pairs found in the cleaned cells."""
    decimals, pairs, adjacent = set(), set(), set()
    for row in rows:
        for cell in row:
            p = parse_cell(cell)
            if p.kind == "number" and p.value is not None:
                decimals.add(p.value)
                if p.sd is not None:
                    decimals.add(p.sd)
            elif p.kind == "pair":
                pairs.add(p.pair)
            toks = []
            for t in _TOKEN_RE.findall(cell):
                tp = parse_cell(t)
                if tp.kind == "number" and tp.value is not None:
                    toks.append(tp.value)
                    decimals.add(tp.value)
            for a, b in zip(toks, toks[1:]):
                adjacent.add((a, b))
    return {"decimals": decimals, "pairs": pairs, "adjacent": adjacent}


def pin_present(pin_value: str, view: dict) -> str:
    """'yes' / 'no' / 'not_numeric' for one cell pin value (compared by Decimal value)."""
    p = parse_cell(pin_value)
    if p.kind == "number" and p.value is not None:
        return "yes" if p.value in view["decimals"] else "no"
    if p.kind == "pair":
        a, b = p.pair
        return "yes" if (p.pair in view["pairs"] or (a, b) in view["adjacent"]) else "no"
    return "not_numeric"


def check_pins(table: dict, pins: list) -> dict:
    """Values-only pin check for one gate table. Structural pins are not checked."""
    view = numeric_view(table_cells(table["_body"]))
    per_pin, skipped = {}, []
    for pin in pins:
        if pin.get("kind") != "cell":
            skipped.append(pin["id"])
            continue
        per_pin[pin["id"]] = {"value": pin["value"], "result": pin_present(pin["value"], view),
                              "key_uncertain": bool(pin.get("key_uncertain"))}
    numeric = {k: v for k, v in per_pin.items() if v["result"] != "not_numeric"}
    gated = {k: v for k, v in numeric.items() if not v["key_uncertain"]}
    return {
        "pins": per_pin,
        "present": sum(1 for v in numeric.values() if v["result"] == "yes"),
        "total": len(numeric),
        "present_gated": sum(1 for v in gated.values() if v["result"] == "yes"),
        "total_gated": len(gated),
        "missing_ids": sorted(k for k, v in numeric.items() if v["result"] == "no"),
        "not_numeric_ids": sorted(k for k, v in per_pin.items() if v["result"] == "not_numeric"),
        "structural_not_checked": sorted(skipped),
    }


def load_pins(path: Path = PINS_FILE) -> dict:
    """{'gate_tables': {table_id: {...}}, 'pins_by_table': {table_id: [pin,..]}}."""
    data = load_json(path)
    gate = {t["table_id"]: t for t in data["tables"] if t["role"] == "gate"}
    by_table: dict = {}
    for pin in data["pins"]:
        by_table.setdefault(pin["table_id"], []).append(pin)
    return {"gate_tables": gate, "pins_by_table": by_table}


def scan_main(src_dir: Path, main_rel: str, paper_id: str, pins: Optional[dict]) -> dict:
    stats = {"resolved": [], "unresolved": []}
    main_path = Path(src_dir) / main_rel
    text = load_resolved(main_path, Path(src_dir), stats)
    scanned = scan_tables(text)
    gate = []
    for tid, t in (pins or {"gate_tables": {}})["gate_tables"].items():
        if t["paper_id"] != paper_id:
            continue
        found = [x for x in scanned["tables"] if x["caption_number"] == t["caption_number"]]
        entry = {"table_id": tid, "caption_number": t["caption_number"], "found": bool(found)}
        if found:
            x = found[0]
            entry.update({
                "caption_first80": x["caption_first80"],
                "has_multirow": x["has_multirow"],
                "pin_check": check_pins(x, pins["pins_by_table"].get(tid, [])),
            })
        gate.append(entry)
    tables = [{k: v for k, v in t.items() if k != "_body"} for t in scanned["tables"]]
    return {
        "main": main_rel,
        "inputs_resolved": len(stats["resolved"]),
        "inputs_unresolved": stats["unresolved"],
        "tables": tables,
        "doubts": scanned["doubts"],
        "gate_tables": gate,
    }


def scan_paper(paper_dir: Path, paper_id: str, pins: Optional[dict]) -> dict:
    fetch_info = load_json(paper_dir / "fetch.json") if (paper_dir / "fetch.json").exists() else {}
    src_dir = paper_dir / "src"
    result = {"id": paper_id, "label": paper_label(paper_id),
              "source_available": bool(fetch_info.get("source_available")),
              "format": fetch_info.get("format"), "mains": [], "main_files": []}
    if not src_dir.is_dir() or not result["source_available"]:
        return result
    mains = find_mains(src_dir)
    result["main_files"] = mains
    result["mains"] = [scan_main(src_dir, m, paper_id, pins) for m in mains]
    return result


# ----------------------------------------------------------------- fetch and safe extraction

class Throttle:
    def __init__(self, gap: float = MIN_GAP_S, clock=time.monotonic, sleep=time.sleep):
        self.gap, self.clock, self.sleep, self._last = gap, clock, sleep, None

    def wait(self) -> None:
        if self._last is not None:
            d = self.gap - (self.clock() - self._last)
            if d > 0:
                self.sleep(d)
        self._last = self.clock()


class _ArxivRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        u = urllib.parse.urlparse(newurl)
        host = u.hostname or ""
        if u.scheme != "https" or not (host == "arxiv.org" or host.endswith(".arxiv.org")):
            raise urllib.error.HTTPError(
                newurl, code, f"redirect outside arxiv.org refused (host: {host or newurl})", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def default_opener():
    return urllib.request.build_opener(_ArxivRedirect).open


class _TooLarge(Exception):
    pass


def _read_capped(resp, limit: int) -> bytes:
    buf = io.BytesIO()
    while True:
        chunk = resp.read(1 << 16)
        if not chunk:
            break
        buf.write(chunk)
        if buf.tell() > limit:
            raise _TooLarge(f"download over {limit} bytes")
    return buf.getvalue()


def download(url: str, opener, throttle: Throttle, sleep=time.sleep, ua: str = USER_AGENT) -> dict:
    """GET url; at most one retry after RETRY_WAIT_S, only for transient failures."""
    last = "unknown error"
    for attempt in (0, 1):
        if attempt:
            sleep(RETRY_WAIT_S)
        throttle.wait()
        req = urllib.request.Request(url, headers={"User-Agent": ua})
        try:
            with opener(req, timeout=60) as resp:
                data = _read_capped(resp, MAX_DOWNLOAD)
                return {"ok": True, "data": data, "http_status": getattr(resp, "status", 200),
                        "content_type": resp.headers.get("Content-Type"),
                        "final_url": resp.geturl()}
        except _TooLarge as e:
            return {"ok": False, "http_status": None, "error": str(e)}
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}: {e.reason}"
            if e.code == 429 or 500 <= e.code < 600:
                continue
            return {"ok": False, "http_status": e.code, "error": last}
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            last = f"{type(e).__name__}: {e}"
            continue
    return {"ok": False, "http_status": None, "error": last}


def _gunzip_capped(raw: bytes, limit: int = MAX_DECOMPRESSED) -> Optional[bytes]:
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(raw)) as g:
            out = g.read(limit + 1)
    except (OSError, EOFError):
        return None
    return None if len(out) > limit else out


def _is_tar(data: bytes) -> bool:
    if len(data) > 262 and data[257:262] == b"ustar":
        return True
    try:
        return tarfile.is_tarfile(io.BytesIO(data))
    except (tarfile.TarError, OSError):
        return False


def _looks_latex(data: bytes) -> bool:
    head = data[:200000]
    return b"\\documentclass" in head or b"\\begin{document}" in head or b"\\input" in head


def classify(raw: bytes) -> dict:
    """Detect the downloaded payload. Returns {format, source_available, payload}."""
    if raw[:2] == b"\x1f\x8b":
        dec = _gunzip_capped(raw)
        if dec is None:
            return {"format": "gzip-unreadable", "source_available": False, "payload": None}
        if _is_tar(dec):
            return {"format": "tar.gz", "source_available": True, "payload": dec}
        if dec[:4] == b"%PDF":
            return {"format": "pdf-only", "source_available": False, "payload": None}
        if _looks_latex(dec):
            return {"format": "gz-single-tex", "source_available": True, "payload": dec}
        return {"format": "gzip-unknown", "source_available": False, "payload": None}
    if _is_tar(raw):
        return {"format": "tar", "source_available": True, "payload": raw}
    if raw[:4] == b"%PDF":
        return {"format": "pdf-only", "source_available": False, "payload": None}
    if raw.lstrip()[:1] == b"<":
        return {"format": "html", "source_available": False, "payload": None}
    if _looks_latex(raw):
        return {"format": "tex-plain", "source_available": True, "payload": raw}
    return {"format": "unknown", "source_available": False, "payload": None}


def _member_problem(m: tarfile.TarInfo) -> Optional[str]:
    name = m.name
    p = name.replace("\\", "/")
    parts = [x for x in p.split("/") if x not in ("", ".")]
    if p.startswith("/") or re.match(r"^[A-Za-z]:", p):
        return "absolute path"
    if ".." in parts:
        return "path traversal"
    if m.issym() or m.islnk():
        return "link"
    if not (m.isfile() or m.isdir()):
        return "special file"
    return None


def safe_extract(tar_bytes: bytes, dest: Path) -> dict:
    """Extract only plain files/dirs that stay inside dest; everything else is recorded."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    rejected, allowed, total = [], [], 0
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:") as tar:
        members = tar.getmembers()
        if len(members) > MAX_MEMBERS:
            return {"extracted": 0, "rejected": [{"name": "*", "reason": f"over {MAX_MEMBERS} members"}]}
        for m in members:
            why = _member_problem(m)
            if why is None:
                total += m.size
                if total > MAX_DECOMPRESSED:
                    why = "archive over size cap"
            if why:
                rejected.append({"name": m.name, "reason": why})
            else:
                allowed.append(m)
        try:
            tar.extractall(dest, members=allowed, filter="data")
        except TypeError as e:  # python without extraction filters: do not fall back to a weaker mode
            raise RuntimeError("tarfile extraction filters unavailable in this Python") from e
    return {"extracted": sum(1 for m in allowed if m.isfile()), "rejected": rejected}


def process_archive(raw: bytes, paper_dir: Path) -> dict:
    """Classify, then extract into paper_dir/src. Never raises on a no-source payload."""
    info = classify(raw)
    out = {"format": info["format"], "source_available": info["source_available"],
           "extracted_files": 0, "rejected_members": []}
    if not info["source_available"]:
        return out
    src = Path(paper_dir) / "src"
    if info["format"] in ("tar.gz", "tar"):
        try:
            r = safe_extract(info["payload"], src)
        except tarfile.TarError as e:
            out.update(source_available=False, format=info["format"] + "-unreadable", error=str(e))
            return out
        out["extracted_files"], out["rejected_members"] = r["extracted"], r["rejected"]
    else:
        src.mkdir(parents=True, exist_ok=True)
        (src / "main.tex").write_bytes(info["payload"])
        out["extracted_files"] = 1
    return out


def fetch_one(pid: str, root: Path, opener, throttle: Throttle, sleep=time.sleep) -> dict:
    if pid not in FETCH_LIST or not _ID_RE.match(pid):
        raise ValueError(f"{pid!r} is not on the approved fetch list")
    paper_dir = Path(root) / pid
    paper_dir.mkdir(parents=True, exist_ok=True)
    src_file = paper_dir / f"{pid}.src"
    info_file = paper_dir / "fetch.json"
    url = f"https://arxiv.org/e-print/{pid}"
    prev = load_json(info_file) if info_file.exists() else {}
    if src_file.exists():  # never re-download a file already on disk
        raw = src_file.read_bytes()
        rec = {**prev, "id": pid, "url": url, "status": "already_on_disk", "bytes": len(raw),
               "sha256": hashlib.sha256(raw).hexdigest()}
        if "format" not in prev or not (paper_dir / "src").exists():
            rec.update(process_archive(raw, paper_dir))
        dump_json(info_file, rec)
        return rec
    got = download(url, opener, throttle, sleep)
    rec = {"id": pid, "url": url,
           "fetched_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    if not got["ok"]:
        rec.update(status="failed", http_status=got.get("http_status"), error=got.get("error"),
                   source_available=False, format=None, bytes=None, sha256=None)
        dump_json(info_file, rec)
        return rec
    raw = got["data"]
    src_file.write_bytes(raw)
    rec.update(status="downloaded", http_status=got["http_status"], content_type=got["content_type"],
               final_url=got["final_url"], bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    rec.update(process_archive(raw, paper_dir))
    dump_json(info_file, rec)
    return rec


def fetch_all(ids, root: Path, opener=None, sleep=time.sleep, clock=time.monotonic) -> list:
    opener = opener or default_opener()
    throttle = Throttle(MIN_GAP_S, clock, sleep)
    return [fetch_one(pid, root, opener, throttle, sleep) for pid in ids]


# ----------------------------------------------------------------- S-row selection

SCOPE_WORDS = ["all", "every", "each", "consistent*", "across", "always", "outperform*", "best", "both", "any"]
_SCOPE_RE = re.compile(
    r"\b(" + "|".join(re.escape(w[:-1]) + r"\w*" if w.endswith("*") else re.escape(w) for w in SCOPE_WORDS) + r")\b",
    re.I,
)
_TABLE_REF = re.compile(
    r"\b(?:Tables?|Tabs?\.?)\s*((?:[A-Z]\.?)?\d+(?:\s*(?:[-–—,&/]|and|or)\s*(?:[A-Z]\.?)?\d+)*)"
)
_ROW_ID = re.compile(r"^P(\d+)-([A-Za-z]+)(\d+)$")


def row_sort_key(row_id: str):
    m = _ROW_ID.match(row_id)
    return (int(m.group(1)), m.group(2), int(m.group(3))) if m else (10**6, row_id, 0)


def paper_number(row_id: str) -> int:
    m = _ROW_ID.match(row_id)
    return int(m.group(1)) if m else 10**6


def extract_table_refs(text: str) -> list:
    """Table ids cited in text, in order, unique. Numeric ranges 'Tables 3-5' are expanded."""
    out = []
    for m in _TABLE_REF.finditer(text or ""):
        toks = re.findall(r"((?:[A-Z]\.?)?\d+)|([-–—])", m.group(1))
        ids = []
        prev, dash = None, False
        for ident, sep in toks:
            if sep:
                dash = True
                continue
            ident = ident.replace(".", "")
            if dash and prev is not None and prev.isdigit() and ident.isdigit() and 0 < int(ident) - int(prev) <= 10:
                ids.extend(str(n) for n in range(int(prev) + 1, int(ident)))
            ids.append(ident)
            prev, dash = ident, False
        for i in ids:
            if i not in out:
                out.append(i)
    return out


def _iter_rows(paper: dict):
    em = paper.get("expected_matrix") or []
    if isinstance(em, dict):
        for v in em.values():
            if isinstance(v, list):
                yield from v
    else:
        yield from em


def _evidence_text(row: dict) -> str:
    ev = row.get("expected_evidence_sections")
    if isinstance(ev, list):
        ev = "\n".join(str(x) for x in ev)
    return str(ev or "")


def select_s_rows(dev_eval: dict, match_map: dict) -> dict:
    """The T2 S-row rule, applied literally (criteria a-d; see decisions.md 2026-10-28)."""
    rows = []
    for paper in dev_eval.get("papers", []):
        for r in _iter_rows(paper):
            rows.append({"paper_id": paper.get("paper_id"), **r})
    mm = match_map.get("rows", {})

    def claim_id(row_id):
        # the map names a matched run-1 claim by claim_fingerprint (persisted_claim_id is null in dev)
        e = mm.get(row_id) or {}
        return None if e.get("confirmed_no_match") else (e.get("claim_fingerprint") or e.get("persisted_claim_id"))

    by_claim: dict = {}
    for r in rows:
        if r.get("expected_label") != "supported":
            cid = claim_id(r["id"])
            if cid:
                by_claim.setdefault(cid, []).append(r["id"])

    infos = []
    for r in rows:
        if r.get("expected_label") != "supported":
            continue
        cid = claim_id(r["id"])
        a = bool(cid)
        cited = extract_table_refs(str(r.get("scoring_notes") or ""))
        for t in extract_table_refs(_evidence_text(r)):
            if t not in cited:
                cited.append(t)
        b = bool(cited)
        words = sorted({w.lower() for w in _SCOPE_RE.findall(str(r.get("claim_text_verbatim") or ""))})
        c = bool(words)
        shared = by_claim.get(cid, []) if cid else []
        d = not shared
        infos.append({
            "row_id": r["id"], "paper": f"P{paper_number(r['id'])}", "paper_id": r.get("paper_id"),
            "expected_label": r.get("expected_label"), "claim_fingerprint": cid,
            "tables_cited": cited,
            "tables_in_why_this_case": extract_table_refs(str(r.get("why_this_case") or "")),
            "scope_words": words, "shared_with_refusal_rows": shared,
            "a": a, "b": b, "c": c, "d": d,
        })
    infos.sort(key=lambda x: row_sort_key(x["row_id"]))

    full = [x for x in infos if x["a"] and x["b"] and x["c"] and x["d"]]
    selected, seen = [], set()
    for x in full:  # first per paper, in paper order
        if x["paper"] not in seen:
            seen.add(x["paper"])
            selected.append({**x, "via": "first-per-paper"})
    selected = selected[:10]
    chosen = {x["row_id"] for x in selected}
    for x in full:  # fill by row id to 10
        if len(selected) >= 10:
            break
        if x["row_id"] not in chosen:
            selected.append({**x, "via": "fill"})
            chosen.add(x["row_id"])
    relaxed = False
    if len(selected) < 8:  # drop (c), fill by row id to 8
        relaxed = True
        for x in infos:
            if len(selected) >= 8:
                break
            if x["a"] and x["b"] and x["d"] and x["row_id"] not in chosen:
                selected.append({**x, "via": "relaxed-no-scope-word"})
                chosen.add(x["row_id"])

    shared_rows = [x for x in infos if x["a"] and x["b"] and x["c"] and not x["d"]]
    return {
        "counts": {
            "s_rows": len(infos),
            "a": sum(x["a"] for x in infos),
            "a_b": sum(x["a"] and x["b"] for x in infos),
            "a_b_c": sum(x["a"] and x["b"] and x["c"] for x in infos),
            "a_b_c_d": len(full),
            "selected": len(selected),
            "criterion_c_relaxed": relaxed,
        },
        "selected": selected,
        "shared_claim_rows": shared_rows,
    }


# ----------------------------------------------------------------- report

def _cell(v) -> str:
    return str(v).replace("|", "/").replace("\n", " ")


def _md_table(header: list, rows: list) -> str:
    lines = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    lines += ["| " + " | ".join(_cell(c) for c in r) + " |" for r in rows]
    return "\n".join(lines)


def _yn(b) -> str:
    return "y" if b else "n"


def _macro_list(names: list, cap: int = 15) -> str:
    if not names:
        return "-"
    shown = ", ".join("\\" + n for n in names[:cap])
    return shown + (f" (+{len(names) - cap})" if len(names) > cap else "")


def build_report(root: Path, pins: dict, s_rows: Optional[dict]) -> str:
    root = Path(root)
    scans, fetches = {}, {}
    for pid in FETCH_LIST:
        d = root / pid
        scans[pid] = load_json(d / "scan.json") if (d / "scan.json").exists() else None
        fetches[pid] = load_json(d / "fetch.json") if (d / "fetch.json").exists() else None

    L = ["# Step P - arXiv LaTeX probe (facts only)", "",
         "Date: 2026-10-29. INR 0. No LLM, no pipeline or eval run. Source: arxiv.org/e-print for the 15 approved ids.",
         "Pin check compares values only (Decimal equality of cell/token values); labels and structural pins are not checked.",
         "A value match can be coincidental (small integers, repeated values); the check does not tie a value to a row or column.", ""]

    L += ["## Downloads", ""]
    rows = []
    for pid in FETCH_LIST:
        f = fetches[pid] or {}
        rows.append([paper_label(pid), pid, f.get("status", "not fetched"), f.get("http_status", "-"),
                     f.get("bytes", "-"), (f.get("sha256") or "-")[:16], f.get("format", "-"),
                     _yn(f.get("source_available")), len(f.get("rejected_members") or [])])
    L += [_md_table(["paper", "id", "status", "http", "bytes", "sha256 (16)", "format", "source", "rejected members"], rows), ""]

    L += ["## Per paper", ""]
    rows = []
    for pid in FETCH_LIST:
        sc = scans[pid]
        f = fetches[pid] or {}
        if not sc or not sc["mains"]:
            rows.append([paper_label(pid), pid.rsplit("v", 1)[0], "v" + pid.rsplit("v", 1)[1],
                         _yn(sc and sc["source_available"]),
                         f.get("format", "-"), "-", "-", "-", "-", "-", "-", "-"])
            continue
        for m in sc["mains"]:
            t = m["tables"]
            macros = sorted({x for tb in t for x in tb["custom_macros"]})
            rows.append([paper_label(pid), pid.rsplit("v", 1)[0], "v" + pid.rsplit("v", 1)[1], "y", sc["format"],
                         m["main"], m["inputs_resolved"], len(t),
                         sum(x["has_multirow"] for x in t), sum(x["has_multicolumn"] for x in t),
                         sum(x["has_includegraphics"] for x in t), _macro_list(macros)])
    L += [_md_table(["paper", "id", "version", "source", "format", "main file(s)", "\\input count", "tables found",
                     "with multirow", "with multicolumn", "as image (includegraphics)", "custom macros in tabulars"], rows), ""]

    L += ["## Gate tables", ""]
    rows = []
    for tid, t in pins["gate_tables"].items():
        pid = t["paper_id"]
        sc = scans.get(pid)
        mains = sc["mains"] if sc else []
        if not mains:
            rows.append([tid, "n (no source)", "-", "-", "-", "-", "-"])
            continue
        for m in mains:
            g = next((x for x in m["gate_tables"] if x["table_id"] == tid), None)
            label = tid + (f" [{m['main']}]" if len(mains) > 1 else "")
            if not g or not g["found"]:
                rows.append([label, "n", "-", "-", "-", "-", "-"])
                continue
            pc = g["pin_check"]
            rows.append([label, "y", g["caption_first80"], _yn(g["has_multirow"]),
                         f"{pc['present']}/{pc['total']}", f"{pc['present_gated']}/{pc['total_gated']}",
                         ", ".join(pc["missing_ids"]) or "-"])
    L += [_md_table(["gate table", "found", "caption (first 80)", "multirow", "pin values present x/y (all cell pins)",
                     "x/y (excluding key_uncertain)", "missing pin ids"], rows), ""]

    L += ["## T2-R S rows (select-s-rows)", ""]
    if s_rows:
        c = s_rows["counts"]
        L += [f"S rows: {c['s_rows']}; (a): {c['a']}; (a,b): {c['a_b']}; (a,b,c): {c['a_b_c']}; (a,b,c,d): {c['a_b_c_d']}; "
              f"selected: {c['selected']}; criterion (c) relaxed: {_yn(c['criterion_c_relaxed'])}.", ""]
        def found_cell(row):
            pid = DEV_PAPERS.get(row["paper"])
            sc = scans.get(pid)
            if not sc or not sc["mains"]:
                return "n (no source)"
            if len(sc["mains"]) > 1:
                return "multiple main files"
            have = {str(t["caption_number"]) for t in sc["mains"][0]["tables"] if t["caption_number"] is not None}
            parts = [f"{t}:{'y' if t in have else ('n' if t.isdigit() else 'n/a (non-numeric id)')}" for t in row["tables_cited"]]
            return ", ".join(parts)
        rows = [[r["row_id"], r["paper"], ", ".join(r["tables_cited"]), found_cell(r), r["via"],
                 ", ".join(r["scope_words"]), ", ".join(r["tables_in_why_this_case"]) or "-"] for r in s_rows["selected"]]
        L += [_md_table(["row id", "paper", "tables cited", "found in LaTeX (table:y/n)", "selected via",
                         "scope words", "tables named in why_this_case (not used to select)"], rows), ""]
        L += ["Shared-claim rows (pass a, b, c; fail d), reported apart:", ""]
        rows = [[r["row_id"], r["paper"], ", ".join(r["tables_cited"]), found_cell(r),
                 ", ".join(r["shared_with_refusal_rows"])] for r in s_rows["shared_claim_rows"]]
        L += [_md_table(["row id", "paper", "tables cited", "found in LaTeX (table:y/n)", "shares claim with"], rows)
              if rows else "(none)", ""]
    else:
        L += ["(s_rows.json not found)", ""]

    L += ["## Multirow prevalence (papers with exactly one main file)", ""]
    def prevalence(ids):
        n_all = n_mr = 0
        for pid in ids:
            sc = scans[pid]
            if sc and len(sc["mains"]) == 1:
                t = sc["mains"][0]["tables"]
                n_all += len(t)
                n_mr += sum(x["has_multirow"] for x in t)
        return n_mr, n_all
    groups = [("dev", [p for p in FETCH_LIST if is_dev(p)]), ("golden", [p for p in FETCH_LIST if not is_dev(p)]),
              ("total", list(FETCH_LIST))]
    rows = [[name, f"{a}/{b}"] for name, ids in groups for a, b in [prevalence(ids)]]
    L += [_md_table(["set", "tables with multirow / all tables"], rows), ""]

    L += ["## Problems", ""]
    probs = []
    for pid in FETCH_LIST:
        f, sc = fetches[pid] or {}, scans[pid]
        lab = f"{paper_label(pid)} ({pid})"
        if not f:
            probs.append(f"{lab}: not fetched")
        elif f.get("status") == "failed":
            probs.append(f"{lab}: download failed ({f.get('error')})")
        elif not f.get("source_available"):
            probs.append(f"{lab}: no source (format: {f.get('format')})")
        for rj in f.get("rejected_members") or []:
            probs.append(f"{lab}: archive member rejected: {rj['name']} ({rj['reason']})")
        if sc and sc["source_available"] and len(sc["mains"]) != 1:
            probs.append(f"{lab}: {len(sc['mains'])} main file(s): {sc['main_files']}")
        for m in (sc or {}).get("mains", []):
            for u in m["inputs_unresolved"]:
                probs.append(f"{lab}: unresolved \\input/\\include: {u} (in {m['main']})")
            for d in m["doubts"]:
                probs.append(f"{lab}: numbering: {d}")
            for t in m["tables"]:
                if t["has_includegraphics"] and not t["has_tabular"]:
                    probs.append(f"{lab}: table index {t['index']} (caption {t['caption_number']}) has no tabular, includes a graphic")
    L += ([f"- {p}" for p in probs] or ["(none)"]) + [""]
    return "\n".join(L)


# ----------------------------------------------------------------- CLI

def _cmd_select(args) -> int:
    out = select_s_rows(load_json(DEV_EVAL), load_json(DEV_MATCH_MAP))
    dump_json(Path(args.root) / "s_rows.json", out)
    print(json.dumps(out["counts"]))
    for r in out["selected"]:
        print(r["row_id"], r["via"], ",".join(r["tables_cited"]), ",".join(r["scope_words"]))
    print("shared-claim rows:", [r["row_id"] for r in out["shared_claim_rows"]])
    return 0


def _cmd_fetch(args) -> int:
    ids = args.ids or list(FETCH_LIST)
    bad = [i for i in ids if i not in FETCH_LIST]
    if bad:
        print("not on the approved list:", bad)
        return 2
    for rec in fetch_all(ids, Path(args.root)):
        print(rec["id"], rec.get("status"), rec.get("format"), rec.get("error") or "")
    return 0


def _cmd_scan(args) -> int:
    pins = load_pins()
    for pid in FETCH_LIST:
        d = Path(args.root) / pid
        res = scan_paper(d, pid, pins) if d.is_dir() else {"id": pid, "label": paper_label(pid), "source_available": False,
                                                         "format": None, "mains": [], "main_files": []}
        dump_json(d / "scan.json", res)
        print(pid, "mains:", len(res["mains"]), "tables:", [len(m["tables"]) for m in res["mains"]])
    return 0


def _cmd_report(args) -> int:
    s_path = Path(args.root) / "s_rows.json"
    md = build_report(Path(args.root), load_pins(), load_json(s_path) if s_path.exists() else None)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md + "\n", encoding="utf-8")
    print("wrote", out)
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=str(DEFAULT_ROOT))
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("select-s-rows").set_defaults(fn=_cmd_select)
    f = sub.add_parser("fetch")
    f.add_argument("--ids", nargs="*")
    f.set_defaults(fn=_cmd_fetch)
    sub.add_parser("scan").set_defaults(fn=_cmd_scan)
    r = sub.add_parser("report")
    r.add_argument("--out", default=str(REPORT_FILE))
    r.set_defaults(fn=_cmd_report)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
