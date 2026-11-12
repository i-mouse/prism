"""CLI 1b: run-to-run noise of saved no-change groups, and the tolerance T. Read-only, zero LLM calls.

A no-change group = repeats with the same auditor model, thinking level, backend, prompt hash, flags, grounding model
and claims file (decisions.md 2026-11-11, "Step 1 reading rules", 1b). Spread = highest minus lowest count across the
repeats of one group. T = the largest spread in non-void groups that use the product auditor (gemini-3.6-flash, flags
off) over four counts: refusal-row claims flagged (RAW), S-row false rejections (EFFECTIVE), golden refusal-family,
golden positive hits; capped at 3 with the measured value printed beside it. Void groups, gemini-3.8-flash groups and
the other groups listed below are printed in a second table and never set T.

The group list is explicit (below). Counts that a group's claims file cannot support print "n/a" (the 18-claim groups
hold no S rows and no golden rows).

Usage (from Prism.PythonService):
  uv run python -m eval.step1.noise [--out-dir PATH]
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
    row_details,
)
from eval.step1 import common, core

COUNT_KEYS = ("refusal", "s_false_rejections", "golden_refusal_family", "golden_positive_hits")
COUNT_LABELS = {
    "refusal": "refusal-row claims flagged (RAW)",
    "s_false_rejections": "S-row false rejections (EFFECTIVE)",
    "golden_refusal_family": "golden refusal-family",
    "golden_positive_hits": "golden positive hits",
}
SCREEN_VOID = "screen void: V3 voided arm 1 and V4 voids the whole screen (decisions.md 2026-11-07)"


@dataclass(frozen=True)
class Group:
    name: str
    dirs: tuple[Path, ...]
    kind: str                       # "dev84" | "golden22" | "r18"
    claims_path: Path
    arm: common.ArmDef | None       # None = the folders carry no run_config
    config_note: str
    void: bool
    void_reason: str
    for_t: bool                     # True = may set T (non-void, product auditor, flags off); a problem is fatal
    beside_reason: str              # why it is printed beside T when for_t is False (a problem is only a note)


def _dirs(base: Path, pattern: str, n: int) -> tuple[Path, ...]:
    return tuple(base / pattern.format(n=i) for i in range(1, n + 1))


def groups() -> list[Group]:
    b, c1, c2 = common.ARM_B, common.ARM_C1, common.ARM_C2
    result = [
        Group("full check B dev (gemini-3.6-flash medium, Vertex)", tuple(common.full_check_dirs(b, "dev")), "dev84",
              common.FULL_CHECK_CLAIMS_PATH, b, "run_config", False, "", True, ""),
        Group("full check B golden (gemini-3.6-flash medium, Vertex)", tuple(common.full_check_dirs(b, "golden")),
              "golden22", common.GOLDEN_CLAIMS_PATH, b, "run_config", False, "", True, ""),
    ]
    for arm in (c1, c2):
        for set_name, kind, claims in (("dev", "dev84", common.FULL_CHECK_CLAIMS_PATH),
                                       ("golden", "golden22", common.GOLDEN_CLAIMS_PATH)):
            result.append(Group(
                f"full check {arm.name} {set_name} ({arm.auditor_model} {arm.thinking_level}, Vertex)",
                tuple(common.full_check_dirs(arm, set_name)), kind, claims, arm, "run_config", False, "", False,
                "gemini-3.8-flash is not the product auditor",
            ))
    for arm in (b, c1, c2):
        result.append(Group(
            f"screen {arm.name} ({arm.auditor_model} {arm.thinking_level}, Vertex, 18 claims)",
            tuple(common.screen_dirs(arm)), "r18", common.STAGE_A_CLAIMS_PATH, arm, "run_config", True, SCREEN_VOID,
            False, "void",
        ))
    dev = common.DEV_FIXTURE_DIR
    result.append(Group(
        "exp1 medium (gemini-3.6-flash medium, AI Studio, 18 claims)", _dirs(dev, "exp1_medium_{n}", 2), "r18",
        common.STAGE_A_CLAIMS_PATH, None, "no run_config", False, "", False,
        "2 repeats, no run_config: backend and grounding model not recorded (open question 1: default = not used)",
    ))
    result.append(Group(
        "exp1 high (gemini-3.6-flash high, AI Studio, 18 claims)", _dirs(dev, "exp1_high_{n}", 3), "r18",
        common.STAGE_A_CLAIMS_PATH, None, "no run_config", False, "", False,
        "thinking high is not the product setting (medium) (open question 2: default = not used)",
    ))
    result.append(Group(
        "A1 scope check (gemini-3.6-flash medium, flag ON, 18 claims)",
        _dirs(common.SCRATCH_DIR / "a1_output_2026-10-28", "exp1_medium_scope_{n}", 3), "r18",
        common.STAGE_A_CLAIMS_PATH, None, "run_config present, scope check flag ON", False, "", False,
        "scope-check flag is ON, so not a flags-off group",
    ))
    return result


# --- measuring one group -------------------------------------------------------------------------------

def measure_group(group: Group, rows_r: list, rows_s: list, matrix) -> dict:
    invalid: list[str] = []
    dirs = list(group.dirs)
    result: dict = {
        "name": group.name, "kind": group.kind, "void": group.void, "void_reason": group.void_reason,
        "for_t": group.for_t, "beside_reason": group.beside_reason, "dirs": [str(d) for d in dirs],
        "counts": {k: None for k in COUNT_KEYS}, "spread": {k: None for k in COUNT_KEYS},
        "changed": None, "config": group.config_note, "prompt_hashes": [], "invalid": invalid, "skipped": None,
    }
    missing = [d for d in dirs if not d.is_dir()]
    if missing:
        text = "folder missing: " + "; ".join(str(d) for d in missing)
        if group.for_t:
            invalid.append(text)
        else:
            result["skipped"] = text
        return result
    if group.for_t:
        common.ensure_full_check_folders(dirs, invalid)

    entries = common.load_claims_file(group.claims_path)
    for d in dirs:
        common.check_claims_present(d, entries, invalid)
    papers = sorted({p for p, _, _ in entries})
    hashes = sorted({h for d in dirs for h in common.prompt_hashes(d, papers)})
    result["prompt_hashes"] = hashes
    if len(hashes) != 1:
        invalid.append(f"{group.name}: the repeats carry different prompt hashes {hashes}")
    elif group.for_t and group.kind != "golden22" and hashes[0] != common.FLAG_OFF_PROMPT_HASH:
        # (golden fixtures keep the base golden run's header, so only "identical across repeats" is required there)
        invalid.append(f"{group.name}: prompt hash {hashes[0]}, expected the flag-off hash {common.FLAG_OFF_PROMPT_HASH}")

    metas = None
    if group.arm is not None:
        metas = sfc._load_meta(dirs, invalid)         # run_config equal across the repeats, status OK
        common.check_arm_config(group.arm, [m.config for m in metas], group.name, invalid)
        first = next((m.config for m in metas if m.config is not None), None)
        if first is not None:
            result["config"] = (
                f"backend {first.get('backend')}, auditor {first.get('auditor_model')}, thinking {first.get('thinking_level')}, "
                f"grounding {first.get('other_models', {}).get('grounding_primary')} / "
                f"{first.get('other_models', {}).get('grounding_fallback')}, structurer "
                f"{first.get('other_models', {}).get('structurer')}"
            )
    else:
        configs = [score_screen._load_run_config(d, invalid) for d in dirs]
        if all(c is not None for c in configs):
            invalid.extend(score_screen._config_differences(dirs, configs))
        first = next((c for c in configs if isinstance(c, dict)), None)
        result["config"] = "default (no run_config)" if first is None else f"run_config {first}"

    counts = result["counts"]
    if group.kind in ("dev84", "r18"):
        inv, labels, _, _ = score_screen.collect(rows_r, dirs)
        invalid.extend(inv)
        if not inv:
            counts["refusal"] = [core.flag_count(labels[rid][i] for rid in labels) for i in range(len(dirs))]
    if group.kind == "dev84":
        matched_s = [r for r in rows_s if r.claim_index is not None]
        s_counts = []
        for d in dirs:
            details = row_details(matched_s, d)
            statuses = [details[r.row_id] for r in matched_s]
            if any(s is None for s in statuses):
                invalid.append(f"{d}: an S row has no claim data")
                break
            s_counts.append(core.flag_count(s["effective_status"] for s in statuses if s is not None))
        else:
            counts["s_false_rejections"] = s_counts
    if group.kind == "golden22" and metas is not None:
        golden = sfc._load_golden_arm(dirs, metas, matrix, sfc.BASELINE_BEST_CASE, invalid)
        folders = golden["folders"]
        if all("correct_refusals" in f for f in folders):
            counts["golden_refusal_family"] = [f["correct_refusals"] for f in folders]
            counts["golden_positive_hits"] = [f["positive_hits"] for f in folders]

    # Share of claims whose RAW label is not the same in every repeat (over the group's claims file).
    cache = common.FixtureCache()
    vectors = []
    for paper_id, index, _ in entries:
        reads = [cache.read(d, paper_id, index, invalid) for d in dirs]
        if all(r is not None for r in reads):
            vectors.append([r.raw for r in reads if r is not None])
    if len(vectors) == len(entries):
        result["changed"] = core.share_changed(vectors)

    for key, values in counts.items():
        if values is not None:
            result["spread"][key] = core.spread(values)
    result["invalid"] = list(dict.fromkeys(invalid))
    if result["invalid"] and not group.for_t:     # a group printed beside T cannot stop the run
        result["skipped"] = "could not be measured: " + "; ".join(result["invalid"])
        result["invalid"] = []
        result["counts"] = {k: None for k in COUNT_KEYS}
        result["spread"] = {k: None for k in COUNT_KEYS}
        result["changed"] = None
    return result


# --- rendering -----------------------------------------------------------------------------------------

def render_group(r: dict) -> list[str]:
    lines = [f"Group: {r['name']}"]
    if r["skipped"]:
        return lines + [f"  not measured ({r['skipped']})"]
    flags = f"void: {'YES - ' + r['void_reason'] if r['void'] else 'no'}"
    lines.append(f"  {flags}; may set T: {'yes' if r['for_t'] else 'no - ' + r['beside_reason']}")
    lines.append(f"  config: {r['config']}; prompt hash {', '.join(r['prompt_hashes'])}; {len(r['dirs'])} repeats")
    for key in COUNT_KEYS:
        values = r["counts"][key]
        if values is None:
            lines.append(f"  {COUNT_LABELS[key]:<36} n/a")
        else:
            lines.append(f"  {COUNT_LABELS[key]:<36} per repeat {values}  spread {r['spread'][key]}")
    if r["changed"] is not None:
        n, total = r["changed"]
        lines.append(f"  claims whose RAW label differs between repeats: {n} of {total} ({100 * n / total:.1f}%)")
    return lines


def run(out_dir: Path) -> int:
    rows_r = resolve_adjudicated_rows(DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR, row_type="R")
    rows_s = resolve_adjudicated_rows(DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR, row_type="S")
    try:
        matrix = load_matrix(sfc.DEFAULT_MATRIX_PATH)
    except ValueError as exc:
        print(f"INVALID: golden matrix: {exc}")
        return 1
    results = [measure_group(g, rows_r, rows_s, matrix) for g in groups()]
    invalid = [f"{r['name']}: {m}" for r in results for m in r["invalid"]]
    if invalid:
        for reason in dict.fromkeys(invalid):
            print(f"INVALID: {reason}")
        return 1

    t_spreads = {
        f"{r['name']} / {COUNT_LABELS[key]}": r["spread"][key]
        for r in results if r["for_t"] and not r["void"] and r["skipped"] is None
        for key in COUNT_KEYS if r["spread"][key] is not None
    }
    t = core.t_rule(t_spreads)

    lines = ["Run-to-run noise of saved no-change groups (descriptive; no recorded verdict changes).", ""]
    lines.append("== Groups that may set T (non-void, product auditor gemini-3.6-flash, flags off) ==")
    for r in results:
        if r["for_t"]:
            lines += render_group(r) + [""]
    if t.t is None:
        lines.append("T: not computed (no eligible group)")
    else:
        lines.append(f"T = {t.t}")
        lines.append("  set by: " + "; ".join(t.set_by) + f" (spread {t.measured})")
        if t.capped:
            lines.append(f"  measured {t.measured}, capped at {core.T_CAP}")
    lines += ["", "== Printed beside T, never used for it (void, gemini-3.8-flash, no run_config, other setting) =="]
    for r in results:
        if not r["for_t"]:
            lines += render_group(r) + [""]
    lines.append("T is measured on single runs, so it is an upper bound for 2-of-3 voted counts. T applies to future "
                 "tests only; how T enters a mark is written in each future pre-registration.")
    text = "\n".join(lines) + "\n"
    print(text)
    payload = {
        "t": {"t": t.t, "measured": t.measured, "capped": t.capped, "set_by": list(t.set_by)},
        "t_spreads": t_spreads, "groups": results,
    }
    for path in common.write_outputs(out_dir, "1b_noise", text, payload):
        print(f"wrote {path}")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out-dir", type=Path, default=common.DEFAULT_OUT_DIR)
    args = parser.parse_args()
    sys.exit(run(args.out_dir))


if __name__ == "__main__":
    main()
