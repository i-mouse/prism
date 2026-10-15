"""Shared helpers for Experiment 3 pre-checks (local only, scratch/exp3/).

extract_pdf_text_sync and normalize_for_match (plus their small private
dependencies) are COPIED VERBATIM below rather than imported, because
importing either source module triggers side effects that need a running
environment:

- Prism.PythonService/main.py (module-level, on import): init_telemetry(),
  PsycopgInstrumentor().instrument(), and construction of AIService,
  RAGService, memory_db connection pool, langgraph AsyncPostgresSaver,
  agent_service.workflow via its own imports - DB/RabbitMQ/blob/LLM client
  setup, not something a read-only pre-check should trigger.
- Prism.PythonService/extraction/grounding.py (module-level, on import):
  `from config import settings` runs Prism.PythonService/config.py:118
  `settings = PrismSettings()`, a pydantic BaseSettings with REQUIRED fields
  `messaging_connection_string` (ConnectionStrings__messaging) and
  `storage_connection_string` (ConnectionStrings__blobs) with no defaults -
  raises pydantic.ValidationError without those env vars / a .env file.

Do not hand-edit the copied blocks below without re-syncing from source;
each is labeled with its exact source file:line range as read on 2026-10-14.
"""
import json
import re
import unicodedata
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[2]
DEV_EVAL_PATH = REPO_ROOT / "docs" / "evals" / "dev_eval.json"
PDF_DIR = REPO_ROOT / "docs" / "research_papers"
DEV_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "dev_match_map.json"
ADJUDICATION_TEMPLATE_PATH = (
    REPO_ROOT / "docs" / "evals" / "fixtures" / "dev" / "exp2" / "adjudication_template.json"
)


# ============================================================================
# Verbatim copy: Prism.PythonService/main.py:76, 82-88, 102-115
# ============================================================================

PASSWORD_PROTECTED_REASON = "password-protected PDF - cannot extract text"


class PdfPasswordProtectedError(Exception):
    """Raised when a PDF requires a password. Deterministic at open time -
    checked immediately after fitz.open() instead of letting
    Document.load_page() raise ValueError partway through iteration, which
    would be ambiguous with the IndexError a 0-page encrypted doc also
    raises during that same iteration."""


def extract_pdf_text_sync(local_path: str) -> tuple[str, int]:
    """Synchronous PDF extraction wrapper so it doesn't block the async loop.

    Returns (text, page_count) - the page count feeds the "preparing" stage
    detail message shown in the activity view.
    """
    final_text = ''
    with fitz.open(local_path) as doc:
        if doc.needs_pass or doc.is_encrypted:
            raise PdfPasswordProtectedError(PASSWORD_PROTECTED_REASON)
        page_count = doc.page_count
        for page in doc:
            final_text += page.get_text()
    return final_text, page_count


# ============================================================================
# Verbatim copy: Prism.PythonService/extraction/grounding.py:253-282
# ============================================================================

_HYPHEN_LINEBREAK_RE = re.compile(r"(\w)-\s*\n\s*(\w)")
_QUOTE_DASH_TABLE = str.maketrans({
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"',
    "–": "-", "—": "-",
})


def _join_hyphen_linebreak(m: re.Match) -> str:
    # Only rejoin a word split across a line ("exam-\nple"); keep the hyphen
    # when the next char isn't lowercase (a digit or a capital after the break).
    if m.group(2).islower():
        return m.group(1) + m.group(2)
    return m.group(0)


def normalize_for_match(text: str) -> str:
    """Normalises text for the Stage-1 RapidFuzz comparison only.

    Absorbs PDF-extraction artefacts (ligatures, soft hyphens, words broken
    across lines, table cells split by newlines, typographic quotes/dashes)
    without touching content: punctuation, digits and "|" are kept, so a
    quote with changed numbers or LLM-added table pipes still mismatches.
    Never persisted and never shown to the auditor. Idempotent.
    """
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("­", "")
    text = _HYPHEN_LINEBREAK_RE.sub(_join_hyphen_linebreak, text)
    text = text.translate(_QUOTE_DASH_TABLE)
    return " ".join(text.split())


# ============================================================================
# Local to this pre-check only (not copied from the pipeline)
# ============================================================================

def load_dev_eval() -> dict:
    return json.loads(DEV_EVAL_PATH.read_text(encoding="utf-8"))


def iter_dev_rows(dev_eval: dict):
    """Yields (filename, row_dict) for every row in every paper, in file order."""
    for paper in dev_eval["papers"]:
        filename = paper["filename"]
        for row in paper["expected_matrix"]:
            yield filename, row


def paper_text(filename: str) -> str:
    """Page-joined text exactly as extract_pdf_text_sync produces it:
    page.get_text() concatenated in page order with NO added separator."""
    text, _ = extract_pdf_text_sync(str(PDF_DIR / filename))
    return text


REGEX_SPLIT_RE = re.compile(r"(?<=[.?!])\s+(?=[A-Z])")


def split_regex(text: str) -> list[str]:
    return REGEX_SPLIT_RE.split(text)


def split_pysbd_pdf_clean(text: str):
    """pysbd doc_type="pdf", clean=True.

    Deviation from the task's literal doc_type="pdf", clean=False: the
    installed pysbd raises ValueError for that combination (doc_type="pdf"
    requires clean=True). clean=True means pysbd may modify/clean the text
    before segmenting, so segments can differ from the raw extracted text;
    comparison still happens via normalize_for_match as planned."""
    import pysbd
    seg = pysbd.Segmenter(language="en", doc_type="pdf", clean=True)
    return seg.segment(text)


def split_pysbd_text_noclean(text: str):
    """pysbd doc_type="text", clean=False.

    Deviation from the task's literal doc_type="pdf": satisfies clean=False
    literally, but loses pysbd's pdf-specific segmentation heuristics."""
    import pysbd
    seg = pysbd.Segmenter(language="en", doc_type="text", clean=False)
    return seg.segment(text)
