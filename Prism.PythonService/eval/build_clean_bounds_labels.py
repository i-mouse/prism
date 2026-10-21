"""CLI: builds the clean-extraction attempt's K6/K7 worst-case/best-case bound
label CSVs from the AI judges' labels, per docs/decisions.md, "Clean-extraction
attempt: spot-check result, diagnostic, bounded scoring - 2026-10-20".

Unlike eval/merge_label_pack.py (which sends every AI disagreement to Nitin for
a single final label), this script resolves nothing: AI-agreed items take the
AI label in both bound files; AI-disagreed items (including either AI
"unsure") get a fixed worst-case label in the low file and a fixed best-case
label in the high file. Nobody adjudicates disagreements here, and no review
file is read.

Merge rules:
  AIs agree -> final label = AI label in BOTH the low and the high file.
    K6 agreement is judged on CLAIM (A) vs NOT-CLAIM (B/C/D). Edge case: both
    say not-claim but with different letters -> still agreed; final label is
    ChatGPT's letter (recorded in the note), same as eval/merge_label_pack.py.
    K7 agreement is judged on the exact label (same/broader/narrower/different).
  Either AI says "unsure", or the AIs disagree -> nobody decides:
    low (worst-case) file: K6 label "unsure" (buckets as not-claim), K7 label
      "different"; note "ai_disagreed_worst".
    high (best-case) file: K6 label "A", K7 label "same"; note
      "ai_disagreed_best".

Refuses (no file written, no guessing) on: any item missing from --chatgpt or
--gemini, or present there but not in --template (or vice versa); a duplicate
item_id in any input; an unknown label value; any path containing "_key".

No LLM or API calls, no network, no git. Reuses eval.merge_label_pack's I/O
and validation helpers (read_label_csv, read_template, write_labels_csv,
k6_bucket, _refuse_key_path) and eval.blind_review.sha256_file.

Usage:
  uv run python -m eval.build_clean_bounds_labels --mode k6 \\
      --chatgpt docs/evals/clean_labels/k6/ai/k6_chatgpt.csv \\
      --gemini docs/evals/clean_labels/k6/ai/k6_gemini.csv \\
      --template docs/evals/clean_labels/k6/k6_labels.csv \\
      --low-out docs/evals/clean_labels/k6/k6_labels_low.csv \\
      --high-out docs/evals/clean_labels/k6/k6_labels_high.csv
"""
import argparse
from pathlib import Path

from eval.blind_review import sha256_file
from eval.merge_label_pack import (
    K6_LABELS,
    K7_LABELS,
    _refuse_key_path,
    k6_bucket,
    read_label_csv,
    read_template,
    write_labels_csv,
)

WORST_LABEL = {"k6": "unsure", "k7": "different"}
BEST_LABEL = {"k6": "A", "k7": "same"}


def merge_item_bounds(mode: str, chatgpt_label: str, gemini_label: str) -> dict:
    """Returns {"low_label", "high_label", "low_note", "high_note",
    "category" ("agreed"|"disagreed")}. Never raises on disagreement -
    unlike merge_label_pack's merge_item, there is no review label to fall
    back to; a disagreement simply gets the fixed worst/best labels for its
    bounds."""
    unsure_either = chatgpt_label == "unsure" or gemini_label == "unsure"
    if mode == "k6":
        agree = (not unsure_either) and k6_bucket(chatgpt_label) == k6_bucket(gemini_label)
    else:
        agree = (not unsure_either) and chatgpt_label == gemini_label

    if not agree:
        return {
            "low_label": WORST_LABEL[mode], "high_label": BEST_LABEL[mode],
            "low_note": "ai_disagreed_worst", "high_note": "ai_disagreed_best",
            "category": "disagreed",
        }

    if mode == "k6" and chatgpt_label != gemini_label:
        # agreed-notclaim edge case: same bucket, different letters
        note = f"agreed_not_claim chatgpt={chatgpt_label} gemini={gemini_label}"
        return {"low_label": chatgpt_label, "high_label": chatgpt_label,
                "low_note": note, "high_note": note, "category": "agreed"}
    return {"low_label": chatgpt_label, "high_label": chatgpt_label,
            "low_note": "ai_agreed", "high_note": "ai_agreed", "category": "agreed"}


def build_bounds_pack(
    mode: str, chatgpt: dict[str, str], gemini: dict[str, str], item_ids: list[str],
) -> dict:
    """Returns {"low_rows": [(item_id, label, note), ...], "high_rows": [...],
    "agreed": int, "disagreed": int}. Raises ValueError on any missing/unknown
    item (no guessing)."""
    chatgpt_ids, gemini_ids, template_ids = set(chatgpt), set(gemini), set(item_ids)
    problems = []
    if chatgpt_ids != template_ids:
        problems.append(f"chatgpt vs labels template item_id mismatch: "
                         f"only in chatgpt={sorted(chatgpt_ids - template_ids)}, "
                         f"only in template={sorted(template_ids - chatgpt_ids)}")
    if gemini_ids != template_ids:
        problems.append(f"gemini vs labels template item_id mismatch: "
                         f"only in gemini={sorted(gemini_ids - template_ids)}, "
                         f"only in template={sorted(template_ids - gemini_ids)}")
    if problems:
        raise ValueError("; ".join(problems))

    low_rows = []
    high_rows = []
    agreed = disagreed = 0
    for item_id in item_ids:
        merged = merge_item_bounds(mode, chatgpt[item_id], gemini[item_id])
        low_rows.append((item_id, merged["low_label"], merged["low_note"]))
        high_rows.append((item_id, merged["high_label"], merged["high_note"]))
        if merged["category"] == "disagreed":
            disagreed += 1
        else:
            agreed += 1

    return {"low_rows": low_rows, "high_rows": high_rows, "agreed": agreed, "disagreed": disagreed}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["k6", "k7"], required=True)
    parser.add_argument("--chatgpt", type=Path, required=True)
    parser.add_argument("--gemini", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True, help="blank labels template, read-only")
    parser.add_argument("--low-out", type=Path, required=True)
    parser.add_argument("--high-out", type=Path, required=True)
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    for path in (args.chatgpt, args.gemini, args.template, args.low_out, args.high_out):
        _refuse_key_path(path)

    allowed = K6_LABELS if args.mode == "k6" else K7_LABELS
    chatgpt = read_label_csv(args.chatgpt, allowed, require_labels=True)
    gemini = read_label_csv(args.gemini, allowed, require_labels=True)
    item_ids = read_template(args.template)

    result = build_bounds_pack(args.mode, chatgpt, gemini, item_ids)

    write_labels_csv(args.low_out, result["low_rows"])
    write_labels_csv(args.high_out, result["high_rows"])

    for path in (args.low_out, args.high_out):
        print(f"{path} rows={len(item_ids)} sha256={sha256_file(path)}")


if __name__ == "__main__":
    main()
