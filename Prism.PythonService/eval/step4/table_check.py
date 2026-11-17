"""Pure logic of the step 4 table checker (decisions.md "Pre-registration: step 4 - table checker for table claims
(text only), Vertex, 3 runs - 2026-11-15"). No LLM, no network. The only file reads are the prompt / schema files,
for the two hashes and the checker's system prompt.

Rulings implemented here:
  1  routing, the joined table blocks and the 60,000-character cap (route, build_table_blocks)
  3  the code guard on quoted cells (guard_piece)
  4  could-not-check (piece_outcomes)
  5  no_row counts as failed (piece_outcomes)
  6  the claim result and the fallback to today's auditor (claim_result)
  7  the model compares cells; code only guards quotes and counts failed pieces

The finder (eval/step4/tablefind.py, frozen at FINDER_COMMIT) is imported, never edited. Nothing in this file names
an eval row, a paper or a table number.
"""
import hashlib
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path

from eval.auditor_v2.cell_parser import ParsedCell, parse_cell, values_equal
from eval.step4 import tablefind
from eval.step4.table_check_schemas import PieceAnswer

FINDER_COMMIT = "f7ca8a3"
JOIN_CAP_CHARS = 60_000
BLOCK_SEPARATOR = "\n\n"

_STEP4_DIR = Path(__file__).parent
_SERVICE_ROOT = _STEP4_DIR.parent.parent
CHECKER_PROMPT_PATH = _STEP4_DIR / "table_check_system.md"
CHECKER_SCHEMA_PATH = _STEP4_DIR / "table_check_schemas.py"
LISTER_PROMPT_PATH = _SERVICE_ROOT / "prompts" / "scope_list_system.md"
LISTER_SCHEMA_PATH = _SERVICE_ROOT / "extraction" / "scope_schemas.py"

# Routing reasons (RouteDecision.reason).
ROUTED = "routed"
NO_FOUND_TABLE = "no_found_table"
NO_TABLE_MENTION = "no_table_mention"
CITES_DROPPED_TABLE = "cites_dropped_table"
NO_SPANS = "no_spans"          # set by the caller: a routed claim with no frozen evidence span

# Piece states.
FAILED = "failed"
PASSED = "passed"
COULD_NOT_CHECK = "could_not_check"

# Could-not-check reasons.
CNC_CHECKER_FAILED = "checker_failed"
CNC_MISSING_ANSWER = "missing_answer"
CNC_NOT_A_TABLE_PIECE = "not_a_table_piece"
CNC_GUARD_FAILED = "guard_failed"

# Guard failure reasons.
GUARD_NO_CELLS = "no_cells"
GUARD_TABLE_NOT_INCLUDED = "table_not_included"
GUARD_VALUE_MISSING = "value_missing"
GUARD_ROW_LABEL_MISSING = "row_label_missing"
GUARD_NAME_CHECK = "name_check"

# Fallback reasons (why today's auditor ran on a routed claim).
FALLBACK_LISTER_FAILED = "lister_failed"
FALLBACK_ZERO_PIECES = "zero_pieces"
FALLBACK_COULD_NOT_CHECK = "could_not_check"

LABEL_SUPPORTED = "supported"
LABEL_PARTIAL = "partially_supported"
LABEL_NOT_SUPPORTED = "not_supported"

_WORD_RE = re.compile(r"[^\W\d_]{3,}")


# --- hashes ---------------------------------------------------------------------------------------------------

def _hash_files(*paths: Path) -> str:
    combined = b""
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"hashed file not found at {path}")
        combined += path.read_bytes()
    return hashlib.sha256(combined).hexdigest()[:12]


def checker_hash() -> str:
    """12-char sha256 of the checker's system prompt + its response-schema file."""
    return _hash_files(CHECKER_PROMPT_PATH, CHECKER_SCHEMA_PATH)


def lister_hash() -> str:
    """12-char sha256 of the scope lister's system prompt + its response-schema file (the lister is reused
    unchanged; these are the two files that reach the model in a lister call)."""
    return _hash_files(LISTER_PROMPT_PATH, LISTER_SCHEMA_PATH)


def checker_system_prompt() -> str:
    return CHECKER_PROMPT_PATH.read_text(encoding="utf-8")


# --- table blocks (ruling 1) ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class TableBlocks:
    """One paper's table blocks. included: table number -> block, in number order, as sent to the checker.
    dropped: found tables left out by the 60,000-character cap. block_cap_hits: included or dropped tables whose
    own block was cut by the finder's per-table cap. text: the joined blocks ("" when no table was found)."""
    included: dict[int, str] = field(default_factory=dict)
    dropped: tuple[int, ...] = ()
    block_cap_hits: tuple[int, ...] = ()
    text: str = ""

    @property
    def found(self) -> tuple[int, ...]:
        return tuple(sorted(set(self.included) | set(self.dropped)))


def table_header(n: int) -> str:
    return f"=== Table {n} ==="


def _section(n: int, block: str) -> str:
    return f"{table_header(n)}\n{block}"


def build_table_blocks(paper_text: str) -> TableBlocks:
    """Every table the frozen finder finds exactly once, joined in table-number order, each headed
    "=== Table N ===". The cap counts the joined text (headers and separators included); the first table that
    does not fit and every later one are dropped."""
    view = tablefind.all_tables_view(paper_text)
    included: dict[int, str] = {}
    dropped: list[int] = []
    cap_hits: list[int] = []
    sections: list[str] = []
    length = 0
    for n in sorted(n for n, found_once in view.items() if found_once):
        block, cap_hit = tablefind.cut_block(paper_text, tablefind.find_caption_lines(paper_text, n)[0])
        if cap_hit:
            cap_hits.append(n)
        section = _section(n, block)
        added = len(section) + (len(BLOCK_SEPARATOR) if sections else 0)
        if dropped or length + added > JOIN_CAP_CHARS:
            dropped.append(n)
            continue
        included[n] = block
        sections.append(section)
        length += added
    return TableBlocks(
        included=included, dropped=tuple(dropped), block_cap_hits=tuple(cap_hits),
        text=BLOCK_SEPARATOR.join(sections),
    )


# --- routing (ruling 1) ---------------------------------------------------------------------------------------

@dataclass(frozen=True)
class RouteDecision:
    routed: bool
    reason: str
    cited: tuple[int, ...] = ()


def cited_table_numbers(texts) -> tuple[int, ...]:
    """Table numbers mentioned in the given texts: "Table", spaces, digits - the finder's all-tables pattern."""
    numbers: set[int] = set()
    for text in texts:
        if isinstance(text, str):
            numbers.update(int(m.group(1)) for m in tablefind._MENTION_RE.finditer(text))
    return tuple(sorted(numbers))


def span_texts(spans) -> list[str]:
    """source_section and source_text of every evidence span (dicts or objects)."""
    out: list[str] = []
    for span in spans or ():
        for key in ("source_section", "source_text"):
            value = span.get(key) if isinstance(span, dict) else getattr(span, key, None)
            if isinstance(value, str):
                out.append(value)
    return out


def route(claim_text: str, spans, blocks: TableBlocks) -> RouteDecision:
    """A claim is routed if its text or any evidence span's source_section / source_text mentions a table, the
    paper has at least one found table, and no cited table was dropped by the cap."""
    cited = cited_table_numbers([claim_text, *span_texts(spans)])
    if not blocks.included:
        return RouteDecision(False, NO_FOUND_TABLE, cited)
    if not cited:
        return RouteDecision(False, NO_TABLE_MENTION, cited)
    if set(cited) & set(blocks.dropped):
        return RouteDecision(False, CITES_DROPPED_TABLE, cited)
    return RouteDecision(True, ROUTED, cited)


# --- checker input --------------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Piece:
    piece_id: int      # 1-based position in the lister's list
    text: str
    kind: str


def pieces_from_items(items) -> list[Piece]:
    """The lister's items (objects with .text and .kind) as numbered pieces."""
    return [Piece(i, item.text, item.kind) for i, item in enumerate(items, start=1)]


def build_checker_user_text(claim_text: str, pieces: list[Piece], blocks_text: str) -> str:
    lines = "\n".join(f"{p.piece_id}. [{p.kind}] {p.text}" for p in pieces)
    return f"CLAIM:\n{claim_text}\n\nPIECES:\n{lines}\n\nTABLES:\n{blocks_text}\n"


def invalid_answer_ids(n_pieces: int, answers: list[PieceAnswer]) -> str | None:
    """None when every piece_id is one of 1..n_pieces and none repeats; else the reason (the response is then
    treated like invalid JSON). A listed piece with no answer is not invalid: that piece is could-not-check."""
    seen: set[int] = set()
    for answer in answers:
        if not 1 <= answer.piece_id <= n_pieces:
            return f"piece_id {answer.piece_id} is not one of 1..{n_pieces}"
        if answer.piece_id in seen:
            return f"piece_id {answer.piece_id} is answered more than once"
        seen.add(answer.piece_id)
    return None


# --- code guard (ruling 3) ------------------------------------------------------------------------------------

@lru_cache(maxsize=256)
def _block_cells(block: str) -> tuple[ParsedCell, ...]:
    return tuple(parse_cell(token) for token in block.split())


@lru_cache(maxsize=256)
def _block_norm(block: str) -> str:
    return tablefind.normalize_text(block)


def _words(text: str) -> set[str]:
    return set(_WORD_RE.findall(unicodedata.normalize("NFKC", text or "").casefold()))


def value_in_block(value: str, block: str) -> bool:
    """Every whitespace token of the quoted value equals some whitespace token of the block (shared parse_cell /
    values_equal). An empty value is not found."""
    tokens = (value or "").split()
    if not tokens:
        return False
    cells = _block_cells(block)
    return all(any(values_equal(cell, parsed) for cell in cells) for parsed in map(parse_cell, tokens))


def row_label_in_block(row_label: str, block: str) -> bool:
    norm = tablefind.normalize_text(row_label or "")
    return bool(norm) and norm in _block_norm(block)


def guard_piece(piece_text: str, cells, blocks: TableBlocks) -> list[str]:
    """Reasons the quoted cells of a backed / not_backed piece fail the guard; an empty list is a pass.
    Every quoted value and row label must be in that table's block, and at least one word of 3+ letters from a
    quoted row or column label must be a word of the piece text. Code never redoes the comparison."""
    cells = list(cells or ())
    if not cells:
        return [GUARD_NO_CELLS]
    reasons: list[str] = []
    label_words: set[str] = set()
    for cell in cells:
        block = blocks.included.get(cell.table)
        if block is None:
            reasons.append(GUARD_TABLE_NOT_INCLUDED)
            continue
        if not value_in_block(cell.value, block):
            reasons.append(GUARD_VALUE_MISSING)
        if not row_label_in_block(cell.row_label, block):
            reasons.append(GUARD_ROW_LABEL_MISSING)
        label_words |= _words(cell.row_label) | _words(cell.column_label)
    if not label_words & _words(piece_text):
        reasons.append(GUARD_NAME_CHECK)
    return list(dict.fromkeys(reasons))


# --- pieces and the claim result (rulings 4, 5, 6) ------------------------------------------------------------

@dataclass
class PieceOutcome:
    piece_id: int
    text: str
    kind: str
    answer: str | None                 # the checker's answer, None when there is none
    state: str                         # FAILED / PASSED / COULD_NOT_CHECK
    reason: str | None = None          # the could-not-check reason
    guard_reasons: list[str] = field(default_factory=list)
    cells: list[dict] = field(default_factory=list)


def piece_outcomes(pieces: list[Piece], answers: list[PieceAnswer] | None, blocks: TableBlocks) -> list[PieceOutcome]:
    """answers None = the checker call failed or returned invalid JSON after its retry: every piece is
    could-not-check. no_row is failed; not_a_table_piece, a guard failure and a missing answer are could-not-check."""
    by_id = {a.piece_id: a for a in answers} if answers is not None else {}
    out: list[PieceOutcome] = []
    for piece in pieces:
        if answers is None:
            out.append(PieceOutcome(piece.piece_id, piece.text, piece.kind, None, COULD_NOT_CHECK, CNC_CHECKER_FAILED))
            continue
        answer = by_id.get(piece.piece_id)
        if answer is None:
            out.append(PieceOutcome(piece.piece_id, piece.text, piece.kind, None, COULD_NOT_CHECK, CNC_MISSING_ANSWER))
            continue
        cells = [c.model_dump() for c in answer.cells]
        if answer.answer == "no_row":
            out.append(PieceOutcome(piece.piece_id, piece.text, piece.kind, answer.answer, FAILED, cells=cells))
        elif answer.answer == "not_a_table_piece":
            out.append(PieceOutcome(
                piece.piece_id, piece.text, piece.kind, answer.answer, COULD_NOT_CHECK, CNC_NOT_A_TABLE_PIECE,
                cells=cells,
            ))
        else:
            reasons = guard_piece(piece.text, answer.cells, blocks)
            if reasons:
                out.append(PieceOutcome(
                    piece.piece_id, piece.text, piece.kind, answer.answer, COULD_NOT_CHECK, CNC_GUARD_FAILED,
                    guard_reasons=reasons, cells=cells,
                ))
            else:
                state = PASSED if answer.answer == "backed" else FAILED
                out.append(PieceOutcome(piece.piece_id, piece.text, piece.kind, answer.answer, state, cells=cells))
    return out


@dataclass(frozen=True)
class ClaimResult:
    label: str | None        # None when today's auditor decides (use_fallback)
    use_fallback: bool
    n_pieces: int
    n_failed: int
    n_could_not_check: int


def claim_result(outcomes: list[PieceOutcome]) -> ClaimResult:
    """All pieces checked and all failed -> not_supported; >= 1 failed -> partially_supported; 0 failed and all
    checked -> supported; 0 failed and >= 1 could-not-check (or no piece at all) -> today's auditor."""
    n = len(outcomes)
    failed = sum(1 for o in outcomes if o.state == FAILED)
    cnc = sum(1 for o in outcomes if o.state == COULD_NOT_CHECK)
    if n and cnc == 0 and failed == n:
        return ClaimResult(LABEL_NOT_SUPPORTED, False, n, failed, cnc)
    if failed >= 1:
        return ClaimResult(LABEL_PARTIAL, False, n, failed, cnc)
    if n and cnc == 0:
        return ClaimResult(LABEL_SUPPORTED, False, n, failed, cnc)
    return ClaimResult(None, True, n, failed, cnc)


# --- trace and counters ---------------------------------------------------------------------------------------

@dataclass
class ClaimTrace:
    """What a flagged replay records for one routed claim."""
    routed: bool = True
    cited: list[int] = field(default_factory=list)
    lister_failed: bool = False
    checker_failed: bool = False
    pieces: list[PieceOutcome] = field(default_factory=list)
    label: str | None = None             # the checker's label; None when the auditor decided
    use_fallback: bool = False
    fallback_reason: str | None = None
    n_failed: int = 0
    n_could_not_check: int = 0
    checker_model_served: str | None = None

    @property
    def source(self) -> str:
        return "fallback_audit" if self.use_fallback else "checker"

    def to_fields(self) -> dict:
        return {
            "routed": True, "source": self.source, "cited": list(self.cited),
            "lister_failed": self.lister_failed, "checker_failed": self.checker_failed,
            "checker_label": self.label, "fallback_reason": self.fallback_reason,
            "n_pieces": len(self.pieces), "n_failed": self.n_failed, "n_could_not_check": self.n_could_not_check,
            "pieces": [asdict(p) for p in self.pieces],
        }


def unrouted_fields(decision: RouteDecision, reason: str | None = None) -> dict:
    return {"routed": False, "source": "audit", "reason": reason or decision.reason, "cited": list(decision.cited)}


@dataclass
class TableCheckStats:
    """Counters of one flagged run (one repeat). lister_failures / checker_failures count claims whose call still
    failed after the one retry (V6)."""
    claims: int = 0
    routed_claims: int = 0
    unrouted: dict = field(default_factory=dict)            # reason -> claims
    lister_failures: int = 0
    checker_failures: int = 0
    pieces: int = 0
    answers: dict = field(default_factory=dict)             # answer -> pieces
    could_not_check: dict = field(default_factory=dict)     # reason -> pieces
    guard_failures: int = 0
    guard_reasons: dict = field(default_factory=dict)       # guard reason -> pieces
    failed_pieces: int = 0
    checker_labels: dict = field(default_factory=dict)      # label -> claims decided by the checker
    fallback_claims: int = 0
    fallback_reasons: dict = field(default_factory=dict)    # reason -> claims

    @staticmethod
    def _bump(counter: dict, key: str) -> None:
        counter[key] = counter.get(key, 0) + 1

    def record_unrouted(self, reason: str) -> None:
        self.claims += 1
        self._bump(self.unrouted, reason)

    def record_routed(self, trace: ClaimTrace) -> None:
        self.claims += 1
        self.routed_claims += 1
        self.lister_failures += int(trace.lister_failed)
        self.checker_failures += int(trace.checker_failed)
        self.pieces += len(trace.pieces)
        for piece in trace.pieces:
            if piece.answer is not None:
                self._bump(self.answers, piece.answer)
            if piece.state == FAILED:
                self.failed_pieces += 1
            if piece.state == COULD_NOT_CHECK and piece.reason:
                self._bump(self.could_not_check, piece.reason)
            if piece.guard_reasons:
                self.guard_failures += 1
                for reason in piece.guard_reasons:
                    self._bump(self.guard_reasons, reason)
        if trace.use_fallback:
            self.fallback_claims += 1
            self._bump(self.fallback_reasons, trace.fallback_reason or FALLBACK_COULD_NOT_CHECK)
        elif trace.label is not None:
            self._bump(self.checker_labels, trace.label)
