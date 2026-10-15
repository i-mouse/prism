"""Experiment 3 pre-check C: union of past runs.

For the 13 Experiment-2 target rows and the 13 in-scope matched rows, marks
whether each was found in run 1 (docs/evals/dev_match_map.json) and in each
of the 3 Experiment-2 Stage A runs
(docs/evals/fixtures/dev/exp2/adjudication_template.json: control_r1,
treatment_r1, treatment_r2), and whether it was found in ANY of the 4 runs.

ROW_ID_TO_SHAPE and REPLAYED_PAPER_SUBSTRINGS below are copied verbatim from
Prism.PythonService/eval/score_exp2.py:53-59 and :70-73 (read, not edited;
eval/ is scoring/pre-check tooling, not the production extraction pipeline).
Read-only, no LLM calls.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib

# Verbatim copy: Prism.PythonService/eval/score_exp2.py:53-59
ROW_ID_TO_SHAPE = {
    "P7-R2": "E1", "P2-R1": "E1", "P1-R2": "E1", "P12-R1": "E1",
    "P2-R3": "E2", "P2-R4": "E2", "P9-R1": "E2",
    "P4-R3": "E3", "P3-R1": "E3", "P5-R3": "E3", "P8-R3": "E3",
    "P11-R1": "E4",
    "P11-R3": "E5",
}

# Verbatim copy: Prism.PythonService/eval/score_exp2.py:70-73
REPLAYED_PAPER_SUBSTRINGS = (
    "2610.11519", "2610.11132", "2610.11135", "2610.10871", "2610.11291",
    "2610.10590", "2610.12124", "2610.12375", "2610.12114", "2610.12168",
)

R_ROW_RE = re.compile(r"^P\d+-R\d+$")


def in_replay_scope(filename: str) -> bool:
    return any(s in filename for s in REPLAYED_PAPER_SUBSTRINGS)


def main():
    dev_eval = lib.load_dev_eval()
    row_filename = {row["id"]: filename for filename, row in lib.iter_dev_rows(dev_eval)}

    match_map = json.loads(lib.DEV_MATCH_MAP_PATH.read_text(encoding="utf-8"))
    match_rows = match_map["rows"]

    target_ids = set(ROW_ID_TO_SHAPE.keys())

    matched_ids = set()
    for rid, entry in match_rows.items():
        if not R_ROW_RE.match(rid):
            continue
        if rid in target_ids:
            continue
        found_run1 = (entry.get("confirmed_no_match") is False) and (entry.get("claim_fingerprint") is not None)
        if not found_run1:
            continue
        filename = row_filename.get(rid)
        if filename is None or not in_replay_scope(filename):
            continue
        matched_ids.add(rid)

    print("=== Check C: union of past runs ===")
    print(f"target_ids count: {len(target_ids)} (expected 13)")
    print(f"matched_ids count: {len(matched_ids)} (expected 13)")
    if len(target_ids) != 13 or len(matched_ids) != 13:
        print("WARNING: counts do not match the pre-registered 13/13 - reporting as computed, not adjusted.")
    print()

    adjudication = json.loads(lib.ADJUDICATION_TEMPLATE_PATH.read_text(encoding="utf-8"))
    found_in_run: dict[tuple[str, str], bool] = {}
    for entry in adjudication:
        key = (entry["row_id"], entry["run"])
        found_in_run[key] = entry["matched_claim_index"] is not None

    def found_run1(rid: str) -> bool:
        entry = match_rows.get(rid, {})
        return (entry.get("confirmed_no_match") is False) and (entry.get("claim_fingerprint") is not None)

    runs = ("control_r1", "treatment_r1", "treatment_r2")

    def row_report(rid: str) -> tuple[bool, bool, bool, bool, bool]:
        r1 = found_run1(rid)
        per_run = [found_in_run.get((rid, run), False) for run in runs]
        any_found = r1 or any(per_run)
        return (r1, per_run[0], per_run[1], per_run[2], any_found)

    def print_table(label: str, ids: set[str]):
        print(f"--- {label} ({len(ids)} rows) ---")
        print(f"{'row_id':10s} {'run1':>5s} {'ctrl_r1':>8s} {'treat_r1':>9s} {'treat_r2':>9s} {'any':>5s}")
        any_count = 0
        for rid in sorted(ids):
            r1, c1, t1, t2, any_found = row_report(rid)
            if any_found:
                any_count += 1
            print(f"{rid:10s} {str(r1):>5s} {str(c1):>8s} {str(t1):>9s} {str(t2):>9s} {str(any_found):>5s}")
        print(f"{label}: found in ANY of the 4 runs = {any_count}/{len(ids)}")
        print()

    print_table("target rows", target_ids)
    print_table("matched rows", matched_ids)


if __name__ == "__main__":
    main()
