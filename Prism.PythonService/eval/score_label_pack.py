"""CLI: scores one hand-filled K6 or K7 label-pack CSV (eval/build_label_pack.py)
against its hidden key (docs/decisions.md, "Clean-extraction attempt: K6/K7
labelling method, caching dropped, K4 path - 2026-10-19").

  K6  precision with unsure counted as not-claim (GATE, >= 0.70) and with
      unsure counted as claim (report only); per-label counts; NOT_FOUND
      count; PASS/FAIL.
  K7  count of items not labelled "same" (unsure counts as not-same);
      PASS if <= 1; per-label counts.

Refuses to score if any label is empty or not in the mode's allowed set.
No LLM calls, no network.

Usage:
  uv run python -m eval.score_label_pack --mode k6 \\
      --labels docs/evals/clean_k6k7_pack/k6/k6_labels.csv \\
      --key docs/evals/clean_k6k7_pack/k6/_key/k6_key.json
"""
import argparse
import csv
import json
from pathlib import Path

from eval.blind_review import sha256_file

K6_LABELS = {"A", "B", "C", "D", "unsure"}
K7_LABELS = {"same", "broader", "narrower", "different", "unsure"}
K6_MIN_PRECISION = 0.70
K7_MAX_NOT_SAME = 1


def load_labels(labels_path: Path, allowed: set[str]) -> tuple[dict[str, str], list[str]]:
    """Returns (item_id -> label, errors). An error is recorded for a blank,
    missing, or out-of-set label; such rows are excluded from the returned
    mapping."""
    with open(labels_path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    labels: dict[str, str] = {}
    errors: list[str] = []
    for row in rows:
        item_id = row.get("item_id", "").strip()
        label = (row.get("label") or "").strip()
        if not item_id:
            errors.append(f"row with blank item_id: {row!r}")
            continue
        if not label:
            errors.append(f"{item_id}: label is empty")
            continue
        if label not in allowed:
            errors.append(f"{item_id}: label {label!r} not in allowed set {sorted(allowed)}")
            continue
        labels[item_id] = label
    return labels, errors


def validate_against_key(labels: dict[str, str], key_item_ids: list[str], errors: list[str]) -> list[str]:
    """Every key item must have a labelled row. Returns the (possibly
    extended) errors list."""
    errors = list(errors)
    missing = [item_id for item_id in key_item_ids if item_id not in labels]
    for item_id in missing:
        errors.append(f"{item_id}: no labelled row in the labels CSV")
    return errors


def score_k6(labels: dict[str, str], key: dict[str, dict]) -> dict:
    n = len(key)
    counts = {label: 0 for label in K6_LABELS}
    for item_id in key:
        counts[labels[item_id]] += 1
    not_found_count = sum(1 for v in key.values() if v.get("not_found"))
    claims = counts["A"]
    precision_unsure_not_claim = claims / n if n else None
    precision_unsure_claim = (claims + counts["unsure"]) / n if n else None
    return {
        "mode": "k6",
        "n": n,
        "counts": counts,
        "not_found_count": not_found_count,
        "precision_unsure_not_claim": precision_unsure_not_claim,
        "precision_unsure_claim": precision_unsure_claim,
        "pass": n > 0 and precision_unsure_not_claim is not None and precision_unsure_not_claim >= K6_MIN_PRECISION,
    }


def score_k7(labels: dict[str, str], key: dict[str, dict]) -> dict:
    n = len(key)
    counts = {label: 0 for label in K7_LABELS}
    for item_id in key:
        counts[labels[item_id]] += 1
    not_same_count = n - counts["same"]
    return {
        "mode": "k7",
        "n": n,
        "counts": counts,
        "not_same_count": not_same_count,
        "pass": n > 0 and not_same_count <= K7_MAX_NOT_SAME,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["k6", "k7"], required=True)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--output-path", type=Path, default=None)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    print(f"labels sha256={sha256_file(args.labels)}")

    key_doc = json.loads(args.key.read_text(encoding="utf-8"))
    key_items = key_doc["items"]
    allowed = K6_LABELS if args.mode == "k6" else K7_LABELS

    labels, errors = load_labels(args.labels, allowed)
    errors = validate_against_key(labels, list(key_items.keys()), errors)
    if errors:
        for err in errors:
            print(f"ERROR: {err}")
        raise SystemExit(f"refusing to score: {len(errors)} invalid/missing label(s)")

    result = score_k6(labels, key_items) if args.mode == "k6" else score_k7(labels, key_items)
    result["labels_sha256"] = sha256_file(args.labels)
    print(json.dumps(result, indent=2))

    output_path = args.output_path or (args.labels.parent / f"{args.mode}_score.json")
    output_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
