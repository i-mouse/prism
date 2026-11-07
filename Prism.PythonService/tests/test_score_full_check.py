"""Unit tests for eval/score_full_check.py. Offline: invented row ids, claims and folders in tmp_path; the
adjudicated rows, the row-group constants, the expected set sizes and the thresholds are patched to small
numbers, so no dev_eval / match map / matrix / fixture of the repo is read.

The invented world
  refusal rows   misses M1..M5 (M1, M2 parked, so the targets are M3, M4, M5), real hits H1, H2, other O1
  S rows         S0 (shares M3's claim - the P5-R2 / P5-S1 situation), S1..S4, S5 (no claim)
  golden         papers g1 (N1, N2 negatives, P1 positive) and g2 (N3, P2, P3)
  arms           candidate gemini-3.8-flash / high, baseline gemini-3.6-flash / medium, both on Vertex
"""
import json
import shutil
import sys

import pytest

from eval import score_full_check as sfc, score_screen
from eval.score_replay import AdjudicatedRow
from eval.types import ExpectedRow

SUP, PS, NS = "supported", "partially_supported", "not_supported"
CAND, BASE, FALLBACK = "gemini-3.8-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"
CAND_CFG = {"backend": "vertex", "auditor_model": CAND, "thinking_level": "high",
            "other_models": {"structurer": BASE}, "project": "p"}
BASE_CFG = {"backend": "vertex", "auditor_model": BASE, "thinking_level": "medium",
            "other_models": {"structurer": BASE}, "project": "p"}

MISSES, PARKED, TARGETS = ("M1", "M2", "M3", "M4", "M5"), ("M1", "M2"), ("M3", "M4", "M5")
REALS, OTHERS = ("H1", "H2"), ("O1",)
R_IDS = MISSES + REALS + OTHERS
S_FILES = ("S1", "S2", "S3", "S4")          # S0 lives in paper-M3 (shared claim); S5 has no claim
G_PAPERS = {
    "arxiv-g1": [("N1", NS, True), ("N2", NS, True), ("P1", SUP, False)],
    "arxiv-g2": [("N3", NS, True), ("P2", SUP, False), ("P3", SUP, False)],
}
G_CODES = {"NS": (NS, False), "SUP": (SUP, False), "PS": (PS, False), "GROUNDED": (SUP, True)}
EFFECTIVE = {SUP: (SUP, False), PS: (PS, False), NS: (NS, False), "grounded_away": (SUP, True)}


def _r_rows():
    return [
        AdjudicatedRow(row_id=rid, paper_id=f"paper-{rid}", claim_index=0,
                       expected_row=ExpectedRow(id=rid, expected_label=NS, grounding_negative=True))
        for rid in R_IDS
    ]


def _s_rows(expected=SUP):
    def row(sid, paper, index):
        return AdjudicatedRow(row_id=sid, paper_id=paper, claim_index=index,
                              expected_row=ExpectedRow(id=sid, expected_label=expected, grounding_negative=False))
    return ([row("S0", "paper-M3", 0)] + [row(s, f"paper-{s}", 0) for s in S_FILES] + [row("S5", "paper-S5", None)])


@pytest.fixture(autouse=True)
def _patch(monkeypatch):
    monkeypatch.setattr(sfc, "resolve_adjudicated_rows",
                        lambda *a, row_type="R", **k: _r_rows() if row_type == "R" else _s_rows())
    monkeypatch.setattr(score_screen, "MISS_ROWS", MISSES)
    monkeypatch.setattr(score_screen, "REAL_HITS", REALS)
    monkeypatch.setattr(score_screen, "OTHER_ROWS", OTHERS)
    monkeypatch.setattr(score_screen, "PARKED_ROWS", PARKED)
    monkeypatch.setattr(sfc, "EXPECTED_S_ROWS", 6)
    monkeypatch.setattr(sfc, "EXPECTED_S_MATCHED", 5)
    monkeypatch.setattr(sfc, "EXPECTED_GOLDEN_NEGATIVES", 3)
    monkeypatch.setattr(sfc, "EXPECTED_GOLDEN_POSITIVES", 3)
    monkeypatch.setattr(sfc, "MAX_FALSE_REJECTIONS", 2)
    monkeypatch.setattr(sfc, "MIN_GOLDEN_REFUSALS", 2)
    monkeypatch.setattr(sfc, "MIN_GOLDEN_POSITIVES", 2)


# --- the invented folders ---------------------------------------------------------------------

def spec(r=None, s=None, g=None, fb=()):
    """What one folder (dev and golden) holds. fb = row ids whose audit was served by the fallback model."""
    r_ = {**{m: SUP for m in MISSES}, **{h: NS for h in REALS}, "O1": SUP, **(r or {})}
    s_ = {**{sid: SUP for sid in S_FILES}, **(s or {})}
    g_ = {**{"N1": "NS", "N2": "NS", "N3": "NS", "P1": "SUP", "P2": "SUP", "P3": "SUP"}, **(g or {})}
    return {"r": r_, "s": s_, "g": g_, "fb": set(fb)}


def _claim(index, label, missing, served):
    claim = {"index": index, "label": label, "missing": missing, "grounding_status": None,
             "claim_text_verbatim": "c", "claim_summary": "s", "evidence_spans": []}
    if served is not None:
        claim["audit_model_served"] = served
    return claim


def _audit_record(paper, index, model, prompt=1000, cached=200, output=100, thought=400, is_audit=True):
    return {"stage": "audit", "paper_id": paper, "claim_index": index, "thinking_level": "high", "model_used": model,
            "prompt_tokens": prompt, "output_tokens": output, "thought_tokens": thought,
            "total_tokens": prompt + output + thought, "latency_s": 1.0, "cached_tokens": cached,
            "tool_use_tokens": 0, "is_audit": is_audit}


def _write_summary(folder, cfg, records, status="OK"):
    body = {"status": status, "records": records}
    if cfg is not None:
        body["run_config"] = cfg
    (folder / "_summary.json").write_text(json.dumps(body), encoding="utf-8")


def _write_dev(folder, sp, cfg):
    folder.mkdir(parents=True)
    served = lambda rid: FALLBACK if rid in sp["fb"] else cfg["auditor_model"]   # noqa: E731
    records = []

    def write(paper, rid, label, missing):
        (folder / f"{paper}.json").write_text(json.dumps({
            "header": {}, "matches": [], "claims": [_claim(0, label, missing, served(rid))],
        }), encoding="utf-8")
        records.append(_audit_record(paper, 0, served(rid)))
        records.append(_audit_record(paper, 0, cfg["auditor_model"], is_audit=False))

    for rid in R_IDS:
        write(f"paper-{rid}", rid, sp["r"][rid], False)
    for sid in S_FILES:
        label, missing = EFFECTIVE[sp["s"][sid]]
        write(f"paper-{sid}", sid, label, missing)
    _write_summary(folder, cfg, records)


def _write_golden(folder, sp, cfg, mark="golden"):
    folder.mkdir(parents=True)
    records = []
    for paper, rows in G_PAPERS.items():
        claims, matches = [], []
        for index, (rid, _expected, _neg) in enumerate(rows):
            label, missing = G_CODES[sp["g"][rid]]
            model = FALLBACK if rid in sp["fb"] else cfg["auditor_model"]
            claims.append(_claim(index, label, missing, model))
            matches.append({"expected_id": rid, "actual_index": index})
            records.append(_audit_record(paper, index, model))
        (folder / f"{paper}.json").write_text(json.dumps({
            "header": {"replay": {"set": mark}}, "claims": claims, "matches": matches,
        }), encoding="utf-8")
    _write_summary(folder, cfg, records)


def _matrix(path):
    path.write_text(json.dumps({
        "metadata": {"pass_threshold": {"refusal_rate": 0.7, "positive_hit_floor": 10}},
        "papers": [
            {"paper_id": paper, "filename": f"{paper}.pdf", "title": paper,
             "expected_matrix": [
                 {"id": rid, "expected_label": expected, "grounding_negative": neg} for rid, expected, neg in rows
             ]}
            for paper, rows in G_PAPERS.items()
        ],
    }), encoding="utf-8")


class World:
    """Four arms of three folders each (dev/golden x candidate/baseline) built from per-folder specs."""

    def __init__(self, tmp_path, cand=None, base=None, cand_cfg=CAND_CFG, base_cfg=BASE_CFG):
        tmp_path.mkdir(parents=True, exist_ok=True)
        self.tmp = tmp_path
        self.matrix = tmp_path / "matrix_eval.json"
        _matrix(self.matrix)
        cand = cand or [spec()] * 3
        base = base or [spec()] * 3
        self.dev_cand = [tmp_path / f"cand_dev_{i}" for i in (1, 2, 3)]
        self.dev_base = [tmp_path / f"base_dev_{i}" for i in (1, 2, 3)]
        self.gold_cand = [tmp_path / f"cand_gold_{i}" for i in (1, 2, 3)]
        self.gold_base = [tmp_path / f"base_gold_{i}" for i in (1, 2, 3)]
        for i in range(3):
            _write_dev(self.dev_cand[i], cand[i], cand_cfg)
            _write_dev(self.dev_base[i], base[i], base_cfg)
            _write_golden(self.gold_cand[i], cand[i], cand_cfg)
            _write_golden(self.gold_base[i], base[i], base_cfg)
        self.json_out = tmp_path / "out" / "results.json"

    def run(self, capsys, json_out=True, **overrides):
        dirs = dict(dev_candidate=self.dev_cand, dev_baseline=self.dev_base,
                    golden_candidate=self.gold_cand, golden_baseline=self.gold_base)
        dirs.update(overrides)
        code = sfc.run(dirs["dev_candidate"], dirs["dev_baseline"], dirs["golden_candidate"], dirs["golden_baseline"],
                       None, None, None, self.matrix, self.json_out if json_out else None)
        return code, capsys.readouterr().out

    def results(self):
        return json.loads(self.json_out.read_text(encoding="utf-8"))


def _fixes(label="PS"):
    return {"M4": PS if label == "PS" else NS}


def _check(tmp_path, capsys, cand=None, base=None):
    world = World(tmp_path, cand, base)
    code, out = world.run(capsys)
    assert code == 0, out
    return world.results(), out


GOOD = [spec(r={"M4": PS})] * 3     # a candidate that fixes M4 everywhere and changes nothing else


# --- D4 fixes ----------------------------------------------------------------------------------

def test_a_fix_needs_two_of_three_folders(tmp_path, capsys):
    cand = [spec(r={"M4": PS, "M5": PS}), spec(r={"M4": NS, "M5": SUP}), spec(r={"M4": SUP, "M5": SUP})]
    d4 = _check(tmp_path, capsys, cand)[0]["measures"]["D4"]
    assert d4["candidate_as_scored"] == ["M4"] and d4["baseline_as_scored"] == []
    assert d4["pass"] is True


def test_the_candidate_must_fix_one_more_than_the_baseline(tmp_path, capsys):
    base = [spec(r={"M4": PS})] * 3
    d4 = _check(tmp_path, capsys, GOOD, base)[0]["measures"]["D4"]
    assert len(d4["candidate_worst_case"]) == len(d4["baseline_best_case"]) == 1 and d4["pass"] is False
    cand = [spec(r={"M4": PS, "M5": NS})] * 3
    assert _check(tmp_path / "b", capsys, cand, base)[0]["measures"]["D4"]["pass"] is True


def test_parked_rows_are_reported_but_never_counted(tmp_path, capsys):
    cand = [spec(r={"M1": PS, "M2": NS})] * 3
    results, out = _check(tmp_path, capsys, cand)
    d4 = results["measures"]["D4"]
    assert d4["candidate_as_scored"] == [] and d4["pass"] is False
    assert d4["parked"]["candidate"] == {"M1": [PS, PS, PS], "M2": [NS, NS, NS]}
    assert "parked, reported only (candidate): M1: partially_supported" in out


# --- D5 catches --------------------------------------------------------------------------------

def test_a_catch_is_lost_at_two_of_three_not_at_one(tmp_path, capsys):
    one = _check(tmp_path, capsys, [spec(r={"M4": PS, "H1": SUP}), spec(r={"M4": PS}), spec(r={"M4": PS})])[0]
    assert one["measures"]["D5"]["candidate_worst_case_lost"] == [] and one["measures"]["D5"]["pass"] is True
    two = _check(tmp_path / "b", capsys, [spec(r={"M4": PS, "H1": SUP}), spec(r={"M4": PS, "H1": SUP}), spec(r={"M4": PS})])[0]
    assert two["measures"]["D5"]["candidate_worst_case_lost"] == ["H1"] and two["measures"]["D5"]["pass"] is False


def test_the_other_row_is_reported_only_and_in_no_total(tmp_path, capsys):
    cand = [spec(r={"M4": PS, "O1": NS})] * 3
    results, out = _check(tmp_path, capsys, cand)
    d5 = results["measures"]["D5"]
    assert d5["catches"] == list(REALS) and d5["pass"] is True
    assert d5["other_reported_only"]["candidate"] == {"O1": [NS, NS, NS]}
    assert "reported only, in no total (candidate): O1: not_supported" in out


# --- D6 false rejections -----------------------------------------------------------------------

def test_false_rejections_use_the_effective_status_and_ignore_rows_without_a_claim(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, s={"S1": PS, "S2": "grounded_away", "S3": NS})] * 3
    d6 = _check(tmp_path, capsys, cand)[0]["measures"]["D6"]
    assert d6["candidate_as_scored"] == ["S1", "S2", "S3"]          # grounded away -> not_supported; S5 never counts
    assert (d6["s_rows"], d6["matched"], d6["no_claim"]) == (6, 5, 1)
    assert d6["pass"] is False                                      # 3 > the ceiling of 2


def test_false_rejections_need_two_of_three_folders(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, s={"S1": PS}), spec(r={"M4": PS}), spec(r={"M4": PS})]
    assert _check(tmp_path, capsys, cand)[0]["measures"]["D6"]["candidate_as_scored"] == []


def test_false_rejections_must_not_exceed_the_baseline_nor_the_ceiling(tmp_path, capsys):
    two = [spec(r={"M4": PS}, s={"S1": PS, "S2": PS})] * 3
    assert _check(tmp_path, capsys, two, two)[0]["measures"]["D6"]["pass"] is True                 # 2 <= 2 and <= 2
    one_base = [spec(s={"S1": PS})] * 3
    assert _check(tmp_path / "b", capsys, two, one_base)[0]["measures"]["D6"]["pass"] is False     # 2 > baseline 1


def test_fixing_the_shared_claim_also_counts_as_a_false_rejection_of_its_s_row(tmp_path, capsys):
    cand = [spec(r={"M3": PS})] * 3          # M3 is a target AND S0's claim
    results, _ = _check(tmp_path, capsys, cand)
    assert results["measures"]["D4"]["candidate_as_scored"] == ["M3"]
    assert results["measures"]["D6"]["candidate_as_scored"] == ["S0"]


# --- D7 golden ---------------------------------------------------------------------------------

def test_golden_counts_are_voted_per_row(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, g={"N1": "SUP"}), spec(r={"M4": PS}, g={"N1": "SUP", "P1": "GROUNDED"}), spec(r={"M4": PS})]
    d7 = _check(tmp_path, capsys, cand)[0]["measures"]["D7"]
    assert d7["candidate_refusals_as_scored"] == ["N2", "N3"]       # N1 affirmed in 2 of 3
    assert d7["candidate_hits_as_scored"] == ["P1", "P2", "P3"]     # P1 false-rejected in only 1 of 3
    assert d7["pass"] is True


def test_golden_thresholds(tmp_path, capsys, monkeypatch):
    cand = [spec(r={"M4": PS}, g={"N1": "SUP", "N2": "SUP"})] * 3
    assert _check(tmp_path, capsys, cand)[0]["measures"]["D7"]["pass"] is False          # 1 refusal < 2
    cand = [spec(r={"M4": PS}, g={"P1": "PS", "P2": "PS"})] * 3
    assert _check(tmp_path / "b", capsys, cand)[0]["measures"]["D7"]["pass"] is False    # 1 hit < 2


def test_a_negative_refused_by_grounding_counts_as_refused(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, g={"N1": "GROUNDED"})] * 3
    assert "N1" in _check(tmp_path, capsys, cand)[0]["measures"]["D7"]["candidate_refusals_as_scored"]


def test_grounding_negative_fails_when_the_baseline_refuses_and_the_candidate_wrongly_affirms(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, g={"N1": "SUP"})] * 3
    results, out = _check(tmp_path, capsys, cand)
    gn = results["measures"]["D7_grounding_negative"]
    assert gn == {"failing_rows": ["N1"], "pass": False}
    assert results["overall"] == "FAIL" and "grounding-negative: FAIL  failing rows ['N1']" in out


def test_grounding_negative_needs_the_baseline_to_have_refused_it(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, g={"N1": "SUP"})] * 3
    base = [spec(g={"N1": "SUP"})] * 3
    assert _check(tmp_path, capsys, cand, base)[0]["measures"]["D7_grounding_negative"]["pass"] is True


# --- D8 / overall ------------------------------------------------------------------------------

def test_needs_review_is_printed_as_zero_with_no_code_check(tmp_path, capsys):
    results, out = _check(tmp_path, capsys, GOOD)
    assert "D8 Needs review: 0 (no code check in this run)" in out
    assert results["needs_review"] == "0 (no code check in this run)"


def test_all_marks_passing_gives_overall_pass_and_exit_code_zero(tmp_path, capsys):
    results, out = _check(tmp_path, capsys, GOOD)
    assert results["overall"] == "PASS" and "Overall: PASS" in out
    assert all(results["measures"][k]["pass"] for k in ("D4", "D5", "D6", "D7", "D7_grounding_negative"))


def test_a_failing_mark_still_exits_zero_like_score_screen(tmp_path, capsys):
    results, _ = _check(tmp_path, capsys)              # nothing fixed: D4 fails
    assert results["overall"] == "FAIL"


# --- D9 fallback-served audits -----------------------------------------------------------------

def test_a_fallback_served_fix_counts_as_not_fixed_for_the_candidate(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, fb=["M4"]), spec(r={"M4": PS}, fb=["M4"]), spec(r={"M4": PS})]
    results, out = _check(tmp_path, capsys, cand)
    d4 = results["measures"]["D4"]
    assert d4["candidate_as_scored"] == ["M4"] and d4["candidate_worst_case"] == [] and d4["pass"] is False
    assert "as scored 1/3 ['M4']; worst case 0/3 []" in out


def test_a_fallback_served_catch_counts_as_lost_for_the_candidate(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, fb=["H1"]), spec(r={"M4": PS}, fb=["H1"]), spec(r={"M4": PS})]
    d5 = _check(tmp_path, capsys, cand)[0]["measures"]["D5"]
    assert d5["candidate_as_scored_lost"] == [] and d5["candidate_worst_case_lost"] == ["H1"] and d5["pass"] is False


def test_a_fallback_served_s_row_counts_as_a_false_rejection_for_the_candidate(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, fb=["S1"]), spec(r={"M4": PS}, fb=["S1"]), spec(r={"M4": PS})]
    d6 = _check(tmp_path, capsys, cand)[0]["measures"]["D6"]
    assert d6["candidate_as_scored"] == [] and d6["candidate_worst_case"] == ["S1"] and d6["pass"] is False


def test_a_fallback_served_golden_negative_and_positive_count_against_the_candidate(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sfc, "MIN_GOLDEN_POSITIVES", 3)
    cand = [spec(r={"M4": PS}, fb=["N1", "P1"]), spec(r={"M4": PS}, fb=["N1", "P1"]), spec(r={"M4": PS})]
    results, _ = _check(tmp_path, capsys, cand)
    d7 = results["measures"]["D7"]
    assert d7["candidate_refusals_as_scored"] == ["N1", "N2", "N3"] and d7["candidate_refusals_worst_case"] == ["N2", "N3"]
    assert d7["candidate_hits_as_scored"] == ["P1", "P2", "P3"] and d7["candidate_hits_worst_case"] == ["P2", "P3"]
    assert d7["pass"] is False                                              # 2 hits < the (patched) 3
    assert results["measures"]["D7_grounding_negative"]["failing_rows"] == ["N1"]   # wrongly affirmed in the worst case


def test_the_baseline_gets_its_best_case_for_fallback_served_claims(tmp_path, capsys):
    base = [spec(fb=["M4", "S1", "N1", "P1"], r={"M4": SUP}, s={"S1": PS}, g={"N1": "SUP", "P1": "PS"})] * 2 + [spec()]
    cand = [spec(r={"M4": PS})] * 3
    results, _ = _check(tmp_path, capsys, cand, base)
    m = results["measures"]
    assert m["D4"]["baseline_as_scored"] == [] and m["D4"]["baseline_best_case"] == ["M4"]
    assert m["D4"]["pass"] is False                      # 1 >= 1 + 1 is false: the baseline's best case raises the bar
    assert m["D6"]["baseline_as_scored"] == ["S1"] and m["D6"]["baseline_best_case"] == []
    d7 = m["D7"]
    assert "N1" not in d7["baseline_refusals_as_scored"] and "N1" in d7["baseline_refusals_best_case"]
    assert "P1" not in d7["baseline_hits_as_scored"] and "P1" in d7["baseline_hits_best_case"]


def test_parked_and_other_rows_are_never_substituted(tmp_path, capsys):
    cand = [spec(r={"M1": PS, "O1": NS, "M4": PS}, fb=["M1", "O1"])] * 3
    results, _ = _check(tmp_path, capsys, cand)
    rows = {(c["row_id"]): c for c in results["per_claim"] if c["arm"] == "candidate" and c["set"] == "dev"}
    for rid in ("M1", "O1"):
        assert rows[rid]["fallback_served"] is True and rows[rid]["substituted"] is False
        assert rows[rid]["applied"] == rows[rid]["as_scored"]


def test_the_shared_claim_is_substituted_per_row_and_role(tmp_path, capsys):
    cand = [spec(r={"M3": PS, "M4": PS}, fb=["M3"])] * 3
    results, _ = _check(tmp_path, capsys, cand)
    per_claim = {(c["row_id"], c["folder"][-1]): c for c in results["per_claim"] if c["arm"] == "candidate" and c["set"] == "dev"}
    target, s_row = per_claim[("M3", "1")], per_claim[("S0", "1")]
    # one claim, served by the fallback model, read by two rows: each is substituted by its own role's table
    assert (target["role"], target["as_scored"], target["applied"], target["substituted"]) == ("target", PS, SUP, True)
    assert (s_row["role"], s_row["as_scored"], s_row["applied"], s_row["substituted"]) == ("s_row", PS, NS, True)
    assert target["fallback_served"] is True and s_row["fallback_served"] is True
    d4, d6 = results["measures"]["D4"], results["measures"]["D6"]
    assert d4["candidate_as_scored"] == ["M3", "M4"] and d4["candidate_worst_case"] == ["M4"]
    assert d6["candidate_as_scored"] == ["S0"] and d6["candidate_worst_case"] == ["S0"]


def test_per_claim_records_carry_served_model_and_flags_and_folders_get_counts(tmp_path, capsys):
    cand = [spec(r={"M4": PS}, fb=["M4", "S1"])] + [spec(r={"M4": PS})] * 2
    results, out = _check(tmp_path, capsys, cand)
    row = next(c for c in results["per_claim"]
               if c["arm"] == "candidate" and c["set"] == "dev" and c["row_id"] == "M4" and c["folder"].endswith("cand_dev_1"))
    assert row == {"arm": "candidate", "set": "dev", "row_id": "M4", "role": "target", "folder": row["folder"],
                   "as_scored": PS, "applied": SUP, "served_model": FALLBACK, "fallback_served": True, "substituted": True}
    counts = next(f for f in results["fallback"] if f["arm"] == "dev candidate" and f["folder"].endswith("cand_dev_1"))
    assert counts["fallback_served_claims"] == 2 and counts["substitutions_applied"] == 2 and counts["outcomes_changed"] == 2
    clean = next(f for f in results["fallback"] if f["arm"] == "dev candidate" and f["folder"].endswith("cand_dev_2"))
    assert clean["fallback_served_claims"] == 0 and clean["outcomes_changed"] == 0
    assert "Fallback-served audits (D9)" in out


# --- D10 cost ----------------------------------------------------------------------------------

def test_cost_covers_audit_calls_only_each_priced_at_its_serving_model(tmp_path, capsys):
    world = World(tmp_path, GOOD)
    records = [
        _audit_record("p", 0, CAND, prompt=1000, cached=200, output=100, thought=400),
        _audit_record("p", 1, FALLBACK, prompt=2000, cached=0, output=200, thought=0),
        _audit_record("p", 0, CAND, prompt=999999, is_audit=False),      # the structurer: not counted
    ]
    _write_summary(world.dev_cand[0], CAND_CFG, records)
    code, _ = world.run(capsys)
    assert code == 0
    cost = next(c for c in world.results()["cost"] if c["folder"].endswith("cand_dev_1"))
    # call 1 at gemini-3.8-flash: 800 in x 0.75 + 200 cached x 0.075 + 500 out x 3.75 = USD 0.00249
    # call 2 at gemini-3.1-flash-lite: 2000 in x 0.25 + 200 out x 1.50 = USD 0.0008
    expected_total_inr = (0.00249 + 0.0008) * 100
    assert cost["audit_calls"] == 2
    assert cost["mean_prompt_tokens"] == 1500 and cost["mean_cached_tokens"] == 100
    assert cost["mean_output_tokens"] == 150 and cost["mean_thought_tokens"] == 200
    assert cost["audit_inr_total"] == pytest.approx(expected_total_inr, abs=0.01)
    assert cost["audit_inr_per_claim"] == pytest.approx(expected_total_inr / 2, abs=0.001)


# --- INVALID (D11) -----------------------------------------------------------------------------

def _drop_run_config(folder):
    summary = json.loads((folder / "_summary.json").read_text("utf-8"))
    summary.pop("run_config")
    (folder / "_summary.json").write_text(json.dumps(summary), encoding="utf-8")


def _edit_summary(folder, **changes):
    summary = json.loads((folder / "_summary.json").read_text("utf-8"))
    summary.update(changes)
    (folder / "_summary.json").write_text(json.dumps(summary), encoding="utf-8")


def _edit_claim(path, **changes):
    data = json.loads(path.read_text("utf-8"))
    data["claims"][0].update(changes)
    path.write_text(json.dumps(data), encoding="utf-8")


def _del_key(path, key):
    data = json.loads(path.read_text("utf-8"))
    del data["claims"][0][key]
    path.write_text(json.dumps(data), encoding="utf-8")


INVALID_CASES = [
    ("folder missing", lambda w, mp: shutil.rmtree(w.dev_cand[1]), "cand_dev_2: folder missing"),
    ("no summary", lambda w, mp: (w.dev_base[0] / "_summary.json").unlink(), "base_dev_1: no _summary.json"),
    ("summary unreadable", lambda w, mp: (w.gold_cand[0] / "_summary.json").write_text("{", encoding="utf-8"), "unreadable"),
    ("status not ok", lambda w, mp: _edit_summary(w.dev_cand[0], status="VOID_CAP_HIT"), "status is 'VOID_CAP_HIT', not OK"),
    ("no run_config", lambda w, mp: _drop_run_config(w.dev_cand[0]), "no run_config in _summary.json"),
    ("config differs within an arm",
     lambda w, mp: _edit_summary(w.dev_cand[1], run_config={**CAND_CFG, "thinking_level": "medium"}),
     "run_config.thinking_level differs"),
    ("different backends", lambda w, mp: [_edit_summary(d, run_config={**BASE_CFG, "backend": "aistudio"}) for d in w.dev_base],
     "run_config.backend differs between dev candidate"),
    ("dev and golden candidate differ",
     lambda w, mp: [_edit_summary(d, run_config={**CAND_CFG, "auditor_model": "gemini-3.9-flash"}) for d in w.gold_cand],
     "differs between dev candidate"),
    ("no audit_model_served", lambda w, mp: _del_key(w.dev_cand[0] / "paper-M4.json", "audit_model_served"),
     "M4 claim lacks audit_model_served"),
    ("s row fixture missing", lambda w, mp: (w.dev_base[2] / "paper-S1.json").unlink(), "S1 FIXTURE_MISSING"),
    ("bad label", lambda w, mp: _edit_claim(w.dev_cand[0] / "paper-M4.json", label="maybe"), "label 'maybe' is not a replay label"),
    ("s row sizes", lambda w, mp: mp.setattr(sfc, "EXPECTED_S_ROWS", 7), "S rows: 6 rows with 5 matched, expected 7 with 5"),
    ("golden sizes", lambda w, mp: mp.setattr(sfc, "EXPECTED_GOLDEN_NEGATIVES", 4),
     "golden matrix: 3 negatives and 3 positives, expected 4 and 3"),
    ("golden folder not marked", lambda w, mp: (w.gold_cand[0] / "arxiv-g1.json").write_text(json.dumps(
        {"header": {"replay": {"set": "dev"}}, "claims": [], "matches": []}), encoding="utf-8"),
     "not a --set golden replay"),
    ("golden claim not replayed", lambda w, mp: _drop_golden_claim(w.gold_base[1]), "does not cover frozen-matched claims [2]"),
    ("unpriced model", lambda w, mp: _edit_summary(w.dev_cand[0], records=[_audit_record("p", 0, "gemini-9-flash")]), "no price on file"),
    ("no audit records", lambda w, mp: _edit_summary(w.dev_cand[0], records=[]), "no audit call records"),
]


def _drop_golden_claim(folder):
    path = folder / "arxiv-g1.json"
    data = json.loads(path.read_text("utf-8"))
    data["claims"] = data["claims"][:2]
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.mark.parametrize("name, mutate, message", INVALID_CASES, ids=[c[0] for c in INVALID_CASES])
def test_invalid_cases_print_the_reason_exit_one_and_score_nothing(tmp_path, capsys, monkeypatch, name, mutate, message):
    world = World(tmp_path, GOOD)
    mutate(world, monkeypatch)
    code, out = world.run(capsys)
    assert code == 1, out
    assert f"INVALID: " in out and message in out
    assert "D4 fixes" not in out and "Overall" not in out
    assert not world.json_out.exists()


def test_a_matched_s_row_that_does_not_expect_supported_is_invalid(tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(sfc, "resolve_adjudicated_rows",
                        lambda *a, row_type="R", **k: _r_rows() if row_type == "R" else _s_rows(expected=PS))
    code, out = World(tmp_path, GOOD).run(capsys)
    assert code == 1 and "whose expected label is not supported" in out


def test_json_out_inside_a_fixture_folder_is_refused(tmp_path, capsys):
    world = World(tmp_path, GOOD)
    world.json_out = world.dev_cand[0] / "results.json"
    code, out = world.run(capsys)
    assert code == 1 and "--json-out must not be inside a fixture folder" in out and not world.json_out.exists()


def test_each_arm_needs_exactly_three_folders(tmp_path, capsys):
    world = World(tmp_path, GOOD)
    code, out = world.run(capsys, dev_baseline=world.dev_base[:2])
    assert code == 1 and "dev baseline needs exactly 3 folders, got 2" in out


def test_all_invalid_reasons_are_listed_once(tmp_path, capsys):
    world = World(tmp_path, GOOD)
    _edit_summary(world.dev_cand[0], status="VOID_CAP_HIT")
    shutil.rmtree(world.gold_base[2])
    code, out = world.run(capsys)
    assert code == 1
    assert out.count("cand_dev_1: _summary.json status is") == 1 and out.count("base_gold_3: folder missing") == 1


# --- the CLI and the self-check against score_screen --------------------------------------------

def test_main_requires_exactly_three_folders_per_arm(tmp_path, monkeypatch):
    world = World(tmp_path, GOOD)
    argv = ["score_full_check", "--matrix-path", str(world.matrix)]
    for flag, dirs in (("--dev-candidate", world.dev_cand[:2]), ("--dev-baseline", world.dev_base),
                       ("--golden-candidate", world.gold_cand), ("--golden-baseline", world.gold_base)):
        argv += [a for d in dirs for a in (flag, str(d))]
    monkeypatch.setattr(sys, "argv", argv)
    with pytest.raises(SystemExit) as exc:
        sfc.main()
    assert exc.value.code == 2


def test_main_exit_codes(tmp_path, monkeypatch):
    world = World(tmp_path, GOOD)

    def argv(dev_cand):
        out = ["score_full_check", "--matrix-path", str(world.matrix)]
        for flag, dirs in (("--dev-candidate", dev_cand), ("--dev-baseline", world.dev_base),
                           ("--golden-candidate", world.gold_cand), ("--golden-baseline", world.gold_base)):
            out += [a for d in dirs for a in (flag, str(d))]
        return out

    monkeypatch.setattr(sys, "argv", argv(world.dev_cand))
    with pytest.raises(SystemExit) as ok:
        sfc.main()
    assert ok.value.code == 0
    monkeypatch.setattr(sys, "argv", argv([world.dev_cand[0], world.dev_cand[1], tmp_path / "nope"]))
    with pytest.raises(SystemExit) as bad:
        sfc.main()
    assert bad.value.code == 1


R_LABEL_CASES = [
    {},                                                                  # nothing fixed, nothing lost
    {"M3": [PS, PS, SUP], "M4": [NS, SUP, SUP], "M5": [NS, NS, PS]},     # 2-of-3 boundary on the targets
    {"M1": [PS, PS, PS], "M2": [NS, NS, NS]},                            # parked rows: voted by score_screen, not counted
    {"H1": [SUP, SUP, NS], "H2": [SUP, NS, NS]},                         # one catch lost, one not
    {"M3": [PS, PS, PS], "M4": [NS, NS, NS], "H1": [SUP, SUP, SUP], "H2": [PS, PS, NS], "O1": [NS, NS, NS]},
]


@pytest.mark.parametrize("changes", R_LABEL_CASES)
def test_the_refusal_row_votes_equal_score_screens_on_the_same_folders(tmp_path, changes):
    """The 18-row check on invented folders: the targets fixed and catches lost computed here equal
    score_screen.build_results' totals, row for row."""
    base = {**{m: [SUP] * 3 for m in MISSES}, **{h: [NS] * 3 for h in REALS}, "O1": [SUP] * 3}
    base.update(changes)
    dirs = []
    for i in range(3):
        folder = tmp_path / f"rep_{i + 1}"
        _write_dev(folder, spec(r={rid: base[rid][i] for rid in R_IDS}), BASE_CFG)
        dirs.append(folder)
    invalid, labels, claims, configs = score_screen.collect(_r_rows(), dirs)
    assert invalid == []
    expected = score_screen.build_results(dirs, labels, claims, configs)["totals"]
    mine = sfc.r_votes(labels)
    assert mine["targets_fixed"] == expected["auditor_targets_caught_ids"]
    assert mine["catches_lost"] == expected["real_hits_lost_ids"]
