"""CLI entry point for the Prism eval harness: matrix_eval.json runner.

Loads the claim-support matrix, fetches actual claims per paper (Postgres
or committed JSON fixtures), matches expected rows to actual claims via
the LLM-as-judge matcher, scores each paper, aggregates into a single
run, prints a report, writes a JSON log, and exits 0/1 for CI gating.
"""
import argparse
import asyncio
import json
import statistics
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from eval.data_source import read_from_db, read_from_fixture
from eval.matcher import match
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
    positive_hits: int
    positive_total: int
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
    try:
        if source == "db":
            claims = await read_from_db(paper.filename)
        else:
            claims = read_from_fixture(fixture_dir / f"{paper.paper_id}.json")
    except Exception as exc:
        return PaperRunResult(
            paper_id=paper.paper_id,
            filename=paper.filename,
            status="SKIPPED",
            reason=f"read failed: {exc}",
        )

    if not claims:
        reason = "no DB data" if source == "db" else "fixture missing"
        return PaperRunResult(paper_id=paper.paper_id, filename=paper.filename, status="SKIPPED", reason=reason)

    reports: list[EvalReport] = []
    for _ in range(repeat):
        matches = await match(paper.paper_id, paper.expected_rows, claims)
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

    # Worst-case across --repeat runs: each metric is independently minimized
    # per paper, then summed. A partially-invalid variance run must fail the
    # gate, so we never let a lucky run mask a bad one.
    correct_refusals = sum(min(r.correct_refusals for r in result.reports) for result in scored)
    total_negatives = sum(result.reports[0].total_negatives for result in scored)
    refused_by_label = sum(min(r.refused_by_label for r in result.reports) for result in scored)
    refused_by_omission = sum(min(r.refused_by_omission for r in result.reports) for result in scored)
    positive_hits = sum(min(r.positive_hits for r in result.reports) for result in scored)
    positive_total = sum(result.reports[0].positive_total for result in scored)

    refusal_rate = correct_refusals / total_negatives if total_negatives else 0.0
    refusal_rate_valid = positive_hits >= positive_hit_floor

    return MatrixReport(
        correct_refusals=correct_refusals,
        total_negatives=total_negatives,
        refusal_rate=refusal_rate,
        refused_by_label=refused_by_label,
        refused_by_omission=refused_by_omission,
        positive_hits=positive_hits,
        positive_total=positive_total,
        positive_hit_floor=positive_hit_floor,
        refusal_rate_valid=refusal_rate_valid,
        scored_papers=len(scored),
    )


def _print_report(
    results: list[PaperRunResult],
    aggregate: MatrixReport,
    threshold_refusal_rate: float,
    log_relpath: Path,
    exit_code: int,
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

    pct = round(aggregate.refusal_rate * 100)
    threshold_pct = round(threshold_refusal_rate * 100)
    refusal_tag = "PASS" if aggregate.refusal_rate >= threshold_refusal_rate else "FAIL"
    lines.append(
        f"Refusal rate:   {aggregate.correct_refusals}/{aggregate.total_negatives}  ({pct}%)   "
        f"[{refusal_tag} vs {threshold_pct}% threshold]"
    )
    lines.append(f"  by label:        {aggregate.refused_by_label}")
    lines.append(f"  by omission:     {aggregate.refused_by_omission}")

    floor_tag = "OK" if aggregate.refusal_rate_valid else "BELOW FLOOR - mark invalid"
    lines.append(
        f"Positive hits:  {aggregate.positive_hits}/{aggregate.positive_total}  "
        f"(floor: {aggregate.positive_hit_floor})   [{floor_tag}]"
    )
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

    _print_report(results, aggregate, matrix_spec.pass_threshold_refusal_rate, log_relpath, exit_code)

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
