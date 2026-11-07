"""CLI: the full no-regression check of an auditor CANDIDATE against a BASELINE, on the dev set and on the golden
set (decisions D3-D11 of the 2026-11-07 full-check plan). Read-only, prints only, zero LLM calls. It is run once
per candidate; the baseline is the same backend with gemini-3.6-flash at medium.

Each arm is 3 replay folders (eval/replay_audit.py, Vertex runs, so each has a run_config in its _summary.json and
audit_model_served on every claim). Every row-level measure is a per-row 2-of-3 vote across an arm's 3 folders.

Measures (thresholds are constants, never parameters):
  D4 fixes        the 8 targets (the 10 miss rows minus the parked P5-R1, P5-R2), RAW label partially_supported /
                  not_supported. PASS if candidate fixed >= baseline fixed + 1. Parked rows are reported only.
  D5 catches      the 7 REAL_HITS, RAW label; lost = supported. PASS if the candidate loses 0. P1-R3 is reported
                  only, in no total.
  D6 false rej.   matched dev S rows, EFFECTIVE status (missing -> not_supported, else label; score_replay.row_details)
                  partially_supported / not_supported, as n/88 (S rows with no claim count as not false rejections).
                  PASS if candidate <= baseline and <= 8.
  D7 golden       the golden matrix scored per folder with eval.scorer.score on the replayed claims and the frozen
                  matches, then a per-row vote. PASS if the candidate's refusal-family >= 5/16 and positive hits
                  >= 11/21. Grounding-negative FAIL = a golden negative row (scorer.py's definition) that the
                  baseline vote REFUSED and the candidate vote WRONGLY_AFFIRMED.
  D8 Needs review printed as "0 (no code check in this run)".
  D10 cost        per folder, audit calls only (is_audit records of _summary.json): mean prompt / cached / output /
                  thought tokens per audited claim, audit INR per claim and in total. No per-paper projection.

Fallback-served audits (D9): a claim whose audit_model_served differs from its folder's run_config.auditor_model.
The CANDIDATE's such claims are scored as the worst case (target not fixed, catch lost, S row false rejection,
golden negative wrongly affirmed, golden positive false rejection); the BASELINE's as the best case (fixed, kept,
not a false rejection, refused, hit). As-scored and applied totals are both printed, with per-folder counts; the
PASS/FAIL lines use the applied (worst-case candidate vs best-case baseline) numbers. No void count is decided.

INVALID (reason printed, exit 1, no totals): a folder or its _summary.json is missing, unreadable or not status OK;
a folder has no run_config; an arm's run_configs differ in backend, auditor_model, thinking_level or other_models;
candidate and baseline are on different backends; a dev and a golden arm of the same role differ in config; a
required row or claim is missing; a label is not a replay label; a claim lacks audit_model_served; a golden folder
is not a golden replay or does not cover a frozen-matched claim; a model has no price; the row sets are not the
expected sizes (88 S rows with 67 matched, all expecting supported; 16 golden negatives and 21 positives).

Usage (from Prism.PythonService):
  uv run python -m eval.score_full_check \\
      --dev-candidate <c1> --dev-candidate <c2> --dev-candidate <c3> --dev-baseline <b1> ... \\
      --golden-candidate <g1> ... --golden-baseline <gb1> ... [--json-out PATH]
"""
import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from eval import pricing, score_a1, score_screen
from eval.matrix_loader import load_matrix
from eval.score_replay import (
    DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR,
    AdjudicatedRow, _load_fixture, resolve_adjudicated_rows, row_details,
)
from eval.scorer import score
from eval.types import ActualClaim, Match

REPO_ROOT = Path(__file__).parent.parent.parent
DEFAULT_MATRIX_PATH = REPO_ROOT / "docs" / "evals" / "matrix_eval.json"

# --- thresholds and sizes (constants, never parameters) -------------------------------------------
MIN_FIXED_GAIN = 1            # D4: candidate fixed >= baseline fixed + 1
MAX_CATCHES_LOST = 0          # D5
MAX_FALSE_REJECTIONS = 8      # D6 (and <= baseline)
MIN_GOLDEN_REFUSALS = 5       # D7, of EXPECTED_GOLDEN_NEGATIVES
MIN_GOLDEN_POSITIVES = 11     # D7, of EXPECTED_GOLDEN_POSITIVES
EXPECTED_S_ROWS = 88
EXPECTED_S_MATCHED = 67
EXPECTED_GOLDEN_NEGATIVES = 16
EXPECTED_GOLDEN_POSITIVES = 21
NEEDS_REVIEW_LINE = "0 (no code check in this run)"
STATUS_OK = "OK"
CONFIG_KEYS = ("backend", "auditor_model", "thinking_level", "other_models")
FALSE_REJECTION_STATUSES = ("partially_supported", "not_supported")
SUPPORTED, NOT_SUPPORTED = "supported", "not_supported"
GOLDEN_SET_MARK = "golden"

# D9: what a fallback-served claim counts as, per role. CANDIDATE = worst case, BASELINE = best case.
# Roles: target / catch (RAW label), s_row (EFFECTIVE status), golden_negative / golden_positive (matrix outcome).
CANDIDATE_WORST_CASE = {
    "target": SUPPORTED, "catch": SUPPORTED, "s_row": NOT_SUPPORTED,
    "golden_negative": "WRONGLY_AFFIRMED", "golden_positive": "FALSE_REJECTION",
}
BASELINE_BEST_CASE = {
    "target": NOT_SUPPORTED, "catch": NOT_SUPPORTED, "s_row": SUPPORTED,
    "golden_negative": "REFUSED", "golden_positive": "POSITIVE_HIT",
}
# parked rows and P1-R3 have no entry: they are never substituted (reported only).


@dataclass
class Obs:
    """One row seen in one folder: what the folder says, whether the audit was fallback-served, and what the
    row counts as after the D9 substitution."""
    row_id: str
    role: str
    folder: str
    claim_id: tuple
    as_scored: str
    applied: str
    served: str | None
    fallback: bool

    @property
    def changed(self) -> bool:
        return self.applied != self.as_scored


def _vote(values: list[str], wanted) -> bool:
    return score_a1._votes(values, wanted) >= score_a1.VOTES_NEEDED


def _unique(reasons: list[str]) -> list[str]:
    return list(dict.fromkeys(reasons))


# --- folders: summary, run_config, cost ------------------------------------------------------------

@dataclass
class FolderMeta:
    path: Path
    summary: dict | None
    config: dict | None


def _load_meta(dirs: list[Path], invalid: list[str]) -> list[FolderMeta]:
    metas: list[FolderMeta] = []
    for folder in dirs:
        if not folder.is_dir():
            invalid.append(f"{folder}: folder missing")
            metas.append(FolderMeta(folder, None, None))
            continue
        summary_path = folder / "_summary.json"
        if not summary_path.is_file():
            invalid.append(f"{folder}: no _summary.json")
            metas.append(FolderMeta(folder, None, None))
            continue
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except ValueError as exc:
            invalid.append(f"{folder}: _summary.json unreadable ({exc})")
            metas.append(FolderMeta(folder, None, None))
            continue
        if not isinstance(summary, dict):
            invalid.append(f"{folder}: _summary.json is not an object")
            metas.append(FolderMeta(folder, None, None))
            continue
        if summary.get("status") != STATUS_OK:
            invalid.append(f"{folder}: _summary.json status is {summary.get('status')!r}, not {STATUS_OK}")
        config = summary.get("run_config")
        if not isinstance(config, dict):
            invalid.append(f"{folder}: no run_config in _summary.json (a default run carries no audit_model_served)")
            config = None
        elif not isinstance(config.get("auditor_model"), str):
            invalid.append(f"{folder}: run_config has no auditor_model")
            config = None
        metas.append(FolderMeta(folder, summary, config))
    configs = [m.config for m in metas]
    if all(c is not None for c in configs):
        invalid.extend(score_screen._config_differences(dirs, configs))
    return metas


def _config_differences_between(label_a: str, config_a: dict, label_b: str, config_b: dict, keys) -> list[str]:
    return [
        f"run_config.{key} differs between {label_a} ({config_a.get(key)!r}) and {label_b} ({config_b.get(key)!r})"
        for key in keys if config_a.get(key) != config_b.get(key)
    ]


def _folder_cost(meta: FolderMeta, invalid: list[str]) -> dict | None:
    """Audit calls only (D10): means per audited claim and the audit cost in INR, each call priced at the model
    that served it."""
    records = meta.summary.get("records") if meta.summary else None
    if not isinstance(records, list):
        invalid.append(f"{meta.path}: _summary.json has no records")
        return None
    audits = [r for r in records if isinstance(r, dict) and r.get("is_audit")]
    if not audits:
        invalid.append(f"{meta.path}: _summary.json has no audit call records")
        return None
    total_usd = 0.0
    for record in audits:
        model = record.get("model_used")
        if not isinstance(model, str):
            invalid.append(f"{meta.path}: an audit record has no model_used")
            return None
        try:
            total_usd += pricing.strict_cost_usd_for_model(
                model, record.get("prompt_tokens") or 0, record.get("output_tokens") or 0,
                record.get("thought_tokens") or 0, record.get("cached_tokens") or 0, record.get("tool_use_tokens") or 0,
            )
        except pricing.UnpricedModelError as exc:
            invalid.append(f"{meta.path}: {exc}")
            return None
    n = len(audits)

    def mean(field: str) -> float:
        return sum((r.get(field) or 0) for r in audits) / n

    total_inr = total_usd * pricing.INR_PER_USD
    return {
        "folder": str(meta.path), "audit_calls": n,
        "mean_prompt_tokens": round(mean("prompt_tokens"), 1), "mean_cached_tokens": round(mean("cached_tokens"), 1),
        "mean_output_tokens": round(mean("output_tokens"), 1), "mean_thought_tokens": round(mean("thought_tokens"), 1),
        "audit_inr_per_claim": round(total_inr / n, 4), "audit_inr_total": round(total_inr, 2),
    }


# --- observations ----------------------------------------------------------------------------------

def _make_obs(
    row_id: str, role: str, folder: Path, claim_id: tuple, as_scored: str, claim: dict, config: dict,
    table: dict, invalid: list[str],
) -> Obs:
    if "audit_model_served" not in claim:
        invalid.append(f"{folder}: {row_id} claim lacks audit_model_served")
        served, fallback = None, False
    else:
        served = claim["audit_model_served"]
        fallback = score_screen._served_differs(served, config.get("auditor_model"))
    applied = table[role] if (fallback and role in table) else as_scored
    return Obs(row_id, role, str(folder), claim_id, as_scored, applied, served if isinstance(served, str) else None, fallback)


def _dev_roles() -> dict[str, str]:
    """row_id -> role for the refusal rows the dev measures use."""
    roles: dict[str, str] = {}
    parked = set(score_screen.PARKED_ROWS)
    for rid in score_screen.MISS_ROWS:
        roles[rid] = "parked" if rid in parked else "target"
    for rid in score_screen.REAL_HITS:
        roles[rid] = "catch"
    for rid in score_screen.OTHER_ROWS:
        roles[rid] = "other"
    return roles


def _load_dev_arm(
    dirs: list[Path], metas: list[FolderMeta], rows_r: list[AdjudicatedRow], rows_s: list[AdjudicatedRow],
    table: dict, invalid: list[str],
) -> dict[str, list[Obs]]:
    """{row_id: [Obs per folder]} for the dev refusal rows (RAW label) and the matched S rows (EFFECTIVE status)."""
    obs: dict[str, list[Obs]] = {}
    # score_screen.collect is the refusal rows' loader (the same code path score_screen votes on): RAW labels and
    # the claim dicts per folder, and its own INVALID reasons.
    collect_invalid, labels, claims, _ = score_screen.collect(rows_r, dirs)
    invalid.extend(collect_invalid)
    if collect_invalid or any(meta.config is None for meta in metas):
        return obs   # the reasons are already recorded

    roles = _dev_roles()
    by_id = {r.row_id: r for r in rows_r}
    for rid, role in roles.items():
        row = by_id[rid]
        obs[rid] = [
            _make_obs(rid, role, dirs[i], (row.paper_id, row.claim_index), labels[rid][i], claims[rid][i],
                      metas[i].config, table, invalid)
            for i in range(len(dirs))
        ]

    matched_s = [r for r in rows_s if r.claim_index is not None]
    for i, folder in enumerate(dirs):
        if not folder.is_dir() or metas[i].config is None:
            continue   # already INVALID
        details = row_details(matched_s, folder)
        for row in matched_s:
            detail = details[row.row_id]
            if detail is None:
                reason = "FIXTURE_MISSING" if _load_fixture(folder, row.paper_id) is None else "no claim data"
                invalid.append(f"{folder}: {row.row_id} {reason}")
                continue
            if detail["raw_label"] not in score_screen.VALID_LABELS:
                invalid.append(f"{folder}: {row.row_id} label {detail['raw_label']!r} is not a replay label")
                continue
            claim = score_a1._row_claim(row, folder)
            obs.setdefault(row.row_id, []).append(
                _make_obs(row.row_id, "s_row", folder, (row.paper_id, row.claim_index), detail["effective_status"],
                          claim, metas[i].config, table, invalid)
            )
    return obs


def _check_s_rows(rows_s: list[AdjudicatedRow], invalid: list[str]) -> None:
    matched = [r for r in rows_s if r.claim_index is not None]
    if len(rows_s) != EXPECTED_S_ROWS or len(matched) != EXPECTED_S_MATCHED:
        invalid.append(
            f"S rows: {len(rows_s)} rows with {len(matched)} matched, expected {EXPECTED_S_ROWS} with {EXPECTED_S_MATCHED}"
        )
    not_supported = [r.row_id for r in matched if r.expected_row.expected_label != SUPPORTED]
    if not_supported:
        invalid.append(f"matched S rows whose expected label is not supported: {not_supported}")


# --- golden ----------------------------------------------------------------------------------------

def _is_negative(row) -> bool:
    return row.grounding_negative or row.expected_label == "not_supported"   # eval/scorer.py's definition


def _read_json(path: Path, invalid: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        invalid.append(f"{path}: file missing")
    except ValueError as exc:
        invalid.append(f"{path}: unreadable ({exc})")
    return None


def _load_golden_arm(dirs: list[Path], metas: list[FolderMeta], matrix, table: dict, invalid: list[str]) -> dict:
    """Returns {"obs": {row_id: [Obs per folder]}, "folders": [per-folder matrix numbers]}."""
    obs: dict[str, list[Obs]] = {}
    folders: list[dict] = []
    for i, folder in enumerate(dirs):
        if not folder.is_dir() or metas[i].config is None:
            folders.append({"folder": str(folder)})
            continue
        totals = dict(correct_refusals=0, total_negatives=0, positive_hits=0, positive_total=0, false_rejections=0, skipped=0)
        for paper in matrix.papers:
            where = f"{folder}/{paper.paper_id}.json"
            fixture = _read_json(folder / f"{paper.paper_id}.json", invalid)
            if fixture is None:
                continue
            if not isinstance(fixture, dict) or not all(k in fixture for k in ("header", "claims", "matches")):
                invalid.append(f"{where}: not a replay fixture (needs header, claims and matches)")
                continue
            if (fixture["header"].get("replay") or {}).get("set") != GOLDEN_SET_MARK:
                invalid.append(f"{where}: header.replay.set is not {GOLDEN_SET_MARK!r} (not a --set golden replay)")
                continue
            try:   # ActualClaim's label is one of the three replay labels, so a bad label is rejected here
                claims = [ActualClaim(**c) for c in fixture["claims"]]
                matches = [Match.model_validate(m) for m in fixture["matches"]]
            except (ValidationError, TypeError) as exc:
                invalid.append(f"{where}: bad claim or match (a label must be a replay label): {exc}")
                continue
            raw_by_index = {c["index"]: c for c in fixture["claims"]}
            known = {m.expected_id for m in matches}
            unmatched_rows = [r.id for r in paper.expected_rows if r.id not in known]
            if unmatched_rows:
                invalid.append(f"{where}: no frozen match entry for {unmatched_rows}")
                continue
            lacking = [m.actual_index for m in matches if m.actual_index is not None and m.actual_index not in raw_by_index]
            if lacking:
                invalid.append(f"{where}: the replay does not cover frozen-matched claims {sorted(set(lacking))}")
                continue

            report = score(paper.expected_rows, claims, matches, positive_hit_floor=0)
            for key in totals:
                totals[key] += getattr(report, key)
            match_by_row = {m.expected_id: m for m in matches}
            for row in paper.expected_rows:
                role = "golden_negative" if _is_negative(row) else "golden_positive"
                outcome = report.per_row[row.id].outcome
                match = match_by_row[row.id]
                if match.actual_index is None:
                    claim_id, claim = (paper.paper_id, None), None
                else:
                    claim_id, claim = (paper.paper_id, match.actual_index), raw_by_index[match.actual_index]
                if claim is None:   # no claim was replayed for this row: nothing to substitute
                    obs.setdefault(row.id, []).append(
                        Obs(row.id, role, str(folder), claim_id, outcome, outcome, None, False))
                else:
                    obs.setdefault(row.id, []).append(
                        _make_obs(row.id, role, folder, claim_id, outcome, claim, metas[i].config, table, invalid))
        folders.append({"folder": str(folder), **totals})
    return {"obs": obs, "folders": folders}


def _check_golden_sizes(matrix, invalid: list[str]) -> None:
    rows = [r for p in matrix.papers for r in p.expected_rows]
    negatives = sum(1 for r in rows if _is_negative(r))
    positives = len(rows) - negatives
    if negatives != EXPECTED_GOLDEN_NEGATIVES or positives != EXPECTED_GOLDEN_POSITIVES:
        invalid.append(
            f"golden matrix: {negatives} negatives and {positives} positives, "
            f"expected {EXPECTED_GOLDEN_NEGATIVES} and {EXPECTED_GOLDEN_POSITIVES}"
        )


# --- measures --------------------------------------------------------------------------------------

def _field(obs: dict[str, list[Obs]], rid: str, field: str) -> list[str]:
    return [getattr(o, field) for o in obs[rid]]


def r_votes(labels: dict[str, list[str]]) -> dict:
    """Targets fixed and catches lost from RAW labels with no substitution - exactly what score_screen votes."""
    parked = set(score_screen.PARKED_ROWS)
    targets = [r for r in score_screen.MISS_ROWS if r not in parked]
    return {
        "targets_fixed": [r for r in targets if _vote(labels[r], score_a1.FIXED_LABELS)],
        "catches_lost": [r for r in score_screen.REAL_HITS if _vote(labels[r], score_a1.LOST_LABEL)],
    }


def _ids(obs, ids, field, wanted) -> list[str]:
    return [rid for rid in ids if _vote(_field(obs, rid, field), wanted)]


def _dev_measures(cand: dict, base: dict, rows_s: list[AdjudicatedRow]) -> dict:
    parked = list(score_screen.PARKED_ROWS)
    targets = [r for r in score_screen.MISS_ROWS if r not in set(parked)]
    catches = list(score_screen.REAL_HITS)
    others = list(score_screen.OTHER_ROWS)
    matched_s = [r.row_id for r in rows_s if r.claim_index is not None]
    fixed = score_a1.FIXED_LABELS

    d4 = {
        "targets": targets,
        "candidate_as_scored": _ids(cand, targets, "as_scored", fixed),
        "candidate_worst_case": _ids(cand, targets, "applied", fixed),
        "baseline_as_scored": _ids(base, targets, "as_scored", fixed),
        "baseline_best_case": _ids(base, targets, "applied", fixed),
        "parked": {
            arm_name: {rid: _field(arm, rid, "as_scored") for rid in parked}
            for arm_name, arm in (("candidate", cand), ("baseline", base))
        },
    }
    d4["pass"] = len(d4["candidate_worst_case"]) >= len(d4["baseline_best_case"]) + MIN_FIXED_GAIN

    d5 = {
        "catches": catches,
        "candidate_as_scored_lost": _ids(cand, catches, "as_scored", score_a1.LOST_LABEL),
        "candidate_worst_case_lost": _ids(cand, catches, "applied", score_a1.LOST_LABEL),
        "baseline_as_scored_lost": _ids(base, catches, "as_scored", score_a1.LOST_LABEL),
        "other_reported_only": {
            arm_name: {rid: _field(arm, rid, "as_scored") for rid in others}
            for arm_name, arm in (("candidate", cand), ("baseline", base))
        },
    }
    d5["pass"] = len(d5["candidate_worst_case_lost"]) <= MAX_CATCHES_LOST

    d6 = {
        "s_rows": len(rows_s), "matched": len(matched_s), "no_claim": len(rows_s) - len(matched_s),
        "candidate_as_scored": _ids(cand, matched_s, "as_scored", FALSE_REJECTION_STATUSES),
        "candidate_worst_case": _ids(cand, matched_s, "applied", FALSE_REJECTION_STATUSES),
        "baseline_as_scored": _ids(base, matched_s, "as_scored", FALSE_REJECTION_STATUSES),
        "baseline_best_case": _ids(base, matched_s, "applied", FALSE_REJECTION_STATUSES),
    }
    d6["pass"] = (
        len(d6["candidate_worst_case"]) <= len(d6["baseline_best_case"])
        and len(d6["candidate_worst_case"]) <= MAX_FALSE_REJECTIONS
    )
    return {"D4": d4, "D5": d5, "D6": d6}


def _golden_measures(cand: dict, base: dict, matrix) -> dict:
    rows = [r for p in matrix.papers for r in p.expected_rows]
    negatives = [r.id for r in rows if _is_negative(r)]
    positives = [r.id for r in rows if not _is_negative(r)]
    c_obs, b_obs = cand["obs"], base["obs"]

    def refused(obs, field):
        return [rid for rid in negatives if _vote(_field(obs, rid, field), "REFUSED")]

    def hits(obs, field):
        return [rid for rid in positives if _vote(_field(obs, rid, field), "POSITIVE_HIT")]

    grounding_fail = [
        rid for rid in negatives
        if _vote(_field(b_obs, rid, "applied"), "REFUSED") and _vote(_field(c_obs, rid, "applied"), "WRONGLY_AFFIRMED")
    ]
    d7 = {
        "negatives": len(negatives), "positives": len(positives),
        "candidate_refusals_as_scored": refused(c_obs, "as_scored"), "candidate_refusals_worst_case": refused(c_obs, "applied"),
        "baseline_refusals_as_scored": refused(b_obs, "as_scored"), "baseline_refusals_best_case": refused(b_obs, "applied"),
        "candidate_hits_as_scored": hits(c_obs, "as_scored"), "candidate_hits_worst_case": hits(c_obs, "applied"),
        "baseline_hits_as_scored": hits(b_obs, "as_scored"), "baseline_hits_best_case": hits(b_obs, "applied"),
        "per_folder": {"candidate": cand["folders"], "baseline": base["folders"]},
    }
    d7["pass"] = (
        len(d7["candidate_refusals_worst_case"]) >= MIN_GOLDEN_REFUSALS
        and len(d7["candidate_hits_worst_case"]) >= MIN_GOLDEN_POSITIVES
    )
    negative_check = {"failing_rows": grounding_fail, "pass": not grounding_fail}
    return {"D7": d7, "D7_grounding_negative": negative_check}


def _fallback_counts(arms: dict[str, list[Obs]]) -> list[dict]:
    """Per arm and folder: distinct fallback-served claims among the scored claims, substitutions applied, and
    how many of them changed the row's outcome."""
    out = []
    for name, obs in arms.items():
        by_folder: dict[str, list[Obs]] = {}
        for row_obs in obs.values():
            for o in row_obs:
                by_folder.setdefault(o.folder, []).append(o)
        for folder, items in sorted(by_folder.items()):
            out.append({
                "arm": name, "folder": folder,
                "fallback_served_claims": len({o.claim_id for o in items if o.fallback}),
                "substitutions_applied": sum(1 for o in items if o.fallback and o.role in CANDIDATE_WORST_CASE),
                "outcomes_changed": sum(1 for o in items if o.changed),
            })
    return out


def _per_claim(arm_name: str, set_name: str, obs: dict[str, list[Obs]]) -> list[dict]:
    return [
        {
            "arm": arm_name, "set": set_name, "row_id": o.row_id, "role": o.role, "folder": o.folder,
            "as_scored": o.as_scored, "applied": o.applied, "served_model": o.served,
            "fallback_served": o.fallback, "substituted": o.fallback and o.role in CANDIDATE_WORST_CASE,
        }
        for row_obs in obs.values() for o in row_obs
    ]


# --- report ----------------------------------------------------------------------------------------

def _fmt(ids: list[str], total: int) -> str:
    return f"{len(ids)}/{total} {ids}"


def _verdict(ok: bool) -> str:
    return "PASS" if ok else "FAIL"


def _print_results(r: dict) -> None:
    m = r["measures"]
    print(f"candidate run_config: {r['candidate']['run_config']}")
    print(f"baseline  run_config: {r['baseline']['run_config']}")

    d4 = m["D4"]
    n = len(d4["targets"])
    print(f"\nD4 fixes ({n} targets, RAW partially_supported/not_supported, 2-of-3 vote)")
    print(f"  candidate: as scored {_fmt(d4['candidate_as_scored'], n)}; worst case {_fmt(d4['candidate_worst_case'], n)}")
    print(f"  baseline : as scored {_fmt(d4['baseline_as_scored'], n)}; best case  {_fmt(d4['baseline_best_case'], n)}")
    print(f"  need candidate worst case >= baseline best case + {MIN_FIXED_GAIN}: {_verdict(d4['pass'])}")
    for arm_name, rows in d4["parked"].items():
        print(f"  parked, reported only ({arm_name}): " + "; ".join(f"{rid}: {', '.join(v)}" for rid, v in rows.items()))

    d5 = m["D5"]
    n = len(d5["catches"])
    print(f"\nD5 catches ({n} real hits, RAW; lost = supported)")
    print(f"  candidate lost: as scored {_fmt(d5['candidate_as_scored_lost'], n)}; worst case {_fmt(d5['candidate_worst_case_lost'], n)}")
    print(f"  baseline lost : as scored {_fmt(d5['baseline_as_scored_lost'], n)}")
    print(f"  need candidate worst case lost <= {MAX_CATCHES_LOST}: {_verdict(d5['pass'])}")
    for arm_name, rows in d5["other_reported_only"].items():
        print(f"  reported only, in no total ({arm_name}): " + "; ".join(f"{rid}: {', '.join(v)}" for rid, v in rows.items()))

    d6 = m["D6"]
    n = d6["s_rows"]
    print(f"\nD6 false rejections (matched S rows, EFFECTIVE status; {d6['no_claim']} of {n} S rows have no claim, not false rejections)")
    print(f"  candidate: as scored {_fmt(d6['candidate_as_scored'], n)}; worst case {_fmt(d6['candidate_worst_case'], n)}")
    print(f"  baseline : as scored {_fmt(d6['baseline_as_scored'], n)}; best case  {_fmt(d6['baseline_best_case'], n)}")
    print(f"  need candidate worst case <= baseline best case and <= {MAX_FALSE_REJECTIONS}: {_verdict(d6['pass'])}")

    d7 = m["D7"]
    print("\nD7 golden (matrix scoring per folder, then per-row 2-of-3 vote)")
    print(f"  refusal-family  candidate: as scored {len(d7['candidate_refusals_as_scored'])}/{d7['negatives']}, "
          f"worst case {len(d7['candidate_refusals_worst_case'])}/{d7['negatives']}; "
          f"baseline: as scored {len(d7['baseline_refusals_as_scored'])}, best case {len(d7['baseline_refusals_best_case'])}")
    print(f"  positive hits   candidate: as scored {len(d7['candidate_hits_as_scored'])}/{d7['positives']}, "
          f"worst case {len(d7['candidate_hits_worst_case'])}/{d7['positives']}; "
          f"baseline: as scored {len(d7['baseline_hits_as_scored'])}, best case {len(d7['baseline_hits_best_case'])}")
    print(f"  need candidate worst case >= {MIN_GOLDEN_REFUSALS}/{d7['negatives']} and >= {MIN_GOLDEN_POSITIVES}/{d7['positives']}: "
          f"{_verdict(d7['pass'])}")
    for arm_name, folders in d7["per_folder"].items():
        for f in folders:
            if "correct_refusals" in f:
                print(f"    {arm_name} {f['folder']}: refusals {f['correct_refusals']}/{f['total_negatives']}, "
                      f"positive hits {f['positive_hits']}/{f['positive_total']}, false rejections {f['false_rejections']}, "
                      f"skipped {f['skipped']}")
    gn = m["D7_grounding_negative"]
    print(f"  grounding-negative: {_verdict(gn['pass'])}" + ("" if gn["pass"] else f"  failing rows {gn['failing_rows']}"))

    print(f"\nD8 Needs review: {NEEDS_REVIEW_LINE}")

    print("\nFallback-served audits (D9), per arm and folder:")
    for f in r["fallback"]:
        print(f"  {f['arm']:<13} {f['folder']}: fallback-served claims {f['fallback_served_claims']}, "
              f"substitutions applied {f['substitutions_applied']}, outcomes changed {f['outcomes_changed']}")

    print("\nD10 audit cost per folder (audit calls only; failed attempts are not in the records):")
    for c in r["cost"]:
        print(f"  {c['arm']:<13} {c['folder']}: {c['audit_calls']} audit calls, mean tokens prompt {c['mean_prompt_tokens']} "
              f"(cached {c['mean_cached_tokens']}) / output {c['mean_output_tokens']} / thought {c['mean_thought_tokens']}; "
              f"INR {c['audit_inr_per_claim']} per claim, INR {c['audit_inr_total']} total")

    print(f"\nOverall: {r['overall']}  "
          f"(D4 {_verdict(m['D4']['pass'])}, D5 {_verdict(m['D5']['pass'])}, D6 {_verdict(m['D6']['pass'])}, "
          f"D7 {_verdict(m['D7']['pass'])}, grounding-negative {_verdict(gn['pass'])})")


# --- run -------------------------------------------------------------------------------------------

def run(
    dev_candidate: list[Path], dev_baseline: list[Path], golden_candidate: list[Path], golden_baseline: list[Path],
    dev_eval_path: Path = DEFAULT_DEV_EVAL_PATH, match_map_path: Path = DEFAULT_MATCH_MAP_PATH,
    run1_fixture_dir: Path = DEFAULT_RUN1_FIXTURE_DIR, matrix_path: Path = DEFAULT_MATRIX_PATH,
    json_out: Path | None = None,
) -> int:
    arms = {
        "dev candidate": dev_candidate, "dev baseline": dev_baseline,
        "golden candidate": golden_candidate, "golden baseline": golden_baseline,
    }
    arms = {name: [Path(d).resolve() for d in dirs] for name, dirs in arms.items()}
    print("Folders:")
    for name, dirs in arms.items():
        for d in dirs:
            print(f"  {name:<17} {d}")

    all_dirs = [d for dirs in arms.values() for d in dirs]
    if json_out is not None and any(Path(json_out).resolve().is_relative_to(d) for d in all_dirs):
        print("INVALID: --json-out must not be inside a fixture folder")
        return 1
    for name, dirs in arms.items():
        if len(dirs) != score_a1.REPEATS:
            print(f"INVALID: {name} needs exactly {score_a1.REPEATS} folders, got {len(dirs)}")
            return 1
    setup_errors = score_screen._setup_errors()
    if setup_errors:
        for reason in setup_errors:
            print(f"STOP: {reason}")
        return 1

    invalid: list[str] = []
    rows_r = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir, row_type="R")
    rows_s = resolve_adjudicated_rows(dev_eval_path, match_map_path, run1_fixture_dir, row_type="S")
    _check_s_rows(rows_s, invalid)
    try:
        matrix = load_matrix(matrix_path)
    except ValueError as exc:
        invalid.append(f"golden matrix: {exc}")
        matrix = None
    if matrix is not None:
        _check_golden_sizes(matrix, invalid)

    metas = {name: _load_meta(dirs, invalid) for name, dirs in arms.items()}
    configs = {name: next((m.config for m in ms if m.config is not None), None) for name, ms in metas.items()}
    for role in ("candidate", "baseline"):
        a, b = configs[f"dev {role}"], configs[f"golden {role}"]
        if a is not None and b is not None:
            invalid.extend(_config_differences_between(f"dev {role}", a, f"golden {role}", b, CONFIG_KEYS))
    for set_name in ("dev", "golden"):
        c, b = configs[f"{set_name} candidate"], configs[f"{set_name} baseline"]
        if c is not None and b is not None:
            invalid.extend(_config_differences_between(f"{set_name} candidate", c, f"{set_name} baseline", b, ("backend",)))

    dev_obs = {
        role: _load_dev_arm(arms[f"dev {role}"], metas[f"dev {role}"], rows_r, rows_s, table, invalid)
        for role, table in (("candidate", CANDIDATE_WORST_CASE), ("baseline", BASELINE_BEST_CASE))
    }
    golden = {}
    if matrix is not None:
        golden = {
            role: _load_golden_arm(arms[f"golden {role}"], metas[f"golden {role}"], matrix, table, invalid)
            for role, table in (("candidate", CANDIDATE_WORST_CASE), ("baseline", BASELINE_BEST_CASE))
        }

    costs: list[dict] = []
    for name, ms in metas.items():
        for meta in ms:
            if meta.summary is not None:
                cost = _folder_cost(meta, invalid)
                if cost is not None:
                    costs.append({"arm": name, **cost})

    invalid = _unique(invalid)
    if invalid:
        for reason in invalid:
            print(f"INVALID: {reason}")
        return 1

    measures = _dev_measures(dev_obs["candidate"], dev_obs["baseline"], rows_s)
    measures.update(_golden_measures(golden["candidate"], golden["baseline"], matrix))
    fallback = _fallback_counts({
        "dev candidate": dev_obs["candidate"], "dev baseline": dev_obs["baseline"],
        "golden candidate": golden["candidate"]["obs"], "golden baseline": golden["baseline"]["obs"],
    })
    overall = all(measures[k]["pass"] for k in ("D4", "D5", "D6", "D7", "D7_grounding_negative"))
    results = {
        "arms": {name: [str(d) for d in dirs] for name, dirs in arms.items()},
        "candidate": {"run_config": configs["dev candidate"]},
        "baseline": {"run_config": configs["dev baseline"]},
        "measures": measures,
        "needs_review": NEEDS_REVIEW_LINE,
        "fallback": fallback,
        "cost": costs,
        "per_claim": (
            _per_claim("candidate", "dev", dev_obs["candidate"]) + _per_claim("baseline", "dev", dev_obs["baseline"])
            + _per_claim("candidate", "golden", golden["candidate"]["obs"])
            + _per_claim("baseline", "golden", golden["baseline"]["obs"])
        ),
        "overall": "PASS" if overall else "FAIL",
    }
    _print_results(results)
    if json_out is not None:
        json_out = Path(json_out)
        json_out.parent.mkdir(parents=True, exist_ok=True)
        json_out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"\nwrote {json_out.resolve()}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ("dev-candidate", "dev-baseline", "golden-candidate", "golden-baseline"):
        parser.add_argument(f"--{name}", action="append", required=True, dest=name.replace("-", "_"), type=Path)
    parser.add_argument("--dev-eval-path", type=Path, default=DEFAULT_DEV_EVAL_PATH)
    parser.add_argument("--match-map-path", type=Path, default=DEFAULT_MATCH_MAP_PATH)
    parser.add_argument("--run1-fixture-dir", type=Path, default=DEFAULT_RUN1_FIXTURE_DIR)
    parser.add_argument("--matrix-path", type=Path, default=DEFAULT_MATRIX_PATH)
    parser.add_argument("--json-out", type=Path, default=None)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    for name in ("dev_candidate", "dev_baseline", "golden_candidate", "golden_baseline"):
        if len(getattr(args, name)) != score_a1.REPEATS:
            parser.error(f"--{name.replace('_', '-')} must be given exactly {score_a1.REPEATS} times, got {len(getattr(args, name))}")
    sys.exit(run(
        args.dev_candidate, args.dev_baseline, args.golden_candidate, args.golden_baseline,
        args.dev_eval_path, args.match_map_path, args.run1_fixture_dir, args.matrix_path, args.json_out,
    ))


if __name__ == "__main__":
    main()
