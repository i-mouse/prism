"""Pure/offline pieces of the scoped auditor (AUDIT_MODE=scoped, Experiment 1).

No LLM calls here. The orchestration that calls Gemini lives in engine.py
(it owns the call helpers); this module holds:
  - the scoped prompt hash (separate from the legacy get_prompt_version),
  - the per-paper inventory cache and inventory hash,
  - the CHECK-line parser,
  - the lower-only aggregation function,
  - the audit-request log writer (never writes paper text).

The model is never told that code may lower its verdict.
"""
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from extraction.scoped_schemas import MAX_SCOPE_ITEMS, PaperInventory, ScopeItem

PROMPTS_DIR = Path(__file__).parent.parent / "prompts"
SCOPED_PROMPT_FILES = (
    PROMPTS_DIR / "scoped" / "inventory_system.md",
    PROMPTS_DIR / "scoped" / "scope_system.md",
    PROMPTS_DIR / "scoped" / "audit_scoped_system.md",
    Path(__file__).parent / "scoped_schemas.py",
)

VERDICTS = ("not_supported", "partially_supported", "supported")
_RANK = {v: i for i, v in enumerate(VERDICTS)}


def get_scoped_prompt_version() -> str:
    """12-char SHA-256 of the scoped prompt files and scoped_schemas.py.
    Independent of prompt_version.get_prompt_version() (the legacy hash)."""
    combined = b""
    for path in SCOPED_PROMPT_FILES:
        if not path.exists():
            raise FileNotFoundError(f"Scoped prompt file not found at {path}")
        combined += path.read_bytes()
    return hashlib.sha256(combined).hexdigest()[:12]


def paper_hash(paper_text: str) -> str:
    return hashlib.sha256(paper_text.encode("utf-8")).hexdigest()[:16]


def inventory_hash(inventory: PaperInventory) -> str:
    canonical = json.dumps([i.model_dump() for i in inventory.items], sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:12]


def inventory_cache_path(logs_dir: Path, paper_text: str) -> Path:
    return logs_dir / "inventory" / f"{paper_hash(paper_text)}_{get_scoped_prompt_version()}.json"


def load_cached_inventory(logs_dir: Path, paper_text: str) -> Optional[PaperInventory]:
    path = inventory_cache_path(logs_dir, paper_text)
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return PaperInventory.model_validate({"items": data["items"]})
    except (OSError, ValueError, KeyError):
        return None


def save_inventory(logs_dir: Path, paper_text: str, inventory: PaperInventory, model_used: str) -> Path:
    path = inventory_cache_path(logs_dir, paper_text)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "paper_hash": paper_hash(paper_text),
                "scoped_prompt_version": get_scoped_prompt_version(),
                "inventory_hash": inventory_hash(inventory),
                "model_used": model_used,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "items": [i.model_dump() for i in inventory.items],
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return path


def truncate_scope(items: list[ScopeItem]) -> tuple[list[ScopeItem], bool]:
    """Caps the scope list at MAX_SCOPE_ITEMS. Returns (items, truncated)."""
    if len(items) > MAX_SCOPE_ITEMS:
        return items[:MAX_SCOPE_ITEMS], True
    return items, False


# --------------------------------------------------------------------- parser
@dataclass
class Check:
    scope_id: str
    status: str  # holds | fails | not_reported
    quote: Optional[str] = None
    raw: str = ""


@dataclass
class ParsedChecks:
    checks: dict[str, Check] = field(default_factory=dict)  # one per scope id, first wins
    flags: list[str] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)
    recognised_lines: int = 0

    @property
    def parse_failed(self) -> bool:
        return self.recognised_lines == 0


_CHECK_RE = re.compile(
    r"^[\s\W]*CHECK\s+(S\d+)\s*:\s*(holds|fails|not_reported)\b\s*(?:\|\s*QUOTE:\s*(.*?))?\s*$",
    re.IGNORECASE,
)
_QUOTE_PAIRS = {'"': '"', "“": "”"}


def _strip_quote(raw: str) -> str:
    q = raw.strip()
    if len(q) >= 2 and q[0] in _QUOTE_PAIRS and q[-1] in _QUOTE_PAIRS.values():
        q = q[1:-1]
    return q.strip()


def parse_checks(audit_text: str, scope_ids: list[str]) -> ParsedChecks:
    """Parses CHECK lines against the fixed scope.

    - A scope id with no CHECK line becomes not_reported, flag missing_check:<id>.
    - An unknown id is ignored, flag unknown_id:<id>.
    - A duplicate id keeps the first line, flag duplicate_id:<id>.
    - fails with no quote is kept as fails but flagged fails_no_quote:<id>
      (aggregation cannot lower on it).
    """
    out = ParsedChecks()
    wanted = {s.upper() for s in scope_ids}
    for line in (audit_text or "").splitlines():
        if "CHECK" not in line.upper():
            continue
        m = _CHECK_RE.match(line)
        if not m:
            continue
        out.raw_lines.append(line.strip())
        out.recognised_lines += 1
        sid = m.group(1).upper()
        status = m.group(2).lower()
        quote = _strip_quote(m.group(3)) if m.group(3) else None
        if sid not in wanted:
            out.flags.append(f"unknown_id:{sid}")
            continue
        if sid in out.checks:
            out.flags.append(f"duplicate_id:{sid}")
            continue
        if status == "not_reported":
            quote = None
        if status == "fails" and not quote:
            out.flags.append(f"fails_no_quote:{sid}")
        out.checks[sid] = Check(scope_id=sid, status=status, quote=quote or None, raw=line.strip())
    for sid in scope_ids:
        if sid.upper() not in out.checks:
            out.flags.append(f"missing_check:{sid.upper()}")
            out.checks[sid.upper()] = Check(scope_id=sid.upper(), status="not_reported", raw="")
    return out


# ---------------------------------------------------------------- aggregation
@dataclass
class Aggregation:
    model_verdict: Optional[str]
    final: Optional[str]
    lowered: bool = False
    trigger_id: Optional[str] = None
    trigger_quote: Optional[str] = None
    aggregation_skipped: bool = False
    dropped_ungrounded: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


def _default_grounded(quote: str, paper_text: str) -> bool:
    from extraction.grounding import _passes_rapidfuzz  # Stage 1, honours GROUNDING_NORMALIZE

    return _passes_rapidfuzz(quote, paper_text)


def aggregate(
    model_verdict: Optional[str],
    scope_ids: list[str],
    parsed: Optional[ParsedChecks],
    paper_text: str,
    grounded: Callable[[str, str], bool] = _default_grounded,
) -> Aggregation:
    """Lower-only aggregation.

    final = model_verdict, except supported -> partially_supported when some
    in-scope CHECK is `fails` and its quote passes the Stage-1 grounding gate
    (with normalisation). not_reported never lowers; ids outside the scope
    never lower (the parser already discarded them); the function never
    returns a verdict ranked above model_verdict. On an unreadable verdict or
    an unparseable CHECK block it keeps model_verdict and sets
    aggregation_skipped.
    """
    agg = Aggregation(model_verdict=model_verdict, final=model_verdict)
    if parsed is not None:
        agg.flags.extend(parsed.flags)
    if model_verdict not in _RANK:
        agg.aggregation_skipped = True
        agg.flags.append("unparsed_verdict")
        return agg
    if parsed is None or (scope_ids and parsed.parse_failed):
        agg.aggregation_skipped = True
        agg.flags.append("checks_unparsed")
        return agg
    if model_verdict != "supported":
        return agg
    for sid in scope_ids:
        check = parsed.checks.get(sid.upper())
        if check is None or check.status != "fails" or not check.quote:
            continue
        if grounded(check.quote, paper_text):
            agg.lowered = True
            agg.final = "partially_supported"
            agg.trigger_id = sid.upper()
            agg.trigger_quote = check.quote
            break
        agg.dropped_ungrounded.append(sid.upper())
    assert _RANK[agg.final] <= _RANK[model_verdict], "aggregation must never raise a verdict"
    return agg


# -------------------------------------------------------------------- logging
def write_scoped_audit_log(logs_dir: Path, chat_id: str, correlation_id: Optional[str], record: dict) -> Path:
    """One JSON record per scoped claim audit under logs/audit_scoped/.
    Callers must not put paper text in `record`; the claim text is allowed."""
    d = logs_dir / "audit_scoped"
    d.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    path = d / f"{now.strftime('%Y%m%dT%H%M%S%f')}_{chat_id}_{correlation_id or 'none'}.json"
    entry = {"timestamp": now.isoformat(), **record}
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
