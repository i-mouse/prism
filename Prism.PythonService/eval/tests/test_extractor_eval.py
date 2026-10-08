"""Offline tests for eval/extractor_eval.py - synthetic strings only."""
import json

from eval import extractor_eval as ev

S1 = "Zorblat quintessence mirrors the vexing archipelago of tumbling marmalade spoons."
S2 = "Plinkett harmonics reduce the crimson velocity of floating cardboard lanterns by forty percent."
S3 = "Quorvex lattice structures never encountered a single wandering pineapple during calibration."
S4 = "Hexadrome cartography suggests that sleepy glaciers prefer polished bronze trumpets."
S5 = "Mibbleton reactors outperform every conceivable teapot under moonlit humidity."
FILLER = "Grevish bookends accumulate beside the quiet orchard while nobody watches."

PAPER = "\n\n".join([FILLER, S1, f"{S2} {S3}", FILLER, S4, f"{S5} {FILLER}", "A split exam-\nple of grommet tiling."])

ROWS = [
    {"id": "R-FULL", "claim_text_verbatim": S1, "grounding_negative": False},
    {"id": "R-PARTIAL", "claim_text_verbatim": f"{S2} {S3}", "grounding_negative": False},
    {"id": "R-MISS", "claim_text_verbatim": S4, "grounding_negative": True},
    {"id": "R-SUPERSET", "claim_text_verbatim": S5, "grounding_negative": True},
    {"id": "R-UNLOCATED", "claim_text_verbatim": "Ultraviolet pancakes negotiate treaties with sarcastic lighthouses.",
     "grounding_negative": False},
    {"id": "R-HYPHEN", "claim_text_verbatim": "A split example of grommet tiling.", "grounding_negative": False},
]

CLAIMS = [
    {"claim_text_verbatim": S1, "claim_summary": "s"},
    {"claim_text_verbatim": S2, "claim_summary": "s"},
    {"claim_text_verbatim": S3, "claim_summary": "s"},
    {"claim_text_verbatim": f"{S5} {FILLER}", "claim_summary": "s"},
    {"claim_text_verbatim": "An invented sentence about velvet submarines that this document never contains.",
     "claim_summary": "s"},
    {"claim_text_verbatim": "A split example of grommet tiling.", "claim_summary": "s"},
    {"claim_summary": "missing verbatim field"},
]


def test_coverage_statuses():
    cov = ev.compute_coverage(PAPER, ROWS, CLAIMS)
    assert cov["row_status"] == {
        "R-FULL": "FULL",
        "R-PARTIAL": "PARTIAL",  # two claims at ~50% each - no single claim reaches 80%
        "R-MISS": "MISS",
        "R-SUPERSET": "FULL",  # one longer claim covers the whole row
        "R-UNLOCATED": "UNLOCATED",
        "R-HYPHEN": "FULL",  # line-break hyphen absorbed by normalize_for_match
    }
    assert cov["unlocated"] == 1 and cov["unlocated_row_ids"] == ["R-UNLOCATED"]
    assert cov["claims"] == 7
    assert cov["unanchored"] == 2  # invented sentence + claim without claim_text_verbatim
    assert cov["unanchored_rate"] == 2 / 7


def test_coverage_splits_grounding_negative():
    cov = ev.compute_coverage(PAPER, ROWS, CLAIMS)
    assert (cov["negative_full"], cov["negative_partial"], cov["negative_miss"]) == (1, 0, 1)
    assert (cov["positive_full"], cov["positive_partial"], cov["positive_miss"]) == (2, 1, 0)
    assert cov["full_total"] == 3


def test_partial_below_threshold_single_claim():
    # one claim covering only the first sentence of a two-sentence row
    cov = ev.compute_coverage(PAPER, [ROWS[1]], [{"claim_text_verbatim": S2}])
    assert cov["row_status"]["R-PARTIAL"] == "PARTIAL"


def test_no_claims_all_miss():
    cov = ev.compute_coverage(PAPER, ROWS, [])
    assert cov["claims"] == 0 and cov["unanchored_rate"] == 0.0
    assert set(cov["row_status"].values()) == {"MISS", "UNLOCATED"}


INVENTED = "Ultraviolet pancakes negotiate treaties with sarcastic lighthouses."


def test_segments_split_on_both_ellipsis_forms():
    assert ev.segments(f" {S1} ... {S4}…{S5} ...") == [S1, S4, S5]
    assert ev.segments("...") == []


def test_stitched_row_full_by_one_stitched_claim():
    row = {"id": "R-ST", "claim_text_verbatim": f"{S1} ... {S4}", "grounding_negative": False}
    cov = ev.compute_coverage(PAPER, [row], [{"claim_text_verbatim": f"{S1} … {S4}"}])
    assert cov["row_status"]["R-ST"] == "FULL"
    assert cov["unanchored"] == 0 and cov["unlocated"] == 0


def test_half_covered_stitched_row_partial():
    row = {"id": "R-ST", "claim_text_verbatim": f"{S1} ... {S4}", "grounding_negative": False}
    one_side = ev.compute_coverage(PAPER, [row], [{"claim_text_verbatim": S1}])
    assert one_side["row_status"]["R-ST"] == "PARTIAL"
    # each segment covered, but by different claims: the one-claim rule keeps it PARTIAL
    split = ev.compute_coverage(PAPER, [row], [{"claim_text_verbatim": S1}, {"claim_text_verbatim": S4}])
    assert split["row_status"]["R-ST"] == "PARTIAL"


def test_stitched_extracted_claim_anchors():
    cov = ev.compute_coverage(PAPER, [], [{"claim_text_verbatim": f"{S2} ... {S5}"}])
    assert cov["unanchored"] == 0
    # the stitched whole would not align as one string
    from extraction.grounding import normalize_for_match
    assert ev.locate(f"{S2} ... {S5}", normalize_for_match(PAPER)) is None


def test_one_unlocatable_segment():
    row = {"id": "R-ST", "claim_text_verbatim": f"{S1} ... {INVENTED}", "grounding_negative": False}
    cov = ev.compute_coverage(PAPER, [row], [{"claim_text_verbatim": f"{S4} … {INVENTED}"}])
    assert cov["row_status"]["R-ST"] == "UNLOCATED"
    assert cov["unanchored"] == 1


def test_counts_only_drops_row_ids():
    cov = ev.compute_coverage(PAPER, ROWS, CLAIMS)
    redacted = ev.counts_only(cov)
    assert "row_status" not in redacted and "unlocated_row_ids" not in redacted
    assert "R-" not in json.dumps(redacted)


def test_invalid_reasons():
    ok = {"json_parse_ok": True, "fallback_used": False, "finish_reason": "STOP"}
    assert ev.invalid_reasons(ok, {"claims": []}, None) == []
    assert ev.invalid_reasons({**ok, "fallback_used": True}, {"claims": []}, None) == ["fallback_model"]
    assert ev.invalid_reasons({**ok, "finish_reason": "MAX_TOKENS"}, {"claims": []}, None) == ["finish_reason:MAX_TOKENS"]
    assert ev.invalid_reasons({**ok, "json_parse_ok": False}, None, "ValueError") == ["json_parse_failed"]
    assert ev.invalid_reasons(ok, ["not", "a", "dict"], None) == ["json_parse_failed"]
    assert ev.invalid_reasons({}, None, "RuntimeError") == ["call_failed:RuntimeError"]


def _run(run_no, full, neg_full, claims, unanchored, statuses):
    return {"run": run_no, "full_total": full, "negative_full": neg_full, "positive_full": full - neg_full,
            "claims": claims, "unanchored": unanchored, "unanchored_rate": unanchored / claims,
            "row_status": statuses, "prompt_tokens": 100, "cached_tokens": 25}


def test_aggregate_paper_and_row_frequency():
    runs = [_run(1, 2, 1, 10, 1, {"A": "FULL", "B": "MISS"}), _run(2, 4, 2, 20, 2, {"A": "FULL", "B": "FULL"})]
    agg = ev.aggregate_paper(runs)
    assert agg["full_total"] == {"mean": 3, "min": 2, "max": 4, "n": 2}
    assert agg["row_full_frequency"] == {"A": "2/2", "B": "1/2"}
    assert agg["cached_share"] == 0.25


def test_aggregate_arm_pairs_runs_present_for_every_paper():
    papers = {
        "p1": {"runs": [_run(1, 2, 1, 10, 1, {}), _run(2, 3, 1, 10, 1, {})]},
        "p2": {"runs": [_run(2, 5, 2, 10, 3, {})]},  # run 1 failed for p2
    }
    arm = ev.aggregate_arm(papers)
    assert [r["run"] for r in arm["per_run"]] == [2]
    assert arm["per_run"][0]["full_total"] == 8
    assert arm["per_run"][0]["unanchored_rate"] == 4 / 20


def _result(per_run_full, per_run_neg, rates, paper_full_means, paper_claim_means):
    return {
        "mode": "live",
        "arm_aggregate": {"per_run": [{"full_total": f, "negative_full": n, "unanchored_rate": r}
                                      for f, n, r in zip(per_run_full, per_run_neg, rates)]},
        "papers": {pid: {"aggregate": {"full_total": {"mean": fm}, "claims": {"mean": paper_claim_means[pid]}}}
                   for pid, fm in paper_full_means.items()},
    }


def test_marks_pass_and_fail():
    before = _result([10, 11], [3, 3], [0.10, 0.10], {"p1": 5.0, "p2": 5.5}, {"p1": 20, "p2": 20})
    after = _result([12, 13], [4, 3], [0.14, 0.15], {"p1": 6.0, "p2": 4.6}, {"p1": 30, "p2": 51})
    marks = {m["mark"]: m["pass"] for m in ev.evaluate_marks(before, after)}
    assert marks == {"M1": True, "M2": True, "M3": False, "M4": True, "M5": True}

    after_bad = _result([11, 13], [2, 2], [0.20, 0.20], {"p1": 6.0, "p2": 4.0}, {"p1": 30, "p2": 40})
    marks = {m["mark"]: m["pass"] for m in ev.evaluate_marks(before, after_bad)}
    assert marks == {"M1": False, "M2": False, "M3": True, "M4": False, "M5": False}


def test_heldout_guard_redacts_log_text_and_silences_output(tmp_path, monkeypatch, capsys):
    from extraction import engine

    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path)
    secret = "SYNTHETIC SECRET CLAIM TEXT"
    with ev.heldout_guard():
        print(secret)
        engine._write_structured_log(
            log_subdir="extraction", chat_id="c1", correlation_id=None, model_used="m",
            request_message_count=3, response_item_count=1, response_raw=secret,
        )
    out = capsys.readouterr()
    assert secret not in out.out and secret not in out.err
    [log_file] = list((tmp_path / "extraction").glob("*.json"))
    content = log_file.read_text(encoding="utf-8")
    assert secret not in content
    record = json.loads(content)
    assert record["response_raw"] == f"[redacted held-out text: {len(secret)} chars]"
    assert record["chat_id"] == "c1" and record["model_used"] == "m"
    # guard is lifted afterwards
    assert engine._write_structured_log.__name__ == "_write_structured_log"
