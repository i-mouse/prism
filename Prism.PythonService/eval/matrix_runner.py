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

from eval.data_source import read_from_db, read_from_fixture, read_matches_from_fixture
from eval.matrix_loader import MatrixSpec, PaperSpec, load_matrix
from eval.scorer import score
from eval.types import EvalReport

REPO_ROOT = Path(__file__).parent.parent.parent
LOGS_DIR = Path(__file__).parent.parent / "logs" / "eval"
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"
DEFAULT_FIXTURE_DIR = REPO_ROOT / "docs" / "evals" / "fixtures"


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
    refused_by_omission: int
    refused_by_grounding: int
    positive_hits: int
    positive_total: int
    false_rejections: int
    false_rejection_rate: float
    positive_hit_floor: int
    refusal_rate_valid: bool
    scored_papers: int


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
            matches = await match(paper.paper_id, paper.expected_rows, claims)
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
    total_negatives = sum(result.reports[0].total_negatives for result in scored)
    refused_by_label = sum(min(r.refused_by_label for r in result.reports) for result in scored)
    refused_by_omission = sum(min(r.refused_by_omission for r in result.reports) for result in scored)
    refused_by_grounding = sum(min(r.refused_by_grounding for r in result.reports) for result in scored)
    positive_hits = sum(min(r.positive_hits for r in result.reports) for result in scored)
    positive_total = sum(result.reports[0].positive_total for result in scored)
    false_rejections = sum(max(r.false_rejections for r in result.reports) for result in scored)

    refusal_rate = correct_refusals / total_negatives if total_negatives else 0.0
    false_rejection_rate = false_rejections / positive_total if positive_total else 0.0
    refusal_rate_valid = positive_hits >= positive_hit_floor

    return MatrixReport(
        correct_refusals=correct_refusals,
        total_negatives=total_negatives,
        refusal_rate=refusal_rate,
        refused_by_label=refused_by_label,
        refused_by_omission=refused_by_omission,
        refused_by_grounding=refused_by_grounding,
        positive_hits=positive_hits,
        positive_total=positive_total,
        false_rejections=false_rejections,
        false_rejection_rate=false_rejection_rate,
        positive_hit_floor=positive_hit_floor,
        refusal_rate_valid=refusal_rate_valid,
        scored_papers=len(scored),
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
    threshold_pct = round(threshold_refusal_rate * 100)
    refusal_tag = "PASS" if aggregate.refusal_rate >= threshold_refusal_rate else "FAIL"
    positive_pct = round(aggregate.positive_hits / aggregate.positive_total * 100) if aggregate.positive_total else 0
    false_rejection_pct = round(aggregate.false_rejection_rate * 100)
    floor_tag = "OK" if aggregate.refusal_rate_valid else "BELOW FLOOR - mark invalid"

    lines.append("=" * 64)
    lines.append("Prism Eval Results")
    lines.append("=" * 64)
    lines.append(
        f"Refusal rate:         {aggregate.correct_refusals}/{aggregate.total_negatives} ({refusal_pct}%) "
        f"[{refusal_tag} vs {threshold_pct}% threshold] "
        "— grounder correctly refused claims paper doesn't support"
    )
    lines.append(f"  by label:            {aggregate.refused_by_label}")
    lines.append(f"  by omission:         {aggregate.refused_by_omission}")
    lines.append(f"  by grounding reject: {aggregate.refused_by_grounding}")
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

    exit_code = (
        0
        if aggregate.scored_papers > 0
        and aggregate.refusal_rate_valid
        and aggregate.refusal_rate >= matrix_spec.pass_threshold_refusal_rate
        else 1
    )

    timestamp = datetime.now(timezone.utc)
    log_path = _write_log(args, results, aggregate, timestamp)
    log_relpath = log_path.relative_to(Path(__file__).parent.parent)

    _print_report(
        results, aggregate, matrix_spec.pass_threshold_refusal_rate, log_relpath, exit_code, verbose=args.verbose
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
