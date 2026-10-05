"""CLI + library: fails if eval-paper text, names or numbers leak into runtime
prompts/code.

Offline and secretless: no LLM calls, no DB, no network, no settings import.
Paper texts are never read here - only the committed hash index
(eval/leakcheck/index.json, built locally by scripts/build_leak_index.py from
the four PDFs after a sha256 check). Eval rows are read from the committed
docs/evals/*.json at run time.

Checks over every runtime file (RUNTIME_GLOBS):
  FAIL  8-gram   any word 8-gram shared with a paper (index) or with any eval
                 row field (claim_text_verbatim, claim_summary, scoring_notes,
                 why_this_case; golden + held-out) or golden_eval.json Q/A
  FAIL  name     an eval-paper name (index) or a name found in an eval row
  FAIL  number   a number from an eval row (decimals, percentages, ints >= 3
                 digits); in prompt files also a paper-text decimal with >= 2
                 integer digits. Section ids ("Section 4.2") are exempt.
  WARN  5-gram   any word 5-gram shared with an eval row field (printed for the
                 PR author to disposition; does not fail)

Held-out sources are never echoed: their hits print file:line + count only,
and any golden-source match text that also occurs in a held-out source is
redacted too.

Allowlist: eval/leakcheck/allowlist.json, file-scoped entries only.

  uv run python -m eval.check_prompt_leak            # exit 0 clean, 1 leak, 2 config error
"""
import argparse
import base64
import hashlib
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

NORMALIZER_VERSION = 1
NGRAM_N = 8
WARN_N = 5
HASH_BYTES = 6
MAX_NAME_TOKENS = 4

SERVICE_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = SERVICE_DIR.parent
LEAKCHECK_DIR = SERVICE_DIR / "eval" / "leakcheck"
INDEX_PATH = LEAKCHECK_DIR / "index.json"
ALLOWLIST_PATH = LEAKCHECK_DIR / "allowlist.json"
GOLDEN_ROWS_PATH = REPO_DIR / "docs" / "evals" / "matrix_eval.json"
HELDOUT_ROWS_PATH = REPO_DIR / "docs" / "evals" / "heldout_eval.json"
GOLDEN_QA_PATH = REPO_DIR / "docs" / "evals" / "golden_eval.json"
ROW_FIELDS = ("claim_text_verbatim", "claim_summary", "scoring_notes", "why_this_case")

# Everything the service loads at run time. eval/, tests/, scratch/, scripts/
# and docs/ are deliberately out of scope.
RUNTIME_GLOBS = (
    "prompts/**/*",
    "extraction/**/*.py",
    "paper_chat/**/*.py",
    "mocks/*.json",
    "*.py",
)
PROMPT_SUFFIXES = {".md", ".json", ".txt"}

# Tokens the name heuristic would pick up that are not paper-specific names.
NAME_STOP = {
    "llm", "llms", "ai", "nlp", "rl", "il", "api", "apis", "pdf", "url", "urls", "json", "sota",
    "qa", "ml", "nn", "gpu", "gpus", "tpu", "cpu", "id", "ids", "us", "usa", "uk", "eg", "ie",
    "etc", "fig", "figs", "arxiv", "neurips", "iclr", "icml", "acl", "emnlp", "naacl", "aaai",
    "ijcai", "cvpr", "eccv", "iccv", "tacl", "jmlr", "ieee", "acm", "corr", "abs", "pp", "vol",
    "github", "http", "https", "www", "com", "org", "html", "openai", "google", "deepmind",
    "anthropic", "microsoft", "meta", "lm", "lms", "rlhf", "sft", "ood", "vs", "et", "al",
    "gpt",  # model family word; specific versions (GPT-3, GPT-4) stay in the index
}

_NAME_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])[A-Za-z][A-Za-z0-9]*(?:[-@.][A-Za-z0-9]+)*")
# Thousands separators kept ("7,405"); a number followed by ".digit" is part of
# a version string ("4.2.1") and is not matched.
_NUM_RE = re.compile(r"(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?(?![\w]|\.\d)")
_PAPER_DECIMAL_RE = re.compile(r"(?<![\w.])\d{2,3}\.\d(?![\w.])")
_SECTION_ID_RE = re.compile(r"(?i)\b(section|appendix|table|figure)\s+[A-Z]?\d+(\.\d+)*")
_QUOTED_SECTION_TITLE_RE = re.compile(r"'\d+(\.\d+)+ (?=[A-Z])")


# ---------------------------------------------------------------- normaliser
def normalize_tokens(text: str) -> list[str]:
    """NFKC, PDF line-break de-hyphenation, lowercase, punctuation -> space."""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"-\s*\n\s*", "", text)
    text = text.lower()
    text = re.sub(r"[^\w\s]|_", " ", text)
    return text.split()


def hash_key(tokens) -> bytes:
    return hashlib.sha256(" ".join(tokens).encode("utf-8")).digest()[:HASH_BYTES]


def ngrams(tokens: list[str], n: int) -> list[tuple[str, ...]]:
    return [tuple(tokens[i:i + n]) for i in range(len(tokens) - n + 1)]


def pack_hashes(keys) -> str:
    return base64.b64encode(b"".join(sorted(set(keys)))).decode("ascii")


def unpack_hashes(blob: str) -> set[bytes]:
    raw = base64.b64decode(blob)
    return {raw[i:i + HASH_BYTES] for i in range(0, len(raw), HASH_BYTES)}


# ------------------------------------------------------- names and numbers
def _name_like(core: str, allow_caps: bool) -> bool:
    core = core.strip("-.@")
    if "@" in core:
        return False  # "pass@1" normalises to "pass 1", which ordinary code text contains
    if len(re.sub(r"[^A-Za-z0-9]", "", core)) < 3:
        return False
    has_d = any(c.isdigit() for c in core)
    has_a = any(c.isalpha() for c in core)
    if has_d and not has_a:
        return False
    if re.fullmatch(r"[A-Za-z](\.[A-Za-z0-9]+)+", core):  # abbreviations, section ids
        return False
    if core.isalpha() and core.isupper():  # all-caps words: only from eval rows
        return allow_caps
    parts = re.split(r"[-@.]", core)
    if len(parts) > 1 and all(p.isalpha() and (p[1:].islower() or (p.isupper() and len(p) <= 3)) for p in parts):
        return False  # title-case compounds ("Oil-Based", "IM-style")
    return any(c.isupper() for c in core[1:]) or (has_d and has_a)


def name_candidates(text: str, allow_caps: bool = False) -> dict[str, int]:
    """Paper/model/dataset-like tokens with their frequency."""
    out: dict[str, int] = {}
    for m in _NAME_TOKEN_RE.finditer(unicodedata.normalize("NFKC", text)):
        t = m.group(0).rstrip(".")
        if t.lower() in NAME_STOP or not _name_like(t, allow_caps):
            continue
        out[t] = out.get(t, 0) + 1
    return out


def row_numbers(text: str) -> set[str]:
    """Numbers worth protecting from an eval row: decimals, percentages, ints >= 3 digits (not years)."""
    out = set()
    for m in _NUM_RE.finditer(_strip_section_ids(unicodedata.normalize("NFKC", text))):
        t = m.group(0)
        if re.fullmatch(r"\d\.0+", t):
            continue  # 0.0, 1.0: not distinctive
        if "." in t or t.endswith("%"):
            out.add(t)
        elif len(t) >= 3 and not re.fullmatch(r"(19|20)\d\d|0+", t):
            out.add(t)
    return out


def paper_decimals(text: str) -> set[str]:
    return set(_PAPER_DECIMAL_RE.findall(unicodedata.normalize("NFKC", text)))


def _strip_section_ids(line: str) -> str:
    return _QUOTED_SECTION_TITLE_RE.sub("'", _SECTION_ID_RE.sub(" ", line))


# ----------------------------------------------------------------- sources
@dataclass
class Source:
    """One thing that must not leak. heldout=True -> never echo its text."""
    sid: str
    heldout: bool
    ngrams8: set = field(default_factory=set)   # hash keys (bytes) or tuples
    ngrams5: set = field(default_factory=set)
    names: set = field(default_factory=set)     # hash keys of normalised phrases
    numbers: set = field(default_factory=set)   # literal strings (rows) or hash keys (papers)
    hashed: bool = True                          # paper sources are hashed; rows are literal


def load_index(path: Path = INDEX_PATH) -> dict:
    index = json.loads(path.read_text(encoding="utf-8"))
    hdr = index.get("header", {})
    expected = {"normalizer_version": NORMALIZER_VERSION, "ngram_n": NGRAM_N, "hash_bytes": HASH_BYTES}
    for k, v in expected.items():
        if hdr.get(k) != v:
            raise IndexMismatch(f"{path}: header {k}={hdr.get(k)!r}, checker expects {v!r}. "
                                "Rebuild with: uv run python scripts/build_leak_index.py")
    return index


class IndexMismatch(Exception):
    pass


def paper_sources(index: dict) -> list[Source]:
    out = []
    for sid, s in index["sources"].items():
        out.append(Source(sid=f"paper:{sid}", heldout=s["heldout"],
                          ngrams8=unpack_hashes(s["ngrams8"]), names=unpack_hashes(s["names"]),
                          numbers=unpack_hashes(s["decimals"])))
    return out


def _row_source(sid: str, claim_text: str, notes_text: str, heldout: bool) -> Source:
    """claim_text = the claim fields; notes_text = scoring notes / rationale.
    All-caps tokens count as names only in the claim fields - notes use
    all-caps for emphasis ("FAIL", "NEVER"), not for names."""
    text = f"{claim_text} \n {notes_text}"
    toks = normalize_tokens(text)
    names = {hash_key(normalize_tokens(n)) for n in name_candidates(claim_text, allow_caps=True)}
    names |= {hash_key(normalize_tokens(n)) for n in name_candidates(notes_text, allow_caps=False)}
    return Source(sid=sid, heldout=heldout, hashed=False,
                  ngrams8=set(ngrams(toks, NGRAM_N)), ngrams5=set(ngrams(toks, WARN_N)),
                  names=names, numbers=row_numbers(text))


def row_sources(golden_path: Path = GOLDEN_ROWS_PATH, heldout_path: Path = HELDOUT_ROWS_PATH,
                qa_path: Path = GOLDEN_QA_PATH) -> list[Source]:
    out = []
    for path, heldout in ((golden_path, False), (heldout_path, True)):
        data = json.loads(path.read_text(encoding="utf-8"))
        for i, paper in enumerate(data["papers"]):
            for j, row in enumerate(paper["expected_matrix"]):
                claim = " \n ".join(str(row.get(f, "")) for f in ROW_FIELDS[:2])
                notes = " \n ".join(str(row.get(f, "")) for f in ROW_FIELDS[2:])
                sid = f"heldout-row:{i}.{j}" if heldout else f"row:{row['id']}"
                out.append(_row_source(sid, claim, notes, heldout))
    qa = json.loads(qa_path.read_text(encoding="utf-8"))
    for q in qa["questions"]:
        out.append(_row_source(f"golden_eval:{q['id']}", q["question"], str(q.get("expected_answer", "")), False))
    return out


# ------------------------------------------------------------------- check
@dataclass
class Hit:
    kind: str          # ngram8 | name | number | ngram5 (warn)
    file: str
    line: int
    source: str
    heldout: bool
    detail: str = ""   # matched text for golden sources; never set for held-out
    key: str = ""      # allowlist key (normalised match or hash hex)
    count: int = 1

    def render(self) -> str:
        level = "WARN" if self.kind == "ngram5" else "LEAK"
        where = f"{self.file}:{self.line}"
        if self.heldout:
            return f"{level} {self.kind:6s} {where}  held-out source  count={self.count}"
        return f"{level} {self.kind:6s} {where}  {self.source}  count={self.count}  {self.detail}"


def runtime_files(root: Path = SERVICE_DIR) -> list[Path]:
    files = set()
    for g in RUNTIME_GLOBS:
        for p in root.glob(g):
            if p.is_file() and "__pycache__" not in p.parts:
                files.add(p)
    return sorted(files)


def _file_tokens(path: Path) -> tuple[list[str], list[int], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    toks, line_of = [], []
    for i, line in enumerate(lines, 1):
        if path.suffix == ".json":
            line = line.replace("\\n", " ").replace('\\"', '"')
        for t in normalize_tokens(line):
            toks.append(t)
            line_of.append(i)
    return toks, line_of, lines


def _contains(src: Source, gram: tuple, which: str) -> bool:
    pool = src.ngrams8 if which == "8" else src.ngrams5
    return (hash_key(gram) in pool) if src.hashed else (gram in pool)


def check_files(files: list[Path], root: Path, sources: list[Source]) -> list[Hit]:
    heldout_sources = [s for s in sources if s.heldout]
    hits: list[Hit] = []
    for path in files:
        rel = path.relative_to(root).as_posix()
        is_prompt = path.suffix in PROMPT_SUFFIXES
        toks, line_of, lines = _file_tokens(path)

        # 8-grams (fail) and 5-grams vs rows (warn): runs of consecutive hits
        for which, n in (("8", NGRAM_N), ("5", WARN_N)):
            grams = ngrams(toks, n)
            for src in sources:
                if which == "5" and src.hashed:
                    continue  # 5-gram warnings are against eval rows only
                starts = [i for i, g in enumerate(grams) if _contains(src, g, which)]
                run: list[int] = []
                for i in starts + [None]:
                    if run and (i is None or i != run[-1] + 1):
                        a, b = run[0], run[-1] + n - 1
                        text = " ".join(toks[a:b + 1])
                        if not src.heldout and any(_contains(h, g, which) for h in heldout_sources
                                                   for g in grams[run[0]:run[-1] + 1]):
                            text = "[redacted: also in a held-out source]"
                        hits.append(Hit(kind="ngram8" if which == "8" else "ngram5", file=rel,
                                        line=line_of[a], source=src.sid, heldout=src.heldout,
                                        detail="" if src.heldout else f'"{text}"',
                                        key=" ".join(toks[a:a + n]) if not src.heldout else hash_key(toks[a:a + n]).hex(),
                                        count=len(run)))
                        run = []
                    if i is not None:
                        run.append(i)

        # names and numbers, per line
        for ln, line in enumerate(lines, 1):
            ltoks = normalize_tokens(line)
            phrases = {}
            for k in range(1, MAX_NAME_TOKENS + 1):
                for g in ngrams(ltoks, k):
                    phrases[hash_key(g)] = " ".join(g)
            nums = {m.group(0) for m in _NUM_RE.finditer(_strip_section_ids(line))}
            for src in sources:
                for hk in phrases.keys() & src.names:
                    hits.append(Hit(kind="name", file=rel, line=ln, source=src.sid, heldout=src.heldout,
                                    detail="" if src.heldout else phrases[hk],
                                    key=phrases[hk] if not src.heldout else hk.hex()))
                if src.hashed:
                    if not is_prompt:
                        continue  # paper decimals are checked in prompt files only
                    found = {n for n in nums if re.fullmatch(r"\d{2,3}\.\d", n) and hash_key([n]) in src.numbers}
                else:
                    pool = src.numbers if is_prompt else {n for n in src.numbers if "." in n or "%" in n}
                    found = nums & pool
                for n in sorted(found):
                    hits.append(Hit(kind="number", file=rel, line=ln, source=src.sid, heldout=src.heldout,
                                    detail="" if src.heldout else n,
                                    key=n if not src.heldout else hash_key([n]).hex()))
    return hits


def load_allowlist(path: Path = ALLOWLIST_PATH) -> list[dict]:
    if not path.exists():
        return []
    entries = json.loads(path.read_text(encoding="utf-8")).get("entries", [])
    for e in entries:
        if not {"kind", "file", "match", "reason"} <= e.keys():
            raise IndexMismatch(f"{path}: allowlist entry missing kind/file/match/reason: {e}")
    return entries


def _allow_key(entry: dict, heldout: bool) -> str:
    """Allowlist entries always quote the runtime file's own text. For a
    held-out hit that text is compared by hash, so no held-out value ever
    has to be written into the allowlist."""
    match = entry["match"]
    if not heldout:
        return match
    if entry["kind"] == "number":
        return hash_key([match]).hex()
    return hash_key(normalize_tokens(match)).hex()


def is_allowed(hit: Hit, allowlist: list[dict]) -> bool:
    for e in allowlist:
        if e["kind"] == hit.kind and e["file"] == hit.file and _allow_key(e, hit.heldout) == hit.key:
            if "line" not in e or e["line"] == hit.line:
                return True
    return False


def run_check(files: list[Path] | None = None, root: Path = SERVICE_DIR, index_path: Path = INDEX_PATH,
              allowlist: list[dict] | None = None, sources: list[Source] | None = None) -> tuple[list[Hit], list[Hit]]:
    """Returns (failures, warnings) after the allowlist is applied."""
    if sources is None:
        sources = paper_sources(load_index(index_path)) + row_sources()
    if files is None:
        files = runtime_files(root)
    allowlist = load_allowlist() if allowlist is None else allowlist
    hits = [h for h in check_files(files, root, sources) if not is_allowed(h, allowlist)]
    return [h for h in hits if h.kind != "ngram5"], [h for h in hits if h.kind == "ngram5"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="files to check (default: all runtime files)")
    parser.add_argument("--root", type=Path, default=SERVICE_DIR, help="paths are reported relative to this")
    parser.add_argument("--index", type=Path, default=INDEX_PATH)
    parser.add_argument("--allowlist", type=Path, default=ALLOWLIST_PATH)
    args = parser.parse_args(argv)
    try:
        files = [f.resolve() for f in args.files] or None
        failures, warnings = run_check(files=files, root=args.root.resolve(), index_path=args.index,
                                       allowlist=load_allowlist(args.allowlist))
    except (IndexMismatch, FileNotFoundError, KeyError, ValueError) as exc:
        print(f"check_prompt_leak: configuration error: {exc}", file=sys.stderr)
        return 2
    for h in sorted(warnings, key=lambda h: (h.file, h.line)):
        print(h.render())
    for h in sorted(failures, key=lambda h: (h.file, h.line)):
        print(h.render())
    n_files = len(files) if files else len(runtime_files(args.root.resolve()))
    print(f"check_prompt_leak: {n_files} files, {len(failures)} leak(s), {len(warnings)} warning(s)")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
