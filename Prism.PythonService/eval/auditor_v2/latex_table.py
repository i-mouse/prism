"""LaTeX table parser and caption identification for T2-R reference tables.

decisions.md 2026-10-29 ("Auditor v2 T1 result ... new order (T2-R first)"). Free, no LLM,
no network. Stdlib plus the unchanged helpers of eval.auditor_v2.latex_probe, table_keys and
cell_parser. Turns the LaTeX of one table into the common table schema v1 used by T1
(cells with spans; header / row-header / section flags); key paths come from table_keys.

Rules are fixed before the first run (plan approved 2026-10-29):

Identification (normalise_caption / caption_match / identify)
    PDF and LaTeX captions are normalised the same way (macros unwrapped, math $ dropped,
    cite/ref/label dropped, NFKC, casefold, Greek letters to ASCII words, only letters and
    digits kept). A LaTeX table is identified if its normalised caption and the PDF caption
    share the first 40 characters (the whole shorter caption if under 40) and exactly one
    LaTeX table matches. Zero or several matches = unidentified; nothing is guessed.

Parser (parse_table_body)
    Rows split on a top-level \\\\ (brace depth 0), cells on an unescaped & at depth 0.
    \\multicolumn{n} -> col_span n. \\multirow{n} / \\multirowcell{n} -> row_span |n|; a
    negative n anchors the cell |n|-1 rows up. Paper macros (\\newcommand, \\renewcommand,
    \\providecommand, \\DeclareRobustCommand, simple \\def) are expanded with arguments, using
    the last definition before the table. Storage boxes (\\sbox ...), \\noalign{..},
    \\setlength, colour commands are dropped. Unknown control words stay as text and are listed.
    Header rows = rows before the first horizontal rule (\\midrule, \\specialrule, \\hline)
    that comes after the first row; else row 0 only. A body row whose only non-empty cell is
    one \\multicolumn over all columns is a section row. Row-label columns = the leading run of
    columns whose non-empty body cells all parse as text (empty columns are skipped, the first
    column with a number / pair / missing cell ends the run).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from eval.auditor_v2 import latex_probe as lp
from eval.auditor_v2 import table_keys as tk
from eval.auditor_v2.cell_parser import parse_cell

SCHEMA_VERSION = 1
PREFIX_LEN = 40
_MAX_DEPTH = 12

# ----------------------------------------------------------------- symbols and plain text

_GREEK_LOWER = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε", "zeta": "ζ", "eta": "η",
    "theta": "θ", "iota": "ι", "kappa": "κ", "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ",
    "omicron": "ο", "pi": "π", "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ", "phi": "φ",
    "chi": "χ", "psi": "ψ", "omega": "ω",
}
_WORD_OF_CHAR = {ch: name for name, ch in _GREEK_LOWER.items()}
_WORD_OF_CHAR.update({
    "ϵ": "epsilon", "ϑ": "theta", "ϕ": "phi", "ϰ": "kappa", "ϱ": "rho", "ς": "sigma", "ϖ": "pi",
    "\u2206": "delta",  # INCREMENT sign, used for Delta in PDF text
})

_SYMBOLS = {
    "pm": "±", "mp": "∓", "textpm": "±", "times": "×", "div": "÷", "cdot": "·",
    "dagger": "†", "ddagger": "‡", "textdagger": "†", "textdaggerdbl": "‡",
    "ast": "*", "star": "*", "textasteriskcentered": "*",
    "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥", "neq": "≠", "ne": "≠", "approx": "≈", "sim": "∼",
    "infty": "∞", "rightarrow": "→", "to": "→", "leftarrow": "←", "Rightarrow": "⇒",
    "uparrow": "↑", "downarrow": "↓", "checkmark": "✓", "ldots": "…", "dots": "…", "cdots": "…",
    "textellipsis": "…", "circ": "∘", "bullet": "•", "textminus": "−", "ell": "ℓ", "textbar": "|",
    "S": "§", "P": "¶",
}
for _n, _c in _GREEK_LOWER.items():
    _SYMBOLS[_n] = _c
    if _n != "omicron":
        _SYMBOLS[_n.capitalize()] = _c.upper()
_SYMBOLS.update(varepsilon="ε", vartheta="θ", varphi="φ", varrho="ρ", varsigma="σ", varpi="π")

_SPACE_WORDS = frozenset({"quad", "qquad", "hfill", "enspace", "thinspace", "newline", "linebreak"})
_SWITCHES = frozenset("""
tiny scriptsize footnotesize small normalsize large Large LARGE huge Huge bfseries itshape mdseries
scshape ttfamily rmfamily sffamily upshape slshape bf it rm sc tt em sl sf centering raggedright
raggedleft noindent selectfont arraybackslash relax strut bigstrut mathstrut par displaystyle
textstyle scriptstyle limits nolimits begingroup endgroup protect hfil hss vss ignorespaces
""".split())

# (name, nargs) dropped with their arguments; (name, nargs, keep) replaced by argument `keep`
_PT_DROP = [
    ("hspace", 1), ("vspace", 1), ("phantom", 1), ("hphantom", 1), ("vphantom", 1), ("rule", 2),
    ("cellcolor", 1), ("rowcolor", 1), ("columncolor", 1), ("color", 1), ("arrayrulecolor", 1),
    ("footnote", 1), ("tnote", 1), ("label", 1), ("cite", 1), ("citep", 1), ("citet", 1),
    ("citeauthor", 1), ("citeyear", 1), ("nocite", 1), ("ref", 1), ("eqref", 1), ("cref", 1),
    ("Cref", 1), ("autoref", 1), ("pageref", 1), ("fontsize", 2),
]
_PT_KEEP = [
    ("textbf", 1, 0), ("textit", 1, 0), ("textsc", 1, 0), ("texttt", 1, 0), ("textrm", 1, 0),
    ("textsf", 1, 0), ("textsl", 1, 0), ("textnormal", 1, 0), ("emph", 1, 0), ("underline", 1, 0),
    ("mathrm", 1, 0), ("mathbf", 1, 0), ("mathit", 1, 0), ("mathsf", 1, 0), ("mathtt", 1, 0),
    ("mathcal", 1, 0), ("mathbb", 1, 0), ("mathbbm", 1, 0), ("boldsymbol", 1, 0), ("bm", 1, 0),
    ("text", 1, 0), ("mbox", 1, 0), ("hbox", 1, 0), ("textsuperscript", 1, 0),
    ("textsubscript", 1, 0), ("textcircled", 1, 0), ("makecell", 1, 0), ("shortstack", 1, 0),
    ("rotatebox", 2, 1), ("scalebox", 2, 1), ("resizebox", 3, 2), ("textcolor", 2, 1),
    ("colorbox", 2, 1), ("parbox", 2, 1), ("raisebox", 2, 1),
]
_DING = {"51": "✓", "55": "✗"}
_PH = {"&": "\u0001", "%": "\u0002", "_": "\u0003", "$": "\u0004", "#": "\u0005", "{": "\u0006", "}": "\u0007"}
_CW_RE = re.compile(r"\\([A-Za-z@]+)\*?")


def plain_text(s: str, unknown: Optional[set] = None) -> str:
    """Plain-text view of a cell or caption. Unknown control words stay as \\name and are
    added to `unknown`. Sub/superscript operators are flattened (no semantics guessed)."""
    s = re.sub(r"\\begin\s*\{[^{}]*\}(?:\[[^\]]*\])?|\\end\s*\{[^{}]*\}", " ", s)
    s = s.replace("\\\\", " ")
    for ch, ph in _PH.items():
        s = s.replace("\\" + ch, ph)
    for name, n in _PT_DROP:
        s = lp.replace_command(s, name, n, None)
    for name, n, keep in _PT_KEEP:
        s = lp.replace_command(s, name, n, keep)
    s = re.sub(r"\\ding\s*\{(\d+)\}", lambda m: _DING.get(m.group(1), ""), s)
    s = s.replace("\\!", "")
    s = re.sub(r"\\[,;:> ]", " ", s)
    s = s.replace("~", " ")

    def cw(m):
        name = m.group(1)
        if name in _SYMBOLS:
            return _SYMBOLS[name]
        if name in _SPACE_WORDS:
            return " "
        if name in _SWITCHES:
            return ""
        if unknown is not None:
            unknown.add(name)
        return "\\" + name

    s = _CW_RE.sub(cw, s)
    s = s.replace("$", "")
    s = re.sub(r"[\^_]", "", s)
    s = s.replace("{", "").replace("}", "")
    s = s.replace("---", "—").replace("--", "–")
    s = re.sub(r"\\([^A-Za-z@])", r"\1", s)
    for ch, ph in _PH.items():
        s = s.replace(ph, ch)
    return re.sub(r"\s+", " ", s).strip()


# ----------------------------------------------------------------- caption identification

def normalise_caption(plain: str) -> str:
    """Shared PDF / LaTeX normalisation: NFKC, casefold, Greek to ASCII words, letters and digits only."""
    s = unicodedata.normalize("NFKC", plain or "").casefold()
    s = "".join(_WORD_OF_CHAR.get(ch, ch) for ch in s)
    return "".join(ch for ch in s if ch.isalnum())


def caption_match(a: str, b: str) -> bool:
    """Same first PREFIX_LEN characters, or the whole shorter caption if under PREFIX_LEN."""
    p = min(PREFIX_LEN, len(a), len(b))
    return p > 0 and a[:p] == b[:p]


def identify(pdf_norms: list, candidates: list) -> dict:
    """candidates = [(index, normalised caption)]. Unique match only; never a guess."""
    pdf_norms = [n for n in pdf_norms if n]
    if not pdf_norms:
        return {"status": "pdf-none", "index": None, "matches": []}
    if len({n[:PREFIX_LEN] for n in pdf_norms}) > 1:
        return {"status": "pdf-ambiguous", "index": None, "matches": []}
    pdf = max(pdf_norms, key=len)
    matches = [idx for idx, norm in candidates if caption_match(pdf, norm)]
    if len(matches) == 1:
        return {"status": "identified", "index": matches[0], "matches": matches}
    return {"status": "latex-none" if not matches else "latex-ambiguous", "index": None, "matches": matches}


_LINE_STOP = re.compile(r"^\s*(?:Table|Figure|Fig\.)\s*\d")


def find_captions_in_lines(lines: list, number: int) -> list:
    """Caption texts for lines starting `Table <number>` followed by ':' '.' or '|'. Continuation
    lines are joined (a trailing hyphen joins without a space) until PREFIX_LEN characters are
    available, a blank line, another Table/Figure line, or 4 continuation lines."""
    head = re.compile(r"^\s*Table\s+" + str(number) + r"(?!\d)\s*[:.|]\s*(.*)$")
    out = []
    for i, line in enumerate(lines):
        m = head.match(line)
        if not m:
            continue
        cur = m.group(1).strip()
        j = i + 1
        while j < len(lines) and j <= i + 4 and len(normalise_caption(cur)) < PREFIX_LEN:
            nxt = lines[j]
            if not nxt.strip() or _LINE_STOP.match(nxt):
                break
            nxt = nxt.strip()
            cur = (cur[:-1] + nxt) if cur.endswith("-") else (cur + " " + nxt).strip()
            j += 1
        out.append(cur)
    return out


# ----------------------------------------------------------------- macro definitions and expansion

@dataclass
class MacroDef:
    name: str
    nargs: int
    default: Optional[str]
    body: str
    pos: int


_NEWCMD_RE = re.compile(
    r"\\(?:newcommand|renewcommand|providecommand|DeclareRobustCommand)\*?\s*"
    r"(?:\{\s*\\([A-Za-z@]+)\s*\}|\\([A-Za-z@]+))"
)
_DEF_RE = re.compile(r"\\(?:g|e|x)?def\s*\\([A-Za-z@]+)((?:\s*#\d)*)\s*(?=\{)")
_CW_START = re.compile(r"\\([A-Za-z@]+)")


def collect_defs(text: str) -> dict:
    """{name: [MacroDef, ...] sorted by position}."""
    defs: dict = {}
    for m in _NEWCMD_RE.finditer(text):
        name = m.group(1) or m.group(2)
        j = lp._skip_ws(text, m.end())
        nargs, default = 0, None
        if j < len(text) and text[j] == "[":
            g = lp.read_group(text, j, "[", "]")
            if g is None:
                continue
            try:
                nargs = int(g[0].strip())
            except ValueError:
                continue
            j = lp._skip_ws(text, g[1])
            if j < len(text) and text[j] == "[":
                g2 = lp.read_group(text, j, "[", "]")
                if g2 is None:
                    continue
                default, j = g2[0], lp._skip_ws(text, g2[1])
        if j >= len(text) or text[j] != "{":
            continue
        body = lp.read_group(text, j)
        if body is not None:
            defs.setdefault(name, []).append(MacroDef(name, nargs, default, body[0], m.start()))
    for m in _DEF_RE.finditer(text):
        body = lp.read_group(text, m.end())
        if body is not None:
            defs.setdefault(m.group(1), []).append(
                MacroDef(m.group(1), m.group(2).count("#"), None, body[0], m.start()))
    for lst in defs.values():
        lst.sort(key=lambda d: d.pos)
    return defs


def _lookup(defs: dict, name: str, pos: int) -> Optional[MacroDef]:
    best = None
    for d in defs.get(name, ()):
        if d.pos < pos:
            best = d
    return best


def _take_arg(text: str, i: int):
    """One undelimited TeX argument at i: a {group}, a control word / symbol, or one character."""
    j = lp._skip_ws(text, i)
    if j >= len(text):
        return None
    if text[j] == "{":
        g = lp.read_group(text, j)
        return None if g is None else (g[0], g[1])
    if text[j] == "\\":
        m = re.compile(r"\\(?:[A-Za-z@]+|.)", re.S).match(text, j)
        return m.group(0), m.end()
    return text[j], j + 1


_COLOR_CMDS = frozenset({"rowcolor", "cellcolor", "columncolor", "arrayrulecolor"})
_DROP_ARGS = {"noalign": 1, "sbox": 2, "setlength": 2, "addtolength": 2, "setcounter": 2, "addtocounter": 2}


def expand_macros(text: str, defs: dict, pos: int, problems: list, used: Optional[set] = None,
                  depth: int = 0) -> str:
    if depth > _MAX_DEPTH:
        problems.append("macro expansion depth cap reached")
        return text
    out, i, n = [], 0, len(text)
    while i < n:
        j = text.find("\\", i)
        if j == -1:
            out.append(text[i:])
            break
        out.append(text[i:j])
        m = _CW_START.match(text, j)
        if not m:
            out.append(text[j:j + 2])
            i = j + 2
            continue
        name, k = m.group(1), m.end()
        if name == "global":
            i = k
            continue
        if name in _COLOR_CMDS:
            parsed = lp._read_args(text, k, 1)
            if parsed is None:
                out.append(m.group(0))
                i = k
                continue
            k = parsed[1]
            while k < n and text[k] == "[":
                g = lp.read_group(text, k, "[", "]")
                if g is None:
                    break
                k = g[1]
            i = k
            continue
        if name in _DROP_ARGS:
            kk = k
            for _ in range(_DROP_ARGS[name]):
                a = _take_arg(text, kk)
                if a is None:
                    break
                kk = a[1]
            i = kk
            continue
        d = _lookup(defs, name, pos)
        if d is None:
            out.append(m.group(0))
            i = k
            continue
        args, kk = [], k
        ok = True
        for a_idx in range(d.nargs):
            if a_idx == 0 and d.default is not None:
                p = lp._skip_ws(text, kk)
                if p < n and text[p] == "[":
                    g = lp.read_group(text, p, "[", "]")
                    if g is None:
                        ok = False
                        break
                    args.append(g[0])
                    kk = g[1]
                else:
                    args.append(d.default)
                continue
            a = _take_arg(text, kk)
            if a is None:
                ok = False
                break
            args.append(a[0])
            kk = a[1]
        if not ok:
            problems.append(f"macro \\{name}: arguments not readable")
            out.append(m.group(0))
            i = k
            continue
        if d.nargs == 0:
            kk = lp._skip_ws(text, kk) if (kk < n and text[kk] in " \t\r\n") else kk
        if used is not None:
            used.add(name)
        rep = re.sub(r"##|#(\d)", lambda mm: "#" if mm.group(0) == "##"
                     else (args[int(mm.group(1)) - 1] if int(mm.group(1)) <= len(args) else ""), d.body)
        out.append(expand_macros(rep, defs, pos, problems, used, depth + 1))
        i = kk
    return "".join(out)


def resolve_inputs(text: str, base: Optional[Path], problems: list):
    """Inline \\input / \\include (comments and \\iffalse stripped). Returns (text, files inlined)."""
    count = 0

    def repl(m):
        nonlocal count
        name = m.group(1) if m.group(1) is not None else m.group(2)
        if "#" in name:
            return m.group(0)
        target = lp._find_tex(base, name) if base is not None else None
        if target is None:
            problems.append(f"unresolved \\input: {name.strip()}")
            return ""
        count += 1
        return "\n" + lp.load_resolved(target, base) + "\n"

    return lp._INPUT_RE.sub(repl, text), count


# ----------------------------------------------------------------- tabular content

_TAB_NAMES = sorted(lp._TABULAR_ARGS, key=len, reverse=True)
_TAB_TOKEN = re.compile(r"\\(begin|end)\s*\{(" + "|".join(re.escape(k) for k in _TAB_NAMES) + r")\}")
_TAB_MARKERS = re.compile(r"\\(endfirsthead|endhead|endfoot|endlastfoot)(?![A-Za-z@])")


def _match_end(s: str, start: int):
    """Index of the matching \\end for a tabular opened just before `start` (depth 1), or None."""
    depth = 1
    for t in _TAB_TOKEN.finditer(s, start):
        depth += 1 if t.group(1) == "begin" else -1
        if depth == 0:
            return t
    return None


def _flatten_nested(content: str, problems: list) -> str:
    for _ in range(10):
        m = _TAB_TOKEN.search(content)
        while m and m.group(1) == "end":
            m = _TAB_TOKEN.search(content, m.end())
        if not m:
            return content
        parsed = lp._read_args(content, m.end(), lp._TABULAR_ARGS[m.group(2)])
        start = parsed[1] if parsed else m.end()
        end = _match_end(content, start)
        if end is None:
            problems.append("nested tabular without end")
            return content
        inner = content[start:end.start()].replace("\\\\", " ").replace("&", " ")
        content = content[:m.start()] + " " + inner + " " + content[end.end():]
    return content


def apply_longtable_markers(content: str) -> str:
    """Keep the first head and the body; drop repeated heads and feet (\\endhead after an
    \\endfirsthead, \\endfoot, \\endlastfoot segments)."""
    marks = list(_TAB_MARKERS.finditer(content))
    if not marks:
        return content
    has_first = any(m.group(1) == "endfirsthead" for m in marks)
    keep, last = [], 0
    for m in marks:
        seg, kind = content[last:m.start()], m.group(1)
        if kind == "endfirsthead" or (kind == "endhead" and not has_first):
            keep.append(seg)
        last = m.end()
    keep.append(content[last:])
    return "\n".join(keep)


def extract_tabular(s: str, env: str, problems: list) -> Optional[str]:
    """Content of the outermost tabular-family environment of a table body (nested ones flattened)."""
    m = _TAB_TOKEN.search(s)
    while m and m.group(1) == "end":
        m = _TAB_TOKEN.search(s, m.end())
    if m is None:
        if env.lower().startswith("longtable"):
            parsed = lp._read_args(s, 0, 1)
            return apply_longtable_markers(s[parsed[1]:] if parsed else s)
        problems.append("no tabular environment in table body")
        return None
    parsed = lp._read_args(s, m.end(), lp._TABULAR_ARGS[m.group(2)])
    if parsed is None:
        problems.append("tabular column spec not readable")
        return None
    start = parsed[1]
    end = _match_end(s, start)
    if end is None:
        problems.append("tabular without matching end")
        return None
    later = [t for t in _TAB_TOKEN.finditer(s, end.end()) if t.group(1) == "begin"]
    if later:
        problems.append(f"{len(later) + 1} tabular environments in one table body (first used)")
    content = _flatten_nested(s[start:end.start()], problems)
    if m.group(2).startswith("longtable"):
        content = apply_longtable_markers(content)
    return content


# ----------------------------------------------------------------- rows, cells, rules

_LEN_OPT = re.compile(r"\s*\[\s*[-+]?[\d.]*\s*(?:pt|em|ex|mm|cm|in|bp|pc|sp|dd|cc|mu|\\[A-Za-z]+)\s*\]")


def split_rows(content: str) -> list:
    """Split on a top-level \\\\ or \\tabularnewline (brace depth 0); [len] / * after \\\\ dropped."""
    rows, buf, depth, i, n = [], [], 0, 0, len(content)
    while i < n:
        c = content[i]
        if c == "\\":
            nxt = content[i + 1:i + 2]
            if nxt == "\\" and depth == 0:
                rows.append("".join(buf))
                buf = []
                i += 2
                if i < n and content[i] == "*":
                    i += 1
                m = _LEN_OPT.match(content, i)
                if m:
                    i = m.end()
                continue
            if depth == 0 and content.startswith("\\tabularnewline", i) and not content[i + 15:i + 16].isalpha():
                rows.append("".join(buf))
                buf = []
                i += 15
                continue
            buf.append(content[i:i + 2])
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        buf.append(c)
        i += 1
    rows.append("".join(buf))
    return rows


def split_cells(row: str) -> list:
    cells, buf, depth, i, n = [], [], 0, 0, len(row)
    while i < n:
        c = row[i]
        if c == "\\":
            buf.append(row[i:i + 2])
            i += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth = max(0, depth - 1)
        elif c == "&" and depth == 0:
            cells.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(c)
        i += 1
    cells.append("".join(buf))
    return cells


_RULE_RE = re.compile(
    r"\\(toprule|midrule|bottomrule|hline|hdashline|cline|cmidrule|specialrule|hhline|addlinespace|Xhline)"
    r"(?![A-Za-z@])"
)
_HEADER_CLOSERS = frozenset({"midrule", "hline", "specialrule"})


def extract_rules(chunk: str):
    """Remove rule commands (with their arguments) from a row chunk. Returns (text, [rule names])."""
    out, rules, i = [], [], 0
    while True:
        m = _RULE_RE.search(chunk, i)
        if not m:
            out.append(chunk[i:])
            break
        out.append(chunk[i:m.start()])
        name, k = m.group(1), m.end()
        if name in ("midrule", "toprule", "bottomrule", "addlinespace"):
            kk = lp._skip_ws(chunk, k)
            if kk < len(chunk) and chunk[kk] == "[":
                g = lp.read_group(chunk, kk, "[", "]")
                if g:
                    k = g[1]
        elif name in ("cline", "hhline", "Xhline"):
            parsed = lp._read_args(chunk, k, 1)
            if parsed:
                k = parsed[1]
        elif name == "cmidrule":
            kk = k
            for opener, closer in (("[", "]"), ("(", ")"), ("[", "]")):
                kk2 = lp._skip_ws(chunk, kk)
                if kk2 < len(chunk) and chunk[kk2] == opener:
                    g = lp.read_group(chunk, kk2, opener, closer)
                    if g:
                        kk = g[1]
            parsed = lp._read_args(chunk, kk, 1)
            if parsed:
                k = parsed[1]
        elif name == "specialrule":
            parsed = lp._read_args(chunk, k, 3)
            if parsed:
                k = parsed[1]
        rules.append(name)
        i = k
    return " ".join(out), rules


_LEADING_SWITCH = re.compile(
    r"^\s*\\(?:centering|raggedright|raggedleft|bfseries|itshape|small|scriptsize|footnotesize|tiny)(?![A-Za-z@])")
_MULTICOL = re.compile(r"\\multicolumn(?![A-Za-z@])")
_MULTIROW = re.compile(r"\\multirow(cell)?(?![A-Za-z@])")


def _int(s: str):
    try:
        return int(s.strip())
    except ValueError:
        return None


def peel_cell(raw: str, problems: list):
    """Strip \\multicolumn / \\multirow wrappers (any nesting). Returns (inner, cs, rs, n_mc, n_mr)."""
    s, cs, rs, n_mc, n_mr = raw.strip(), 1, 1, 0, 0
    for _ in range(8):
        while True:
            m = _LEADING_SWITCH.match(s)
            if not m:
                break
            s = s[m.end():]
        m = _MULTICOL.match(s)
        if m:
            parsed = lp._read_args(s, m.end(), 3)
            if parsed is None:
                problems.append(f"\\multicolumn arguments not readable: {raw.strip()[:40]}")
                break
            args, end = parsed
            if s[end:].strip():
                problems.append(f"text after \\multicolumn: {raw.strip()[:40]}")
            v = _int(args[0])
            if v is None or v < 1:
                problems.append(f"\\multicolumn span not an integer: {args[0][:20]}")
                v = 1
            cs, s, n_mc = v, args[2].strip(), n_mc + 1
            continue
        m = _MULTIROW.match(s)
        if m:
            nargs = 2 if m.group(1) else 3
            parsed = lp._read_args(s, m.end(), nargs)
            if parsed is None:
                problems.append(f"\\multirow arguments not readable: {raw.strip()[:40]}")
                break
            args, end = parsed
            if s[end:].strip():
                problems.append(f"text after \\multirow: {raw.strip()[:40]}")
            v = _int(args[0])
            if v is None or v == 0:
                problems.append(f"\\multirow span not an integer: {args[0][:20]}")
                v = 1
            rs, s, n_mr = v, args[-1].strip(), n_mr + 1
            continue
        break
    if _MULTICOL.search(s) or _MULTIROW.search(s):
        problems.append(f"span command inside cell text: {s[:40]}")
    return s, cs, rs, n_mc, n_mr


@dataclass
class Cell:
    row: int
    col: int
    row_span: int = 1
    col_span: int = 1
    text: str = ""
    is_column_header: bool = False
    is_row_header: bool = False
    is_section_row: bool = False
    n_multicolumn: int = 0
    n_multirow: int = 0


@dataclass
class ParsedTable:
    cells: list = field(default_factory=list)
    n_rows: int = 0
    n_cols: int = 0
    header_rows: list = field(default_factory=list)
    problems: list = field(default_factory=list)
    unknown_macros: list = field(default_factory=list)
    macros_expanded: list = field(default_factory=list)
    n_multirow: int = 0
    n_multicolumn: int = 0
    env: str = ""


def _apply_multirows(rows: list, problems: list) -> None:
    removed = set()
    moves = []
    for r, cells in enumerate(rows):
        for cell in cells:
            if cell.row_span > 1:
                for k in range(1, cell.row_span):
                    rr = r + k
                    below = rows[rr] if rr < len(rows) else []
                    other = next((c for c in below if c.col == cell.col), None)
                    if other is None:
                        problems.append(f"multirow at row {r} col {cell.col}: no cell below in row {rr}")
                    elif other.text.strip():
                        problems.append(f"multirow at row {r} col {cell.col}: row {rr} cell is not empty")
                    else:
                        if other.col_span != cell.col_span:
                            problems.append(f"multirow at row {r} col {cell.col}: width differs in row {rr}")
                        removed.add(id(other))
            elif cell.row_span < 0:
                ar = r + cell.row_span + 1
                if ar < 0:
                    problems.append(f"negative multirow at row {r} col {cell.col} reaches above the table")
                    cell.row_span = 1
                    continue
                other = next((c for c in rows[ar] if c.col == cell.col), None)
                if other is None:
                    problems.append(f"negative multirow at row {r} col {cell.col}: no cell in row {ar}")
                elif other.text.strip():
                    problems.append(f"negative multirow at row {r} col {cell.col}: row {ar} cell is not empty")
                else:
                    removed.add(id(other))
                    for k in range(ar + 1, r):
                        mid = next((c for c in rows[k] if c.col == cell.col), None)
                        if mid is not None and not mid.text.strip():
                            removed.add(id(mid))
                moves.append((cell, r, ar))
    for cell, r, ar in moves:
        rows[r] = [c for c in rows[r] if c is not cell]
        cell.row, cell.row_span = ar, -cell.row_span
        rows[ar].append(cell)
    for r in range(len(rows)):
        rows[r] = sorted((c for c in rows[r] if id(c) not in removed), key=lambda c: c.col)


def parse_tabular_content(content: str, unknown: set, problems: list) -> ParsedTable:
    pt = ParsedTable()
    rows: list = []
    rules_above: list = []
    pending: list = []
    for chunk in split_rows(content):
        text, rules = extract_rules(chunk)
        pending += rules
        cells = []
        col = 0
        for raw in split_cells(text):
            inner, cs, rs, n_mc, n_mr = peel_cell(raw, problems)
            cells.append(Cell(row=len(rows), col=col, row_span=rs, col_span=cs,
                              text=plain_text(inner, unknown), n_multicolumn=n_mc, n_multirow=n_mr))
            col += cs
        if all(not c.text and c.row_span == 1 and c.n_multirow == 0 for c in cells):
            continue  # spacer / trailing chunk; its rules carry to the next kept row
        rows.append(cells)
        rules_above.append(pending)
        pending = []
    pt.n_multirow = sum(c.n_multirow for cs_ in rows for c in cs_)
    pt.n_multicolumn = sum(c.n_multicolumn for cs_ in rows for c in cs_)
    _apply_multirows(rows, problems)
    n_rows = len(rows)
    n_cols = max((c.col + c.col_span for cells in rows for c in cells), default=0)

    # header rows: before the first horizontal rule that comes after the first row
    header_end = 1
    for r in range(1, n_rows):
        if any(x in _HEADER_CLOSERS for x in rules_above[r]):
            header_end = r
            break
    else:
        header_end = 1 if n_rows else 0
    header_rows = list(range(min(header_end, n_rows)))
    for cells in rows:
        for c in cells:
            if c.row in header_rows:
                c.is_column_header = True
                if c.row + c.row_span > header_end:
                    problems.append(f"header cell at row {c.row} col {c.col} spans past the header rows")

    # section rows
    body_cells = {}
    for cells in rows:
        for c in cells:
            if c.row not in header_rows:
                body_cells.setdefault(c.row, []).append(c)
    section_rows = set()
    for r, cs_ in body_cells.items():
        filled = [c for c in cs_ if c.text]
        if (len(filled) == 1 and filled[0].n_multicolumn > 0 and n_cols >= 2
                and filled[0].col_span == n_cols and filled[0].col == 0 and filled[0].row_span == 1):
            filled[0].is_section_row = True
            section_rows.add(r)

    # row-label columns: leading run of text-only columns (empty columns are skipped)
    data_cells = [c for r, cs_ in body_cells.items() if r not in section_rows for c in cs_ if c.text]
    label_cols = []
    for col in range(n_cols):
        in_col = [c for c in data_cells if c.col == col]
        if not in_col:
            continue
        if all(parse_cell(c.text).kind == "text" for c in in_col):
            label_cols.append(col)
        else:
            break
    for c in data_cells:
        if c.col in label_cols:
            c.is_row_header = True

    pt.cells = [c for cells in rows for c in cells]
    pt.n_rows, pt.n_cols, pt.header_rows = n_rows, n_cols, header_rows
    return pt


def parse_table_body(body: str, env: str = "table", defs: Optional[dict] = None, pos: int = 10 ** 9,
                     base: Optional[Path] = None) -> ParsedTable:
    """Parse one LaTeX table body (the text between \\begin{table} and \\end{table})."""
    problems: list = []
    unknown: set = set()
    used: set = set()
    defs = defs or {}
    s = lp.remove_captions(body)
    s = expand_macros(s, defs, pos, problems, used)
    for _ in range(4):
        s, n = resolve_inputs(s, base, problems)
        if not n:
            break
        s = expand_macros(s, defs, pos, problems, used)
    content = extract_tabular(s, env, problems)
    if content is None:
        pt = ParsedTable(problems=problems, env=env)
        return pt
    pt = parse_tabular_content(content, unknown, problems)
    pt.problems = problems
    pt.unknown_macros = sorted(unknown)
    pt.macros_expanded = sorted(used)
    pt.env = env
    return pt


def caption_to_plain(caption_src: Optional[str], defs: dict, pos: int, unknown: Optional[set] = None) -> Optional[str]:
    if caption_src is None:
        return None
    problems: list = []
    return plain_text(expand_macros(caption_src, defs, pos, problems), unknown)


# ----------------------------------------------------------------- schema v1 and readable grid

def to_schema(pt: ParsedTable, caption_text: str, caption_number: int, table_index: int = 0,
              meta: Optional[dict] = None) -> dict:
    cells = [{
        "row": c.row, "col": c.col, "row_span": c.row_span, "col_span": c.col_span, "text": c.text,
        "is_column_header": c.is_column_header, "is_row_header": c.is_row_header,
        "is_section_row": c.is_section_row,
    } for c in sorted(pt.cells, key=lambda c: (c.row, c.col))]
    table = {
        "table_index": table_index, "page": None, "caption_text": caption_text,
        "caption_number": caption_number, "footnotes": [],
        "n_rows": pt.n_rows, "n_cols": pt.n_cols, "cells": cells,
    }
    out = tk.table_with_keys(table)
    out["schema_version"] = SCHEMA_VERSION
    out["latex_meta"] = {
        "env": pt.env, "header_rows": pt.header_rows, "n_multirow": pt.n_multirow,
        "n_multicolumn": pt.n_multicolumn, "macros_expanded": pt.macros_expanded,
        "unknown_macros": pt.unknown_macros, "problems": pt.problems,
        "footnotes_note": "footnotes are not extracted from LaTeX",
        **(meta or {}),
    }
    return out


def render_grid_md(table: dict) -> str:
    """Readable grid: one line per row; span anchors carry [rs=k] / [cs=k]; covered slots show ^ / <."""
    n_rows, n_cols = table["n_rows"], table["n_cols"]
    grid = [["" for _ in range(n_cols)] for _ in range(n_rows)]
    flags = ["" for _ in range(n_rows)]
    for c in table["cells"]:
        label = c["text"].replace("|", "/")
        if c["row_span"] > 1:
            label += f" [rs={c['row_span']}]"
        if c["col_span"] > 1:
            label += f" [cs={c['col_span']}]"
        for dr in range(max(1, c["row_span"])):
            for dc in range(max(1, c["col_span"])):
                r, cc = c["row"] + dr, c["col"] + dc
                if r < n_rows and cc < n_cols:
                    grid[r][cc] = label if (dr == 0 and dc == 0) else ("^" if dr else "<")
        if c["is_column_header"]:
            flags[c["row"]] = "H"
        elif c["is_section_row"]:
            flags[c["row"]] = "S"
    lines = ["| r | f | " + " | ".join(f"c{j}" for j in range(n_cols)) + " |",
             "|" + "---|" * (n_cols + 2)]
    for r in range(n_rows):
        lines.append(f"| {r} | {flags[r] or 'R'} | " + " | ".join(grid[r]) + " |")
    return "\n".join(lines)


# ----------------------------------------------------------------- one paper's tables

class PaperTables:
    """The captioned and uncaptioned tables of one paper's single main LaTeX file."""

    def __init__(self, src_dir: Path):
        self.src_dir = Path(src_dir)
        self.problems: list = []
        self.tables: list = []
        self.defs: dict = {}
        self.text = ""
        mains = lp.find_mains(self.src_dir) if self.src_dir.is_dir() else []
        if len(mains) != 1:
            self.problems.append(f"{len(mains)} main file(s): {mains}")
            return
        self.text = lp.load_resolved(self.src_dir / mains[0], self.src_dir)
        self.defs = collect_defs(self.text)
        cursor = 0
        for t in lp.scan_tables(self.text)["tables"]:
            body = t["_body"]
            pos = self.text.find(body, cursor)
            if pos < 0:
                pos = max(0, self.text.find(body))
            cursor = pos + 1
            cap_src = lp._main_caption(body)
            cap_plain = caption_to_plain(cap_src, self.defs, pos)
            self.tables.append({
                "index": t["index"], "pos": pos, "env": t["env"], "body": body,
                "caption_plain": cap_plain,
                "caption_norm": normalise_caption(cap_plain) if cap_plain is not None else None,
            })

    def candidates(self) -> list:
        return [(t["index"], t["caption_norm"]) for t in self.tables if t["caption_plain"] is not None]

    def get(self, index: int) -> dict:
        return next(t for t in self.tables if t["index"] == index)

    def parse(self, index: int) -> ParsedTable:
        t = self.get(index)
        return parse_table_body(t["body"], t["env"], self.defs, t["pos"], self.src_dir)
