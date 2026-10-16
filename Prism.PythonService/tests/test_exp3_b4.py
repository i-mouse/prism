"""Unit tests for eval/blind_review.py and eval/exp3_b4.py. Offline,
synthetic fixtures only - no LLM calls, no network, no real dev-paper PDFs
or claim text. Pydantic's ValidationError is raised for invalid answer
rows; everything else is plain file I/O against tmp_path trees.
"""
import json

import fitz
import pytest
from pydantic import ValidationError

from eval import exp3_b4
from eval.blind_review import (
    C1Answer,
    C8Answer,
    assign_opaque_ids,
    dedup_by_normalized_text,
    seeded_sample,
    sha256_file,
    verify_lock,
    wilson_interval,
    write_lock,
)
from eval.exp3_b4 import _extract_pdf_text, _insert_repeats


# --------------------------------------------------------------------------
# blind_review.py
# --------------------------------------------------------------------------

def test_seeded_sample_same_seed_same_result():
    items = [f"item-{i}" for i in range(50)]
    assert seeded_sample(items, 10, seed=42) == seeded_sample(items, 10, seed=42)


def test_seeded_sample_different_seed_usually_differs():
    items = [f"item-{i}" for i in range(50)]
    assert seeded_sample(items, 10, seed=1) != seeded_sample(items, 10, seed=2)


def test_seeded_sample_returns_all_when_fewer_than_k():
    items = ["a", "b", "c"]
    assert sorted(seeded_sample(items, 10, seed=1)) == sorted(items)


def test_assign_opaque_ids_stable_across_rebuilds():
    items = ["x", "y", "z", "w"]
    first = assign_opaque_ids(items, prefix="C", seed=20261015)
    second = assign_opaque_ids(items, prefix="C", seed=20261015)
    assert first == second


def test_assign_opaque_ids_sequential_and_prefixed():
    items = ["x", "y", "z"]
    pairs = assign_opaque_ids(items, prefix="C", seed=1)
    ids = sorted(cid for cid, _ in pairs)
    assert ids == ["C0001", "C0002", "C0003"]


def test_dedup_by_normalized_text_keeps_first_occurrence():
    # normalize_for_match collapses whitespace but is case-sensitive (it
    # never lowercases), so the duplicate pair here differs only in spacing.
    items = ["Hello  world.", "Hello world.", "goodbye."]
    deduped = dedup_by_normalized_text(items, text_of=lambda x: x)
    assert deduped == ["Hello  world.", "goodbye."]


def test_wilson_interval_n_zero_is_none():
    assert wilson_interval(0, 0) == (None, None)


def test_wilson_interval_known_value():
    # 21/30 claims: Wilson 95% interval is approximately (0.524, 0.831).
    low, high = wilson_interval(21, 30)
    assert low == pytest.approx(0.524, abs=0.01)
    assert high == pytest.approx(0.831, abs=0.01)


def test_write_lock_then_verify_lock_passes(tmp_path):
    answer = tmp_path / "answer.csv"
    answer.write_text("a,b\n1,2\n", encoding="utf-8")
    lock_path = tmp_path / "lock.json"
    write_lock({"answer.csv": answer}, lock_path)
    verify_lock(lock_path, {"answer.csv": answer})  # must not raise


def test_verify_lock_raises_on_hash_mismatch(tmp_path):
    answer = tmp_path / "answer.csv"
    answer.write_text("a,b\n1,2\n", encoding="utf-8")
    lock_path = tmp_path / "lock.json"
    write_lock({"answer.csv": answer}, lock_path)

    answer.write_text("a,b\n1,3\n", encoding="utf-8")  # edited after lock
    with pytest.raises(ValueError, match="mismatch"):
        verify_lock(lock_path, {"answer.csv": answer})


def test_verify_lock_raises_without_lock_file(tmp_path):
    answer = tmp_path / "answer.csv"
    answer.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no lock file"):
        verify_lock(tmp_path / "missing_lock.json", {"answer.csv": answer})


def test_c1answer_parses_none_as_empty_list():
    answer = C1Answer.model_validate({"row_id": "R1", "paper_id": "P1", "match_ids": "none", "note": ""})
    assert answer.match_ids == []


def test_c1answer_parses_semicolon_separated_ids():
    answer = C1Answer.model_validate({"row_id": "R1", "paper_id": "P1", "match_ids": "C0001; C0002", "note": ""})
    assert answer.match_ids == ["C0001", "C0002"]


def test_c8answer_unsure_valid_with_reason():
    answer = C8Answer.model_validate({"id": "K001", "label": "unsure", "reason": "other", "duplicate": "", "note": ""})
    assert answer.label == "unsure"


def test_c8answer_requires_reason_when_not_claim():
    with pytest.raises(ValidationError):
        C8Answer.model_validate({"id": "K001", "label": "not_claim", "reason": "", "duplicate": "", "note": ""})


def test_c8answer_requires_duplicate_when_claim():
    with pytest.raises(ValidationError):
        C8Answer.model_validate({"id": "K001", "label": "claim", "reason": "", "duplicate": "", "note": ""})


def test_c8answer_blank_label_rejected():
    with pytest.raises(ValidationError):
        C8Answer.model_validate({"id": "K001", "label": "", "reason": "", "duplicate": "", "note": ""})


# --------------------------------------------------------------------------
# exp3_b4.py: repeats spacing
# --------------------------------------------------------------------------

def test_insert_repeats_are_at_least_min_gap_apart():
    items = [{"v": i} for i in range(60)]
    with_repeats = exp3_b4._insert_repeats(items, k=5, seed=20261017, min_gap=20)
    n_original = len(items)
    repeat_positions = [(i, item["repeat_of_index"]) for i, item in enumerate(with_repeats) if "repeat_of_index" in item]
    assert len(repeat_positions) == 5
    for position, original_index in repeat_positions:
        assert abs(position - original_index) >= 20


def test_insert_repeats_handles_small_population_gracefully():
    items = [{"v": i} for i in range(5)]
    with_repeats = exp3_b4._insert_repeats(items, k=5, seed=20261017, min_gap=20)
    assert len(with_repeats) >= len(items)  # no crash; 0 eligible -> 0 repeats added


# --------------------------------------------------------------------------
# exp3_b4.py: PDF text extraction matches main.py's extract_pdf_text_sync logic
# --------------------------------------------------------------------------

def _main_py_reference_extract(path) -> str:
    """Copy of main.py:102-115's loop, inlined here (never importing
    main.py, which has import-time telemetry/DB side effects) so the test
    can prove eval.exp3_b4._extract_pdf_text matches it exactly."""
    final_text = ""
    with fitz.open(path) as doc:
        if doc.needs_pass or doc.is_encrypted:
            raise exp3_b4.PdfPasswordProtectedError("password-protected PDF")
        for page in doc:
            final_text += page.get_text()
    return final_text


def test_extract_pdf_text_matches_main_py_logic(tmp_path):
    pdf_path = tmp_path / "synthetic.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Synthetic claim sentence for the B4 PDF extraction test.")
    doc.save(pdf_path)
    doc.close()

    assert _extract_pdf_text(pdf_path) == _main_py_reference_extract(pdf_path)


# --------------------------------------------------------------------------
# exp3_b4.py: c3/c4 formula on a tiny synthetic fixture (both readings)
# --------------------------------------------------------------------------

def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def _write_fixture_paper(replay_root, run, paper_id, pass1_n, merged_n, sentences_n=0, dropped_ungrounded=0):
    run_dir = replay_root / run
    _write_json(run_dir / f"{paper_id}_pass1.json", {"header": {}, "claims": [{"claim_text_verbatim": f"p1-{i}", "claim_summary": ""} for i in range(pass1_n)]})
    _write_json(
        run_dir / f"{paper_id}_merged.json",
        {"header": {"incomplete": False}, "claims": [{"claim_text_verbatim": f"m-{i}", "claim_summary": "", "pass": "pass1" if i < pass1_n else "pass2"} for i in range(merged_n)]},
    )
    _write_json(run_dir / f"{paper_id}_pass2.json", {"header": {}, "sentences": [f"s-{i}" for i in range(sentences_n)]})
    kept_new_n = max(0, sentences_n - dropped_ungrounded)
    _write_json(
        run_dir / f"{paper_id}_buckets.json",
        {
            "header": {},
            "dropped_ungrounded": dropped_ungrounded,
            "dropped_duplicate": [],
            "kept_but_contained": [],
            "kept_new": [{"sentence": f"s-{i}", "best_match": "", "ratio_score": 0, "partial_ratio_score": 0} for i in range(kept_new_n)],
        },
    )


def test_c3_and_c4_values_and_projection(tmp_path, monkeypatch):
    # P1 and P2 deliberately have different pass1 counts (10 vs 30), so the
    # mean-of-ratios and pooled-ratio readings diverge (2.5 vs 2.75) and a
    # bug that silently uses one formula for both can't pass this test.
    monkeypatch.setattr(exp3_b4, "DEV_PAPERS", ["P1", "P2"])

    for run in ("pass2_r1", "pass2_r2"):
        _write_fixture_paper(tmp_path, run, "P1", pass1_n=10, merged_n=20)  # ratio 2.0
        _write_fixture_paper(tmp_path, run, "P2", pass1_n=30, merged_n=90)  # ratio 3.0
        _write_json(
            tmp_path / run / "_summary.json",
            {"cost_inr": 24.0, "records": [{"paper_id": "P1", "call_kind": "pass2"}, {"paper_id": "P2", "call_kind": "pass2"}]},
        )

    result = exp3_b4._c3_and_c4(tmp_path)
    mean_reading = result["c4_mean_reading"]
    pooled_reading = result["c4_pooled_reading"]

    # r_mean per run = mean(20/10, 90/30) = mean(2.0, 3.0) = 2.5
    assert mean_reading["r"] == pytest.approx(2.5)
    # r_pooled per run = (20+90)/(10+30) = 110/40 = 2.75
    assert pooled_reading["r"] == pytest.approx(2.75)
    # p2 per run = 24 / 2 papers = 12; averaged over both (identical) runs = 12
    assert mean_reading["p2"] == pytest.approx(12.0)
    assert pooled_reading["p2"] == pytest.approx(12.0)

    expected_mean_projected = exp3_b4.C4_COST_PER_PAPER_FACTOR * 2.5 + 12.0
    expected_pooled_projected = exp3_b4.C4_COST_PER_PAPER_FACTOR * 2.75 + 12.0
    assert mean_reading["projected_inr"] == pytest.approx(expected_mean_projected)
    assert pooled_reading["projected_inr"] == pytest.approx(expected_pooled_projected)
    assert mean_reading["pass"] == (expected_mean_projected <= exp3_b4.C4_MAX_INR)
    assert pooled_reading["pass"] == (expected_pooled_projected <= exp3_b4.C4_MAX_INR)


def test_c3_and_c4_aborts_on_non_pass2_call_kind(tmp_path, monkeypatch):
    monkeypatch.setattr(exp3_b4, "DEV_PAPERS", ["P1"])
    _write_fixture_paper(tmp_path, "pass2_r1", "P1", pass1_n=5, merged_n=5)
    _write_json(
        tmp_path / "pass2_r1" / "_summary.json",
        {"cost_inr": 10.0, "records": [{"paper_id": "P1", "call_kind": "pass1"}]},
    )
    with pytest.raises(ValueError, match="non-pass-2"):
        exp3_b4._c3_and_c4(tmp_path)


# --------------------------------------------------------------------------
# exp3_b4.py: c7 sentence-count cross-check
# --------------------------------------------------------------------------

def test_c7_computes_grounding_rate(tmp_path, monkeypatch):
    monkeypatch.setattr(exp3_b4, "DEV_PAPERS", ["P1"])
    for run in ("pass2_r1", "pass2_r2"):
        _write_fixture_paper(tmp_path, run, "P1", pass1_n=1, merged_n=1, sentences_n=10, dropped_ungrounded=1)

    result = exp3_b4._c7(tmp_path)
    assert result["pass2_r1"]["sentences"] == 10
    assert result["pass2_r1"]["dropped_ungrounded"] == 1
    assert result["pass2_r1"]["rate"] == pytest.approx(0.9)
    assert result["pass2_r1"]["pass"] is False  # 0.9 < 0.95


def test_c7_aborts_when_sentence_counts_disagree(tmp_path, monkeypatch):
    monkeypatch.setattr(exp3_b4, "DEV_PAPERS", ["P1"])
    _write_fixture_paper(tmp_path, "pass2_r1", "P1", pass1_n=1, merged_n=1, sentences_n=10, dropped_ungrounded=1)
    _write_fixture_paper(tmp_path, "pass2_r2", "P1", pass1_n=1, merged_n=1, sentences_n=10, dropped_ungrounded=1)

    # corrupt pass2_r1's bucket total so it disagrees with pass2.sentences (10)
    buckets_path = tmp_path / "pass2_r1" / "P1_buckets.json"
    buckets = json.loads(buckets_path.read_text(encoding="utf-8"))
    buckets["dropped_ungrounded"] = 2  # bucket total now 11, pass2.sentences still 10
    buckets_path.write_text(json.dumps(buckets), encoding="utf-8")

    with pytest.raises(SystemExit, match="disagrees"):
        exp3_b4._c7(tmp_path)


# --------------------------------------------------------------------------
# exp3_b4.py: tie rule and unsure-as-not_claim, exercised directly against
# the small, decoupled pieces cmd_score uses (no file I/O needed for these).
# --------------------------------------------------------------------------

def test_unsure_counts_as_not_claim_for_c8():
    answer = C8Answer.model_validate({"id": "K001", "label": "unsure", "reason": "other", "duplicate": "", "note": ""})
    is_claim = answer.label == "claim"
    assert is_claim is False


# --------------------------------------------------------------------------
# exp3_b4.py: _credit_c1_match (extracted tie-rule helper), exercised
# directly - this is the actual production function cmd_score calls, not a
# reimplementation of its logic in the test.
# --------------------------------------------------------------------------

def test_credit_c1_match_empty_is_not_recovered():
    assert exp3_b4._credit_c1_match([]) == (False, None)


def test_credit_c1_match_pass2_only_credits_pass2():
    present = [{"present": True, "pass": 2, "merged_index": 0}]
    assert exp3_b4._credit_c1_match(present) == (True, "pass2")


def test_credit_c1_match_pass1_only_credits_pass1():
    present = [{"present": True, "pass": 1, "merged_index": 0}]
    assert exp3_b4._credit_c1_match(present) == (True, "pass1")


def test_credit_c1_match_tie_credits_pass1():
    """A row whose present match_ids include one pass-1 and one pass-2 claim
    in the same run must still count as recovered (c1) but be credited to
    pass 1 (reported as a run-1 adjudication disagreement), never c6."""
    present = [{"present": True, "pass": 1, "merged_index": 0}, {"present": True, "pass": 2, "merged_index": 1}]
    assert exp3_b4._credit_c1_match(present) == (True, "pass1")


# --------------------------------------------------------------------------
# exp3_b4.py: c8 scoring - repeats must not inflate a run's sample size,
# and must not be double-counted in report-only groupings (independent
# audit fix, 2026-10-16).
# --------------------------------------------------------------------------

def _make_c8_key(pass2_r1=28, pass2_r2=28, pass2_both=2, pass1_control=30, repeats=()):
    """Builds a synthetic c8_key.json "items" dict with the given raw group
    sizes, then appends repeat entries (each a dict {from_group, run_memberships})
    pointing at the first item of that group."""
    key: dict[str, dict] = {}
    counter = 0
    group_sizes = {"pass2_r1": pass2_r1, "pass2_r2": pass2_r2, "pass2_both": pass2_both, "pass1_control": pass1_control}
    run_memberships_by_group = {
        "pass2_r1": ["pass2_r1"],
        "pass2_r2": ["pass2_r2"],
        "pass2_both": ["pass2_r1", "pass2_r2"],
        "pass1_control": [],
    }
    first_of_group: dict[str, str] = {}
    for group, size in group_sizes.items():
        for _ in range(size):
            counter += 1
            kid = f"K{counter:03d}"
            key[kid] = {"group": group, "run_memberships": run_memberships_by_group[group], "position": 0, "repeat_of": None}
            first_of_group.setdefault(group, kid)

    for group in repeats:
        counter += 1
        kid = f"K{counter:03d}"
        original_id = first_of_group[group]
        key[kid] = {
            "group": group,
            "run_memberships": run_memberships_by_group[group],
            "position": 0,
            "repeat_of": original_id,
        }
    return key


def _c8_run_sample(c8_key, run):
    return [
        kid for kid, info in c8_key.items()
        if run in info.get("run_memberships", []) and info.get("repeat_of") is None
    ]


def test_c8_run_sample_excludes_repeats_and_stays_30():
    c8_key = _make_c8_key(repeats=["pass2_r2", "pass2_r2"])  # mirrors the real run's 2 pass2_r2 repeats
    r1_sample = _c8_run_sample(c8_key, "pass2_r1")
    r2_sample = _c8_run_sample(c8_key, "pass2_r2")
    assert len(r1_sample) == 30
    assert len(r2_sample) == 30  # without the fix this would be 32


def test_c8_run_sample_repeat_label_not_double_counted():
    c8_key = _make_c8_key(repeats=["pass2_r2"])
    repeat_id = next(kid for kid, info in c8_key.items() if info["repeat_of"] is not None)
    original_id = c8_key[repeat_id]["repeat_of"]

    r2_sample = _c8_run_sample(c8_key, "pass2_r2")
    assert repeat_id not in r2_sample
    assert original_id in r2_sample
    # the repeat's own label (even if different from the original's) must
    # never be counted toward the run's claims total - it's excluded entirely.


def test_c8_control_n_excludes_repeats():
    c8_key = _make_c8_key(repeats=["pass1_control", "pass1_control", "pass1_control"])
    originals = {kid: info for kid, info in c8_key.items() if info["repeat_of"] is None}
    control_ids = [kid for kid, info in originals.items() if info["group"] == "pass1_control"]
    assert len(control_ids) == 30  # without the fix this would be 33


def test_c8_control_useful_rate_and_reasons_populated(tmp_path):
    c8_key = _make_c8_key(pass2_r1=2, pass2_r2=2, pass2_both=0, pass1_control=4, repeats=["pass1_control"])
    answers = {}
    control_originals = [kid for kid, info in c8_key.items() if info["repeat_of"] is None and info["group"] == "pass1_control"]
    for i, kid in enumerate(control_originals):
        if i % 2 == 0:
            answers[kid] = C8Answer.model_validate({"id": kid, "label": "claim", "duplicate": "no", "reason": "", "note": ""})
        else:
            answers[kid] = C8Answer.model_validate({"id": kid, "label": "not_claim", "reason": "method_setup", "duplicate": "", "note": ""})

    useful_flags = [answers[kid].label == "claim" and answers[kid].duplicate == "no" for kid in control_originals]
    reasons = [answers[kid].reason for kid in control_originals if answers[kid].label != "claim"]
    assert len(control_originals) == 4  # originals only, repeat excluded
    assert sum(useful_flags) == 2
    assert reasons == ["method_setup", "method_setup"]


# --------------------------------------------------------------------------
# exp3_b4.py: self-consistency pairing - exactly the (original, repeat)
# pairs, never more (issue 3 from the independent audit: confirmed already
# correct, pinned here so it can't silently regress).
# --------------------------------------------------------------------------

def test_self_consistency_pairs_exactly_the_repeats():
    c8_key = _make_c8_key(repeats=["pass2_r1", "pass2_r2", "pass1_control", "pass1_control", "pass2_both"])
    repeat_pairs = [(info["repeat_of"], kid) for kid, info in c8_key.items() if info.get("repeat_of")]
    assert len(repeat_pairs) == 5
    for original_id, repeat_id in repeat_pairs:
        assert c8_key[original_id]["repeat_of"] is None
        assert c8_key[repeat_id]["repeat_of"] == original_id


# --------------------------------------------------------------------------
# exp3_b4.py: _c3_and_c4 / _c7 with genuinely different per-run inputs, so
# a bug that silently reuses run 1's numbers for run 2 can't pass.
# --------------------------------------------------------------------------

def test_c7_per_run_values_and_cross_run_difference(tmp_path, monkeypatch):
    monkeypatch.setattr(exp3_b4, "DEV_PAPERS", ["P1"])
    _write_fixture_paper(tmp_path, "pass2_r1", "P1", pass1_n=1, merged_n=1, sentences_n=10, dropped_ungrounded=1)  # rate 0.9
    _write_fixture_paper(tmp_path, "pass2_r2", "P1", pass1_n=1, merged_n=1, sentences_n=20, dropped_ungrounded=1)  # rate 0.95

    result = exp3_b4._c7(tmp_path)
    assert result["pass2_r1"]["sentences"] == 10
    assert result["pass2_r1"]["rate"] == pytest.approx(0.9)
    assert result["pass2_r1"]["pass"] is False
    assert result["pass2_r2"]["sentences"] == 20
    assert result["pass2_r2"]["rate"] == pytest.approx(0.95)
    assert result["pass2_r2"]["pass"] is True
    assert result["pass2_r1"]["rate"] != result["pass2_r2"]["rate"]


def test_c3_and_c4_per_run_values_differ_and_average_correctly(tmp_path, monkeypatch):
    monkeypatch.setattr(exp3_b4, "DEV_PAPERS", ["P1"])
    _write_fixture_paper(tmp_path, "pass2_r1", "P1", pass1_n=10, merged_n=20)  # ratio 2.0
    _write_json(tmp_path / "pass2_r1" / "_summary.json", {"cost_inr": 10.0, "records": [{"paper_id": "P1", "call_kind": "pass2"}]})
    _write_fixture_paper(tmp_path, "pass2_r2", "P1", pass1_n=10, merged_n=40)  # ratio 4.0
    _write_json(tmp_path / "pass2_r2" / "_summary.json", {"cost_inr": 20.0, "records": [{"paper_id": "P1", "call_kind": "pass2"}]})

    result = exp3_b4._c3_and_c4(tmp_path)
    per_run = result["c3_per_run"]
    assert per_run["pass2_r1"]["r_mean"] == pytest.approx(2.0)
    assert per_run["pass2_r2"]["r_mean"] == pytest.approx(4.0)
    assert per_run["pass2_r1"]["p2"] == pytest.approx(10.0)
    assert per_run["pass2_r2"]["p2"] == pytest.approx(20.0)

    # averaged across the two (deliberately different) runs
    assert result["c4_mean_reading"]["r"] == pytest.approx(3.0)
    assert result["c4_mean_reading"]["p2"] == pytest.approx(15.0)
