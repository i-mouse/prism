"""CLI entry point for the Prism eval harness: matrix_eval.json runner.

Loads the claim-support matrix and fetches actual claims + matches per
paper, then scores and aggregates into a single run, prints a report,
writes a JSON log, and exits 0/1 for CI gating.

Two sources, two very different cost profiles:
  --source db       Reads Postgres, calls the LLM-as-judge matcher live
                     (eval/matcher.py). Local dev only - needs AI_API_KEY.
  --source fixture  Reads claims AND matches already frozen into the
                     fixture by eval/dump_fixture.py. Zero LLM calls, so
                     eval.matcher (and google.genai) is never imported -
                     this is what CI runs, no API key required.
"""
import argparse
import asyncio
import json
import statistics
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from eval.data_source import read_from_db, read_from_fixture, read_matches_from_fixture
from eval.match_map import load_match_map
from eval.matrix_loader import MatrixSpec, PaperSpec, load_matrix
from eval.scorer import score
from eval.types import EvalReport
from extraction.prompt_version import get_prompt_version

REPO_ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = Path(__file__).parent.parent / "logs" / "eval"
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"
DEFAULT_MATCH_MAP_PATH = REPO_ROOT / "docs" / "evals" / "match_map.json"


@dataclass
class PaperRunResult:
    """Outcome for one paper: either SKIPPED (no data) or SCORED (1+ EvalReports)."""

    paper_id: str
    filename: str
    status: str  # "SCORED" | "SKIPPED"
    claims_count: int = 0
    reports: list[EvalReport] = field(default_factory=list)
    reason: str | None = None


@dataclass
class MatrixReport:
    """Aggregate across all SCORED papers, worst-case across --repeat runs."""

    correct_refusals: int
    total_negatives: int
    refusal_rate: float
    refused_by_label: int
    refused_by_grounding: int
    wrongly_affirmed: int
    not_extracted: int
    positive_hits: int
    positive_total: int
    false_rejections: int
    false_rejection_rate: float
    positive_hit_floor: int
    refusal_rate_valid: bool
    scored_papers: int
    strict_correct_refusals: int
    strict_refusal_rate: float
    skipped: int


@dataclass
class MatchMapGate:
    """Whether the human-adjudicated match map (docs/evals/match_map.json)
    backs up this run's headline number, computed against the golden ids
    actually in scope for this run (all 37 by default, fewer under --paper).

    matcher_miss = total_rows - coverage_count: rows with no adjudication
    yet. This is a transitional bucket - it exists because match_map.json
    starts as an all-null skeleton and gets filled in by hand over time, not
    because it's a fourth scoring outcome alongside REFUSED/WRONGLY_AFFIRMED/
    NOT_EXTRACTED. It is reported, never credited, and never overrides the
    per-row outcome from eval/scorer.py.
    """

    total_rows: int
    coverage_count: int
    matcher_miss: int
    coverage_ok: bool
    hash_mismatch: bool
    current_prompt_hash: str
    match_map_prompt_hash: Optional[str]
    load_error: Optional[str]


def _build_match_map_gate(golden_ids: set[str], match_map_path: Path) -> MatchMapGate:
    current_prompt_hash = get_prompt_version()
    total_rows = len(golden_ids)

    match_map = None
    load_error: Optional[str] = None
    try:
        match_map = load_match_map(match_map_path, golden_ids)
    except FileNotFoundError:
        load_error = f"no match map found at {match_map_path}"
    except Exception as exc:  # malformed JSON, schema mismatch, id mismatch
        load_error = str(exc)

    coverage_count = match_map.coverage_count if match_map is not None else 0
    match_map_prompt_hash = match_map.metadata.prompt_hash if match_map is not None else None

    return MatchMapGate(
        total_rows=total_rows,
        coverage_count=coverage_count,
        matcher_miss=total_rows - coverage_count,
        coverage_ok=match_map is not None and coverage_count == total_rows,
        hash_mismatch=(
            match_map is not None
            and match_map_prompt_hash is not None
            and match_map_prompt_hash != current_prompt_hash
        ),
        current_prompt_hash=current_prompt_hash,
        match_map_prompt_hash=match_map_prompt_hash,
        load_error=load_error,
    )


def _display_name(result: PaperRunResult) -> str:
    return Path(result.filename).stem


def _paper_matches(paper: PaperSpec, name: str) -> bool:
    if name == "all":
        return True
    needle = name.lower()
    return needle in paper.paper_id.lower() or needle in paper.filename.lower()


async def _run_paper(
    paper: PaperSpec,
    source: str,
    fixture_dir: Path,
    repeat: int,
    positive_hit_floor: int,
) -> PaperRunResult:
    reports: list[EvalReport] = []

    if source == "db":
        # Imported here, not at module scope, so a --source fixture run
        # (CI, no AI_API_KEY) never imports eval.matcher or google.genai.
        from eval.matcher import match

        try:
            claims = await read_from_db(paper.filename)
        except Exception as exc:
            return PaperRunResult(
                paper_id=paper.paper_id, filename=paper.filename, status="SKIPPED", reason=f"read failed: {exc}"
            )

        if not claims:
            return PaperRunResult(paper_id=paper.paper_id, filename=paper.filename, status="SKIPPED", reason="no DB data")

        for _ in range(repeat):
            matches, _used_matcher_model = await match(paper.paper_id, paper.expected_rows, claims)
            reports.append(score(paper.expected_rows, claims, matches, positive_hit_floor=positive_hit_floor))

    else:  # source == "fixture"
        fixture_path = fixture_dir / f"{paper.paper_id}.json"

        try:
            claims = read_from_fixture(fixture_path)
        except Exception as exc:
            return PaperRunResult(
                paper_id=paper.paper_id, filename=paper.filename, status="SKIPPED", reason=f"read failed: {exc}"
            )

        if not claims:
            return PaperRunResult(paper_id=paper.paper_id, filename=paper.filename, status="SKIPPED", reason="fixture missing")

        matches = read_matches_from_fixture(fixture_path)
        if not matches:
            return PaperRunResult(
                paper_id=paper.paper_id,
                filename=paper.filename,
                status="SKIPPED",
                reason=(
                    "legacy fixture missing 'matches' key; regenerate via "
                    f"'uv run python -m eval.dump_fixture --paper {paper.paper_id}'"
                ),
            )

        # Matches are frozen - re-scoring under --repeat is deterministic,
        # so variance across runs is honestly zero.
        for _ in range(repeat):
            reports.append(score(paper.expected_rows, claims, matches, positive_hit_floor=positive_hit_floor))

    return PaperRunResult(
        paper_id=paper.paper_id,
        filename=paper.filename,
        status="SCORED",
        claims_count=len(claims),
        reports=reports,
    )


def _variance_summary(reports: list[EvalReport]) -> dict:
    correct_refusals = [r.correct_refusals for r in reports]
    positive_hits = [r.positive_hits for r in reports]
    return {
        "runs": len(reports),
        "correct_refusals": {
            "min": min(correct_refusals),
            "max": max(correct_refusals),
            "mean": statistics.mean(correct_refusals),
        },
        "positive_hits": {
            "min": min(positive_hits),
            "max": max(positive_hits),
            "mean": statistics.mean(positive_hits),
        },
    }


def _aggregate(results: list[PaperRunResult], positive_hit_floor: int) -> MatrixReport:
    scored = [r for r in results if r.status == "SCORED"]

    # Worst-case across --repeat runs: each metric is independently pushed to
    # its worst value per paper, then summed. A partially-invalid variance
    # run must fail the gate, so we never let a lucky run mask a bad one.
    # "Worst" is min() for metrics where higher is better (hits, correct
    # refusals) and max() for false_rejections, where higher is worse.
    correct_refusals = sum(min(r.correct_refusals for r in result.reports) for result in scored)
    strict_correct_refusals = sum(min(r.strict_correct_refusals for r in result.reports) for result in scored)
    total_negatives = sum(result.reports[0].total_negatives for result in scored)
    refused_by_label = sum(min(r.refused_by_label for r in result.reports) for result in scored)
    refused_by_grounding = sum(min(r.refused_by_grounding for r in result.reports) for result in scored)
    # wrongly_affirmed/not_extracted are bad-if-high, like false_rejections below -
    # worst-cased with max() so a lucky run can't mask a paper that sometimes
    # fails outright or sometimes extracts nothing for a negative row.
    wrongly_affirmed = sum(max(r.wrongly_affirmed for r in result.reports) for result in scored)
    not_extracted = sum(max(r.not_extracted for r in result.reports) for result in scored)
    positive_hits = sum(min(r.positive_hits for r in result.reports) for result in scored)
    positive_total = sum(result.reports[0].positive_total for result in scored)
    false_rejections = sum(max(r.false_rejections for r in result.reports) for result in scored)
    # skipped is a property of the frozen claims (grounding already ran),
    # not of matcher variance, so it's stable across --repeat like
    # total_negatives/positive_total rather than worst-cased like the
    # outcome-derived metrics above.
    skipped = sum(result.reports[0].skipped for result in scored)

    refusal_rate = correct_refusals / total_negatives if total_negatives else 0.0
    strict_refusal_rate = strict_correct_refusals / total_negatives if total_negatives else 0.0
    false_rejection_rate = false_rejections / positive_total if positive_total else 0.0
    refusal_rate_valid = positive_hits >= positive_hit_floor

    return MatrixReport(
        correct_refusals=correct_refusals,
        total_negatives=total_negatives,
        refusal_rate=refusal_rate,
        refused_by_label=refused_by_label,
        refused_by_grounding=refused_by_grounding,
        wrongly_affirmed=wrongly_affirmed,
        not_extracted=not_extracted,
        positive_hits=positive_hits,
        positive_total=positive_total,
        false_rejections=false_rejections,
        false_rejection_rate=false_rejection_rate,
        positive_hit_floor=positive_hit_floor,
        refusal_rate_valid=refusal_rate_valid,
        scored_papers=len(scored),
        strict_correct_refusals=strict_correct_refusals,
        strict_refusal_rate=strict_refusal_rate,
        skipped=skipped,
    )


def _print_verbose_false_rejections(results: list[PaperRunResult]) -> list[str]:
    """One block per false-rejected positive-support row: paper, claim
    summary, extractor label, grounder verdict, and the golden expected
    label - everything needed to eyeball whether Slice 2.8 fixed it."""
    lines = ["", "False rejections (positive-support rows the grounder refused):"]
    found_any = False

    for result in results:
        if result.status == "SKIPPED":
            continue
        for report in result.reports[:1]:  # first run is representative; --repeat variance shown separately
            for outcome in report.per_row.values():
                if outcome.outcome != "FALSE_REJECTION":
                    continue
                found_any = True
                lines.append(f"  [{_display_name(result)}] {outcome.expected_id}")
                lines.append(f"    claim summary:    {outcome.actual_claim_summary or '(none)'}")
                lines.append(f"    extractor label:  {outcome.actual_label}")
                lines.append(f"    grounder verdict: {outcome.actual_grounding_status}")
                lines.append(f"    golden expected:  {outcome.expected_label}")

    if not found_any:
        lines.append("  (none)")
    return lines


def _print_report(
    results: list[PaperRunResult],
    aggregate: MatrixReport,
    gate: MatchMapGate,
    threshold_refusal_rate: float,
    log_relpath: Path,
    exit_code: int,
    verbose: bool = False,
) -> None:
    lines = ["Prism eval - matrix run", "======================="]

    name_width = max((len(_display_name(r)) for r in results), default=5)
    for result in results:
        name = _display_name(result).ljust(name_width)
        if result.status == "SKIPPED":
            lines.append(f"paper: {name}   claims: {0:>2}   SKIPPED ({result.reason})")
            continue

        report = result.reports[0]
        matched = sum(1 for outcome in report.per_row.values() if outcome.actual_label is not None)
        lines.append(f"paper: {name}   claims: {result.claims_count:>2}   matched: {matched}")
        if len(result.reports) > 1:
            variance = _variance_summary(result.reports)
            cr, ph = variance["correct_refusals"], variance["positive_hits"]
            lines.append(
                f"  variance (n={variance['runs']}): "
                f"correct_refusals min/mean/max={cr['min']}/{cr['mean']:.1f}/{cr['max']}  "
                f"positive_hits min/mean/max={ph['min']}/{ph['mean']:.1f}/{ph['max']}"
            )

    lines.append("")

    refusal_pct = round(aggregate.refusal_rate * 100)
    strict_pct = round(aggregate.strict_refusal_rate * 100)
    threshold_pct = round(threshold_refusal_rate * 100)
    refusal_tag = "PASS" if aggregate.refusal_rate >= threshold_refusal_rate else "FAIL"
    positive_pct = round(aggregate.positive_hits / aggregate.positive_total * 100) if aggregate.positive_total else 0
    false_rejection_pct = round(aggregate.false_rejection_rate * 100)
    floor_tag = "OK" if aggregate.refusal_rate_valid else "BELOW FLOOR - mark invalid"

    lines.append("=" * 64)
    lines.append("Prism Eval Results")
    lines.append("=" * 64)

    if gate.hash_mismatch:
        lines.append("!" * 64)
        lines.append("WARNING: match_map.json was adjudicated at a different prompt_hash.")
        lines.append(f"  match_map.json prompt_hash: {gate.match_map_prompt_hash}")
        lines.append(f"  this run's prompt_hash:     {gate.current_prompt_hash}")
        lines.append("  A map adjudicated at one hash is invalid once the prompt changes -")
        lines.append("  re-adjudicate before trusting any refusal-rate headline.")
        lines.append("!" * 64)

    if gate.load_error:
        lines.append(f"WARNING: match_map.json could not be used - {gate.load_error}")

    if aggregate.skipped > 0:
        lines.append(f"{aggregate.skipped} claims SKIPPED (transient errors) — not scored")
        lines.append(
            f"INCOMPLETE — {aggregate.skipped} spans not evaluated, cannot compute headline metric"
        )
    elif not gate.coverage_ok:
        lines.append(
            f"HEADLINE SUPPRESSED — match map coverage {gate.coverage_count}/{gate.total_rows}. "
            "Number is not citeable."
        )
    else:
        lines.append(
            f"Refusal-family rate: {aggregate.correct_refusals}/{aggregate.total_negatives} ({refusal_pct}%) "
            f"[{refusal_tag} vs {threshold_pct}% threshold] "
            "— grounder correctly refused claims paper doesn't support"
        )
    lines.append(
        f"Strict-label rate:   {aggregate.strict_correct_refusals}/{aggregate.total_negatives} ({strict_pct}%) "
        "— refused via exact expected_label match only, no omission/grounding-rejection credit"
    )
    lines.append(f"  by label:            {aggregate.refused_by_label}")
    lines.append(f"  by grounding reject: {aggregate.refused_by_grounding}")
    lines.append(f"  wrongly affirmed:    {aggregate.wrongly_affirmed}  (FAIL - not credited)")
    lines.append(f"  not extracted:       {aggregate.not_extracted}  (no claim emitted - not credited)")
    lines.append(f"  skipped:             {aggregate.skipped}  (transient grounding error - excluded from denominator)")
    lines.append(
        f"  matcher_miss:        {gate.matcher_miss}  (no match-map adjudication yet - "
        f"coverage {gate.coverage_count}/{gate.total_rows})"
    )
    lines.append(
        f"Positive hits:        {aggregate.positive_hits}/{aggregate.positive_total} ({positive_pct}%) "
        f"(floor: {aggregate.positive_hit_floor}) [{floor_tag}] "
        "— grounder correctly affirmed claims paper does support"
    )
    lines.append(
        f"False rejection rate: {aggregate.false_rejections}/{aggregate.positive_total} ({false_rejection_pct}%) "
        "— grounder incorrectly refused claims paper does support"
    )
    lines.append("=" * 64)

    if verbose:
        lines.extend(_print_verbose_false_rejections(results))

    lines.append("")
    lines.append(f"Wrote {log_relpath}")
    lines.append(f"Exit {exit_code}")

    print("\n".join(lines))


def _write_log(
    args: argparse.Namespace,
    results: list[PaperRunResult],
    aggregate: MatrixReport,
    gate: MatchMapGate,
    timestamp: datetime,
) -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    filename_ts = timestamp.strftime("%Y%m%dT%H%M%S")
    log_path = LOGS_DIR / f"matrix_{filename_ts}.json"

    papers_json = []
    for result in results:
        entry: dict = {
            "paper_id": result.paper_id,
            "filename": result.filename,
            "status": result.status,
        }
        if result.status == "SKIPPED":
            entry["reason"] = result.reason
        else:
            entry["claims_count"] = result.claims_count
            entry["report"] = result.reports[0].model_dump()
            if len(result.reports) > 1:
                entry["variance"] = _variance_summary(result.reports)
        papers_json.append(entry)

    log_entry = {
        "timestamp": timestamp.isoformat(),
        "args": {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
        "papers": papers_json,
        "aggregate": asdict(aggregate),
        "match_map_gate": asdict(gate),
    }
    log_path.write_text(json.dumps(log_entry, indent=2), encoding="utf-8")
    return log_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prism eval harness matrix runner")
    parser.add_argument("--source", choices=["db", "fixture"], default="db")
    parser.add_argument("--paper", default="all", help="paper_id/filename substring, or 'all'")
    parser.add_argument("--repeat", type=int, default=1, help="matcher runs per paper; reports variance")
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--fixture-dir", type=Path, default=DEFAULT_FIXTURE_DIR)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument(
        "--verbose", action="store_true", help="list each false-rejection (positive-support row the grounder refused)"
    )
    return parser


async def _run(args: argparse.Namespace) -> int:
    matrix_spec: MatrixSpec = load_matrix(args.matrix_path)

    papers = [p for p in matrix_spec.papers if _paper_matches(p, args.paper)]
    if not papers:
        print(f"No papers match --paper {args.paper!r}", file=sys.stderr)
        return 1

    results = [
        await _run_paper(
            paper,
            args.source,
            args.fixture_dir,
            args.repeat,
            matrix_spec.pass_threshold_positive_floor,
        )
        for paper in papers
    ]

    aggregate = _aggregate(results, matrix_spec.pass_threshold_positive_floor)

    golden_ids = {row.id for paper in papers for row in paper.expected_rows}
    gate = _build_match_map_gate(golden_ids, args.match_map_path)

    metric_pass = (
        aggregate.scored_papers > 0
        and aggregate.refusal_rate_valid
        and aggregate.refusal_rate >= matrix_spec.pass_threshold_refusal_rate
    )
    exit_code = 0 if metric_pass and gate.coverage_ok else 1

    timestamp = datetime.now(timezone.utc)
    log_path = _write_log(args, results, aggregate, gate, timestamp)
    log_relpath = log_path.relative_to(Path(__file__).parent.parent)

    _print_report(
        results, aggregate, gate, matrix_spec.pass_threshold_refusal_rate, log_relpath, exit_code, verbose=args.verbose
    )

    return exit_code


def main() -> None:
    args = _build_parser().parse_args()
    sys.exit(asyncio.run(_run(args)))


if __name__ == "__main__":
    from dotenv import load_dotenv

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    load_dotenv()
    main()
