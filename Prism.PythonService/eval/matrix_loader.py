"""Loads docs/evals/matrix_eval.json into typed objects for the runner.

Pure function module: reads one JSON file and returns dataclasses. No LLM
calls, no DB access, no network I/O.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from eval.types import ExpectedRow

DEFAULT_PASS_THRESHOLD_REFUSAL_RATE = 0.70
DEFAULT_PASS_THRESHOLD_POSITIVE_FLOOR = 10


@dataclass
class PaperSpec:
    """One paper's worth of ground-truth rows from matrix_eval.json."""

    paper_id: str
    filename: str
    title: str
    expected_rows: list[ExpectedRow]


@dataclass
class MatrixSpec:
    """Parsed matrix_eval.json: all papers plus the regression-gate thresholds."""

    papers: list[PaperSpec]
    pass_threshold_refusal_rate: float
    pass_threshold_positive_floor: int


def load_matrix(path: str | Path) -> MatrixSpec:
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ValueError(f"Failed to load matrix eval file {path}: {exc}") from exc

    if not isinstance(raw, dict) or "papers" not in raw:
        raise ValueError(f"Malformed matrix eval file {path}: missing 'papers' key")

    pass_threshold = raw.get("metadata", {}).get("pass_threshold")
    if pass_threshold is None:
        print(
            f"[matrix_loader] {path}: no metadata.pass_threshold found, using defaults "
            f"refusal_rate={DEFAULT_PASS_THRESHOLD_REFUSAL_RATE} "
            f"positive_hit_floor={DEFAULT_PASS_THRESHOLD_POSITIVE_FLOOR}"
        )
        refusal_rate = DEFAULT_PASS_THRESHOLD_REFUSAL_RATE
        positive_floor = DEFAULT_PASS_THRESHOLD_POSITIVE_FLOOR
    else:
        refusal_rate = pass_threshold.get("refusal_rate", DEFAULT_PASS_THRESHOLD_REFUSAL_RATE)
        positive_floor = pass_threshold.get("positive_hit_floor", DEFAULT_PASS_THRESHOLD_POSITIVE_FLOOR)

    try:
        papers = [
            PaperSpec(
                paper_id=paper_raw["paper_id"],
                filename=paper_raw["filename"],
                title=paper_raw.get("title", ""),
                expected_rows=[
                    ExpectedRow(
                        id=row["id"],
                        expected_label=row["expected_label"],
                        grounding_negative=row["grounding_negative"],
                        claim_summary=row.get("claim_summary", ""),
                        claim_text_verbatim=row.get("claim_text_verbatim", ""),
                    )
                    for row in paper_raw["expected_matrix"]
                ],
            )
            for paper_raw in raw["papers"]
        ]
    except (KeyError, TypeError, ValidationError) as exc:
        raise ValueError(f"Malformed matrix eval file {path}: {exc}") from exc

    return MatrixSpec(
        papers=papers,
        pass_threshold_refusal_rate=refusal_rate,
        pass_threshold_positive_floor=positive_floor,
    )
