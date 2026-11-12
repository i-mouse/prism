"""CLI 1a: for each of the 106 full-check claims, how many of the 9 saved audits (3 arms x 3 repeats) flagged it.
Read-only, prints and writes text only, zero LLM calls.

Flagged = partially_supported or not_supported (decisions.md 2026-11-11, "Step 1 reading rules", 1a). Counts are per
arm (0-3) and over all 9 audits (0-9), on the RAW label and on the EFFECTIVE status (a grounding-rejected claim counts
as not_supported). Fallback-served audits are counted separately, not removed.

It first reproduces the recorded 2026-11-09 votes with score_full_check's own loaders and vote code. On any mismatch it
prints MISMATCH and exits 1 before printing any count.

Descriptive only. No cut-off is chosen from this data; any cut-off belongs to the step 4 pre-registration.

Usage (from Prism.PythonService):
  uv run python -m eval.step1.flag_counts [--out-dir PATH]
"""
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from eval import score_full_check as sfc
from eval import score_screen
from eval.matrix_loader import load_matrix
from eval.score_replay import (
    DEFAULT_DEV_EVAL_PATH,
    DEFAULT_MATCH_MAP_PATH,
    DEFAULT_RUN1_FIXTURE_DIR,
    resolve_adjudicated_rows,
)
from eval.step1 import common, core

FIRST_LINE = "Descriptive only. No cut-off is chosen from this data."

# Recorded in docs/decisions.md "Full no-regression check result ... - 2026-11-09". Candidates are the applied
# (worst-case) numbers of that entry; B has no fallback-served audit, so as-scored = best case.
EXPECTED: dict[str, dict] = {
    "B": {"fixed": [], "lost": ["P6-R1"], "false_rejections": ["P4-S4"], "golden": (6, 13)},
    "C1": {
        "fixed": ["P4-R2", "P8-R2"], "lost": [],
        "false_rejections": ["P1-S3", "P2-S7", "P9-S4", "P11-S2"], "golden": (7, 12),
    },
    "C2": {
        "fixed": ["P4-R1", "P4-R2", "P7-R1", "P8-R2"], "lost": [],
        "false_rejections": ["P1-S3", "P1-S8", "P8-S7", "P9-S4", "P10-S2", "P12-S4", "P12-S5"], "golden": (9, 10),
    },
}


@dataclass
class LoadedArm:
    arm: common.ArmDef
    dev_dirs: list[Path]
    golden_dirs: list[Path]
    dev_obs: dict
    golden: dict
    dev_config: dict | None
    golden_config: dict | None


def load_arm(
    arm: common.ArmDef, table: dict, rows_r: list, rows_s: list, matrix,
    dev_entries: list, golden_entries: list, invalid: list[str],
) -> LoadedArm:
    dev_dirs = common.full_check_dirs(arm, "dev")
    golden_dirs = common.full_check_dirs(arm, "golden")
    common.ensure_full_check_folders(dev_dirs + golden_dirs, invalid)
    dev_meta = sfc._load_meta(dev_dirs, invalid)
    golden_meta = sfc._load_meta(golden_dirs, invalid)
    common.check_arm_config(arm, [m.config for m in dev_meta], f"{arm.name} dev", invalid)
    common.check_arm_config(arm, [m.config for m in golden_meta], f"{arm.name} golden", invalid)
    dev_config = next((m.config for m in dev_meta if m.config is not None), None)
    golden_config = next((m.config for m in golden_meta if m.config is not None), None)
    if dev_config is not None and golden_config is not None:
        invalid.extend(sfc._config_differences_between(
            f"{arm.name} dev", dev_config, f"{arm.name} golden", golden_config, sfc.CONFIG_KEYS))
    for d in dev_dirs:
        if d.is_dir():
            common.check_claims_present(d, dev_entries, invalid)
            hashes = common.prompt_hashes(d, sorted({p for p, _, _ in dev_entries}))
            if hashes != {common.FLAG_OFF_PROMPT_HASH}:
                invalid.append(f"{d}: prompt hashes {sorted(hashes)}, expected only {common.FLAG_OFF_PROMPT_HASH}")
    for d in golden_dirs:
        if d.is_dir():
            common.check_claims_present(d, golden_entries, invalid)
    dev_obs = sfc._load_dev_arm(dev_dirs, dev_meta, rows_r, rows_s, table, invalid)
    golden = sfc._load_golden_arm(golden_dirs, golden_meta, matrix, table, invalid)
    return LoadedArm(arm, dev_dirs, golden_dirs, dev_obs, golden, dev_config, golden_config)


# --- self-check ----------------------------------------------------------------------------------------

def measured_for(name: str, loaded: dict[str, LoadedArm], rows_s: list, matrix) -> dict:
    """The recorded measures, recomputed with score_full_check's own functions. B alone is compared with itself
    (its as-scored numbers); a candidate against B, using its worst-case (applied) numbers like the recorded table."""
    base = loaded["B"]
    if name == "B":
        dev = sfc._dev_measures(base.dev_obs, base.dev_obs, rows_s)
        gold = sfc._golden_measures(base.golden, base.golden, matrix)
        return {
            "fixed": sorted(dev["D4"]["baseline_as_scored"]), "lost": sorted(dev["D5"]["baseline_as_scored_lost"]),
            "false_rejections": sorted(dev["D6"]["baseline_as_scored"]),
            "golden": (len(gold["D7"]["baseline_refusals_as_scored"]), len(gold["D7"]["baseline_hits_as_scored"])),
        }
    cand = loaded[name]
    dev = sfc._dev_measures(cand.dev_obs, base.dev_obs, rows_s)
    gold = sfc._golden_measures(cand.golden, base.golden, matrix)
    return {
        "fixed": sorted(dev["D4"]["candidate_worst_case"]), "lost": sorted(dev["D5"]["candidate_worst_case_lost"]),
        "false_rejections": sorted(dev["D6"]["candidate_worst_case"]),
        "golden": (len(gold["D7"]["candidate_refusals_worst_case"]), len(gold["D7"]["candidate_hits_worst_case"])),
        "as_scored": {
            "fixed": sorted(dev["D4"]["candidate_as_scored"]), "lost": sorted(dev["D5"]["candidate_as_scored_lost"]),
            "false_rejections": sorted(dev["D6"]["candidate_as_scored"]),
            "golden": (len(gold["D7"]["candidate_refusals_as_scored"]), len(gold["D7"]["candidate_hits_as_scored"])),
        },
    }


def self_check(loaded: dict[str, LoadedArm], rows_s: list, matrix) -> tuple[list[str], list[str], dict]:
    """(report lines, MISMATCH lines, measured per arm)."""
    lines: list[str] = []
    mismatches: list[str] = []
    measured: dict[str, dict] = {}
    for name in ("B", "C1", "C2"):
        got = measured_for(name, loaded, rows_s, matrix)
        measured[name] = got
        want = EXPECTED[name]
        lines.append(
            f"  {name:<3} fixed {len(got['fixed'])}/8 {got['fixed']}; real hits lost {len(got['lost'])}/7 {got['lost']}; "
            f"false rejections {len(got['false_rejections'])}/88 {got['false_rejections']}; "
            f"golden {got['golden'][0]};{got['golden'][1]}"
        )
        for key in ("fixed", "lost", "false_rejections"):
            if got[key] != sorted(want[key]):
                mismatches.append(f"MISMATCH {name} {key}: got {got[key]}, recorded {sorted(want[key])}")
        if tuple(got["golden"]) != tuple(want["golden"]):
            mismatches.append(f"MISMATCH {name} golden refusal-family;positive hits: got {got['golden']}, recorded {want['golden']}")
    return lines, mismatches, measured


# --- per-claim counts ----------------------------------------------------------------------------------

def build_rows(
    universe: list[core.ClaimEntry], loaded: dict[str, LoadedArm], invalid: list[str],
) -> list[dict]:
    cache = common.FixtureCache()
    rows = []
    for entry in universe:
        set_name, paper_id, index = entry.claim_key
        row: dict = {
            "claim": f"{paper_id}#{index}", "set": set_name, "class": entry.claim_class,
            "rows": list(entry.row_ids), "note": entry.note,
        }
        raw_total = eff_total = fallback = 0
        for arm in common.ARMS:
            la = loaded[arm.name]
            dirs = la.dev_dirs if set_name == "dev" else la.golden_dirs
            raws: list[str] = []
            effs: list[str] = []
            for d in dirs:
                read = cache.read(d, paper_id, index, invalid)
                if read is None:
                    continue
                if read.served is None:
                    invalid.append(f"{d}: {paper_id}#{index} lacks audit_model_served")
                    continue
                raws.append(read.raw)
                effs.append(read.effective)
                if score_screen._served_differs(read.served, arm.auditor_model):
                    fallback += 1
            row[f"{arm.name}_raw"] = core.flag_count(raws)
            row[f"{arm.name}_effective"] = core.flag_count(effs)
            raw_total += row[f"{arm.name}_raw"]
            eff_total += row[f"{arm.name}_effective"]
        row["total_raw"] = raw_total
        row["total_effective"] = eff_total
        row["fallback_served"] = fallback
        rows.append(row)
    return rows


# --- rendering -----------------------------------------------------------------------------------------

def render_claim_table(rows: list[dict]) -> list[str]:
    lines = [
        ("Per claim: flagged audits out of 3 per arm and out of 9 in total; RAW = final label, EFFECTIVE = "
        "not_supported if grounding rejected the claim."),
        f"{'class':<16} {'row ids':<22} {'claim':<26} | RAW  B C1 C2 tot | EFF  B C1 C2 tot | fb | note",
    ]
    for r in rows:
        lines.append(
            f"{r['class']:<16} {', '.join(r['rows']):<22} {r['claim']:<26} | "
            f"     {r['B_raw']} {r['C1_raw']:>2} {r['C2_raw']:>2} {r['total_raw']:>3} | "
            f"     {r['B_effective']} {r['C1_effective']:>2} {r['C2_effective']:>2} {r['total_effective']:>3} | "
            f"{r['fallback_served']:>2} | {r['note']}"
        )
    total_fb = sum(r["fallback_served"] for r in rows)
    lines.append("fb = fallback-served audits of the 9 (audit_model_served differs from the arm's auditor). "
                 f"Total over all claims: {total_fb}")
    return lines


def class_histograms(rows: list[dict], key: str, max_count: int) -> dict[str, list[int]]:
    out = {}
    for cls in core.CLASS_ORDER:
        out[cls] = core.histogram([r[key] for r in rows if r["class"] == cls], max_count)
    out["all claims"] = core.histogram([r[key] for r in rows], max_count)
    return out


def render_histograms(rows: list[dict]) -> list[str]:
    lines: list[str] = []
    for basis, basis_label in (("raw", "RAW label"), ("effective", "EFFECTIVE status")):
        for title, key, max_count in (
            ("arm B alone (0-3 of 3 audits)", f"B_{basis}", 3),
            ("all 9 audits (0-9)", f"total_{basis}", 9),
        ):
            lines.append("")
            lines.append(f"Histogram of flag counts by class - {basis_label} - {title}")
            lines.append(f"{'class':<18} {'n':>4} " + " ".join(f"{i:>4}" for i in range(max_count + 1)))
            for cls, hist in class_histograms(rows, key, max_count).items():
                lines.append(f"{cls:<18} {sum(hist):>4} " + " ".join(f"{v:>4}" for v in hist))
    return lines


def render_k_tables(rows: list[dict]) -> list[str]:
    bad = [r for r in rows if r["class"] in core.BAD_CLASSES]
    good = [r for r in rows if r["class"] in core.GOOD_CLASSES]
    lines = [
        "",
        (f"Bad claims = {', '.join(core.BAD_CLASSES)} ({len(bad)}). "
        f"Good claims = {', '.join(core.GOOD_CLASSES)} ({len(good)})."),
    ]
    for basis, basis_label in (("raw", "RAW label"), ("effective", "EFFECTIVE status")):
        for title, key, max_k in (("arm B alone", f"B_{basis}", 3), ("all 9 audits", f"total_{basis}", 9)):
            table = core.flagged_at_least_table([r[key] for r in bad], [r[key] for r in good], max_k)
            lines.append("")
            lines.append(f"Flagged in >= k audits - {basis_label} - {title}")
            lines.append(f"{'k':>3} | {'bad flagged':>16} | {'good flagged':>16}")
            for k, nb, ng in table:
                lines.append(f"{k:>3} | {nb:>4}/{len(bad):<3} {100 * nb / len(bad):>5.1f}% | {ng:>4}/{len(good):<3} {100 * ng / len(good):>5.1f}%")
    return lines


# --- run -----------------------------------------------------------------------------------------------

def run(out_dir: Path) -> int:
    print(FIRST_LINE)
    invalid: list[str] = []
    dev_entries = common.load_claims_file(common.FULL_CHECK_CLAIMS_PATH)
    golden_entries = common.load_claims_file(common.GOLDEN_CLAIMS_PATH)
    if len(dev_entries) != common.EXPECTED_DEV_CLAIMS or len(golden_entries) != common.EXPECTED_GOLDEN_CLAIMS:
        invalid.append(f"claims files hold {len(dev_entries)} dev and {len(golden_entries)} golden claims, "
                       f"expected {common.EXPECTED_DEV_CLAIMS} and {common.EXPECTED_GOLDEN_CLAIMS}")
    setup_errors = score_screen._setup_errors()
    if setup_errors:
        for reason in setup_errors:
            print(f"STOP: {reason}")
        return 1

    rows_r = resolve_adjudicated_rows(DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR, row_type="R")
    rows_s = resolve_adjudicated_rows(DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR, row_type="S")
    sfc._check_s_rows(rows_s, invalid)
    try:
        matrix = load_matrix(sfc.DEFAULT_MATRIX_PATH)
    except ValueError as exc:
        print(f"INVALID: golden matrix: {exc}")
        return 1
    sfc._check_golden_sizes(matrix, invalid)

    loaded: dict[str, LoadedArm] = {}
    for arm in common.ARMS:
        table = sfc.BASELINE_BEST_CASE if arm.name == "B" else sfc.CANDIDATE_WORST_CASE
        loaded[arm.name] = load_arm(arm, table, rows_r, rows_s, matrix, dev_entries, golden_entries, invalid)
    invalid = list(dict.fromkeys(invalid))
    if invalid:
        for reason in invalid:
            print(f"INVALID: {reason}")
        return 1

    check_lines, mismatches, measured = self_check(loaded, rows_s, matrix)
    print("\nSelf-check against the recorded 2026-11-09 votes (score_full_check's own loaders and vote code):")
    for line in check_lines:
        print(line)
    if mismatches:
        for m in mismatches:
            print(m)
        return 1
    print("  self-check OK: all three arms reproduce the recorded numbers")

    universe = core.classify_claims(
        [(rid, obs_list[0].role, ("dev", *obs_list[0].claim_id)) for rid, obs_list in loaded["B"].dev_obs.items()]
        + [(rid, obs_list[0].role, ("golden", *obs_list[0].claim_id))
           for rid, obs_list in loaded["B"].golden["obs"].items() if obs_list[0].claim_id[1] is not None]
    )
    if len(universe) != common.EXPECTED_ALL_CLAIMS:
        print(f"INVALID: {len(universe)} distinct claims, expected {common.EXPECTED_ALL_CLAIMS}")
        return 1
    rows = build_rows(universe, loaded, invalid)
    if invalid:
        for reason in dict.fromkeys(invalid):
            print(f"INVALID: {reason}")
        return 1

    lines = [FIRST_LINE, "", (f"Claims: {len(rows)} (dev {sum(1 for r in rows if r['set'] == 'dev')}, "
                                   f"golden {sum(1 for r in rows if r['set'] == 'golden')}). Arms: B = gemini-3.6-flash medium, "
                                   "C1 = gemini-3.8-flash medium, C2 = gemini-3.8-flash high; 3 repeats each; Vertex."),
             "", "Self-check against the recorded 2026-11-09 votes: OK"]
    lines += check_lines
    lines += [""] + render_claim_table(rows) + render_histograms(rows) + render_k_tables(rows)
    text = "\n".join(lines) + "\n"
    print("\n".join(lines[1:]) + "\n")    # the first line is already printed
    payload = {"first_line": FIRST_LINE, "self_check": measured, "claims": rows}
    for path in common.write_outputs(out_dir, "1a_flag_counts", text, payload):
        print(f"wrote {path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=common.DEFAULT_OUT_DIR)
    args = parser.parse_args()
    sys.exit(run(args.out_dir))


if __name__ == "__main__":
    main()
