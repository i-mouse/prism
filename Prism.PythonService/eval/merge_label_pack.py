"""CLI: merges the clean-extraction attempt's K6/K7 AI-judge labels (ChatGPT +
Gemini, blind to each other) with Nitin's blind review labels into one final
labels CSV, per docs/decisions.md, the 2026-10-19 amendments ("K1, K6 and K7
labelling is AI-assisted..." and "no exchange round between the AIs...").

Merge rules:
  AIs agree -> final label = AI label.
    K6 agreement is judged on CLAIM (A) vs NOT-CLAIM (B/C/D). Edge case: both
    say not-claim but with different letters -> still agreed; final label is
    ChatGPT's letter (recorded in the note, since the scorer only cares about
    A vs not-A).
    K7 agreement is judged on the exact label (same/broader/narrower/different).
  Either AI says "unsure", or the AIs disagree -> final label = Nitin's label
  from the review CSV (his "unsure" is kept as "unsure"; the scorer already
  treats K6 unsure as not-claim and K7 unsure as not-same).
  Spot-check: of the 10 agreed items Nitin also blind-labelled (without seeing
  AI labels or which items are agreed vs disagreements), compare his label to
  the AI label at the same level as agreement (K6 claim/not-claim, K7 exact
  label). In K6 his "unsure" folds into the not-claim bucket for this
  comparison, so it CAN match an agreed B/C/D item; in K7 the comparison is
  exact-label, so his "unsure" never equals a real K7 label and always counts
  as a differ. 0-2 differ -> PASS, file is written, agreed items keep the AI
  label regardless of the spot-check result on them. 3+ differ -> FAIL: no
  file is written, the differing item ids are printed, exit non-zero.

Refuses (no file written, no guessing) on: any item missing from --chatgpt,
--gemini or the --labels template; an item in the AI files not in --labels
(or vice versa); a duplicate item_id in any input; an unknown label value; a
blank label in --review for a row that exists there; a --review item_id not
present in --labels; a spot-check pool (agreed items also in --review) whose
size is not exactly 10; a disagreement item missing from --review; any
--labels row that is already non-blank (refuses to clobber existing work);
any path containing "_key".

No LLM or API calls, no network, no git. Plain stdlib (csv/argparse/pathlib)
plus eval.blind_review.sha256_file, matching eval/build_label_pack.py and
eval/score_label_pack.py.

Usage:
  uv run python -m eval.merge_label_pack --mode k6 \\
      --chatgpt docs/evals/clean_labels/k6/ai/k6_chatgpt.csv \\
      --gemini docs/evals/clean_labels/k6/ai/k6_gemini.csv \\
      --review docs/evals/clean_labels/k6/ai/k6_review_nitin.csv \\
      --labels docs/evals/clean_labels/k6/k6_labels.csv
"""
import argparse
import csv
from pathlib import Path

from eval.blind_review import sha256_file

K6_LABELS = {"A", "B", "C", "D", "unsure"}
K7_LABELS = {"same", "broader", "narrower", "different", "unsure"}
MAX_SPOT_CHECK_DIFFER = 2
EXPECTED_SPOT_CHECK_TOTAL = 10


def _refuse_key_path(path: Path) -> None:
    if "_key" in path.parts or "_key" in path.name:
        raise ValueError(f"refusing path containing '_key': {path}")


def read_label_csv(path: Path, allowed: set[str], *, require_labels: bool) -> dict[str, str]:
    """Returns item_id -> label. If require_labels, every row present in the
    file must carry a non-blank, allowed label - a blank label is a refusal,
    not a skip (used for both the AI judge files and the review file: a row
    that exists there but was never filled in is an error, not "not
    reviewed"). The review file legitimately omits most items entirely;
    that's handled by callers via dict.get(item_id), not by this function."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    labels: dict[str, str] = {}
    for row in rows:
        item_id = (row.get("item_id") or "").strip()
        label = (row.get("label") or "").strip()
        if not item_id:
            raise ValueError(f"{path}: row with blank item_id: {row!r}")
        if item_id in labels:
            raise ValueError(f"{path}: duplicate item_id {item_id!r}")
        if not label:
            if require_labels:
                raise ValueError(f"{path}: {item_id}: label is empty")
            continue
        if label not in allowed:
            raise ValueError(f"{path}: {item_id}: label {label!r} not in allowed set {sorted(allowed)}")
        labels[item_id] = label
    return labels


def read_template(path: Path) -> list[str]:
    """Returns the template's item_ids in file order. Refuses if any row
    already carries a non-blank label (never overwrite existing work) or if
    there is a duplicate item_id."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    item_ids: list[str] = []
    seen: set[str] = set()
    non_blank = []
    for row in rows:
        item_id = (row.get("item_id") or "").strip()
        if not item_id:
            raise ValueError(f"{path}: row with blank item_id: {row!r}")
        if item_id in seen:
            raise ValueError(f"{path}: duplicate item_id {item_id!r}")
        seen.add(item_id)
        item_ids.append(item_id)
        if (row.get("label") or "").strip():
            non_blank.append(item_id)
    if non_blank:
        raise ValueError(
            f"refusing to write {path}: already has non-blank label(s) for {sorted(non_blank)}"
        )
    return item_ids


def k6_bucket(label: str) -> str:
    """A -> claim; everything else (B/C/D/unsure) -> notclaim. Used both to
    test AI-AI agreement (unsure is excluded from this call - see merge_item)
    and to compare Nitin's spot-check label against the agreed AI bucket
    (where his "unsure" correctly folds into notclaim, same as the gate)."""
    return "claim" if label == "A" else "notclaim"


def merge_item(mode: str, chatgpt_label: str, gemini_label: str, review_label: str | None) -> dict:
    """Returns {"final_label", "note", "category" ("agreed"|"disagreed")}.
    Raises ValueError if the item is a disagreement and review_label is
    None (missing from the review CSV)."""
    unsure_either = chatgpt_label == "unsure" or gemini_label == "unsure"
    if mode == "k6":
        agree = (not unsure_either) and k6_bucket(chatgpt_label) == k6_bucket(gemini_label)
    else:
        agree = (not unsure_either) and chatgpt_label == gemini_label

    if not agree:
        if review_label is None:
            raise ValueError("disagreement item missing from the review CSV")
        return {"final_label": review_label, "note": "nitin_disagreement", "category": "disagreed"}

    if mode == "k6" and chatgpt_label != gemini_label:
        # agreed-notclaim edge case: same bucket, different letters
        return {
            "final_label": chatgpt_label,
            "note": f"agreed_not_claim chatgpt={chatgpt_label} gemini={gemini_label}",
            "category": "agreed",
            "_edge_case": True,
        }
    return {"final_label": chatgpt_label, "note": "ai_agreed", "category": "agreed"}


def spot_check_differs(mode: str, nitin_label: str, ai_label: str) -> bool:
    if mode == "k6":
        return k6_bucket(nitin_label) != k6_bucket(ai_label)
    return nitin_label != ai_label  # exact level; "unsure" never equals a real K7 label


def merge_pack(
    mode: str,
    chatgpt: dict[str, str],
    gemini: dict[str, str],
    review: dict[str, str],
    item_ids: list[str],
    expected_spot_check_total: int | None = EXPECTED_SPOT_CHECK_TOTAL,
) -> dict:
    """Returns {"rows": [(item_id, label, note), ...], "agreed": int,
    "disagreed": int, "spot_check_total": int, "spot_check_differ": int,
    "spot_check_differ_ids": [...], "spot_check_pass": bool} on success.
    Raises ValueError on any missing/unknown item (no guessing). Pass
    expected_spot_check_total=None to skip the exact-count check (used only
    by tests of unrelated rules, on fixtures too small to carry 10
    spot-checks); the real CLI always enforces the default of 10."""
    chatgpt_ids, gemini_ids, template_ids = set(chatgpt), set(gemini), set(item_ids)
    review_ids = set(review)
    problems = []
    if chatgpt_ids != template_ids:
        problems.append(f"chatgpt vs labels template item_id mismatch: "
                         f"only in chatgpt={sorted(chatgpt_ids - template_ids)}, "
                         f"only in template={sorted(template_ids - chatgpt_ids)}")
    if gemini_ids != template_ids:
        problems.append(f"gemini vs labels template item_id mismatch: "
                         f"only in gemini={sorted(gemini_ids - template_ids)}, "
                         f"only in template={sorted(template_ids - gemini_ids)}")
    if not review_ids <= template_ids:
        problems.append(f"review item_id(s) not in labels template: {sorted(review_ids - template_ids)}")
    if problems:
        raise ValueError("; ".join(problems))

    rows = []
    agreed = disagreed = 0
    spot_check_total = spot_check_differ = 0
    spot_check_differ_ids: list[str] = []

    for item_id in item_ids:
        merged = merge_item(mode, chatgpt[item_id], gemini[item_id], review.get(item_id))
        rows.append((item_id, merged["final_label"], merged["note"]))
        if merged["category"] == "disagreed":
            disagreed += 1
            continue
        agreed += 1
        if item_id in review:
            spot_check_total += 1
            ai_label_for_compare = chatgpt[item_id]  # == gemini[item_id] unless the k6 edge case, both notclaim bucket
            if spot_check_differs(mode, review[item_id], ai_label_for_compare):
                spot_check_differ += 1
                spot_check_differ_ids.append(item_id)

    if expected_spot_check_total is not None and spot_check_total != expected_spot_check_total:
        raise ValueError(
            f"spot-check pool has {spot_check_total} item(s) (agreed items also in --review), "
            f"expected exactly {expected_spot_check_total}"
        )

    return {
        "rows": rows,
        "agreed": agreed,
        "disagreed": disagreed,
        "spot_check_total": spot_check_total,
        "spot_check_differ": spot_check_differ,
        "spot_check_differ_ids": spot_check_differ_ids,
        "spot_check_pass": spot_check_differ <= MAX_SPOT_CHECK_DIFFER,
    }


def write_labels_csv(path: Path, rows: list[tuple[str, str, str]]) -> None:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["item_id", "label", "note"])
        for row in rows:
            writer.writerow(row)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["k6", "k7"], required=True)
    parser.add_argument("--chatgpt", type=Path, required=True)
    parser.add_argument("--gemini", type=Path, required=True)
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--labels", type=Path, required=True, help="blank template to fill in place")
    return parser


def main() -> None:
    args = _build_parser().parse_args()
    for path in (args.chatgpt, args.gemini, args.review, args.labels):
        _refuse_key_path(path)

    allowed = K6_LABELS if args.mode == "k6" else K7_LABELS
    chatgpt = read_label_csv(args.chatgpt, allowed, require_labels=True)
    gemini = read_label_csv(args.gemini, allowed, require_labels=True)
    review = read_label_csv(args.review, allowed, require_labels=True)
    item_ids = read_template(args.labels)

    result = merge_pack(args.mode, chatgpt, gemini, review, item_ids)

    total = len(item_ids)
    spot_label = f"{result['spot_check_differ']} of {result['spot_check_total']} differ"
    verdict = "PASS" if result["spot_check_pass"] else "FAIL"
    print(f"pack: {args.mode}")
    print(f"total items: {total}")
    print(f"agreed: {result['agreed']}")
    print(f"disagreed: {result['disagreed']}")
    print(f"spot-check: {spot_label}, {verdict}")

    if not result["spot_check_pass"]:
        print("spot-check FAILED - Nitin must label every item himself. Differing item ids:")
        for item_id in result["spot_check_differ_ids"]:
            print(f"  {item_id}")
        raise SystemExit("refusing to write final labels: spot-check FAILED")

    write_labels_csv(args.labels, result["rows"])
    print(f"output path: {args.labels}")
    print(f"output sha256: {sha256_file(args.labels)}")


if __name__ == "__main__":
    main()
