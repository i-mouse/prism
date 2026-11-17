"""eval/replay_audit.py with --table-check: the flag, routing, the checker / fallback / unrouted paths, the trace,
cost accounting, --estimate, and the flag-off output staying byte-identical. Offline: fake SDK, fake grounding,
invented text only (tests/replay_fakes.py)."""
import argparse
import asyncio
import json
from types import SimpleNamespace

import pytest

from eval import pricing, replay_audit
from eval.step4 import score_table_check, table_check, table_check_calls
from extraction import engine, prompt_version

import replay_fakes
from replay_fakes import MODEL, PAPER_A, PAPER_B, PAPER_TEXTS, FakeSdk

C_A0 = "The controller reduces fatigue load on all three turbine models."
C_A1 = "The controller reduces fatigue load under both low and gusty wind."
C_A2 = "Gusty wind is harder than low wind for every model."

# Frozen evidence spans per (paper, claim index); the last claim of paper B has none.
SPANS = {
    (PAPER_A, 0): [{"source_text": "T3 | -11.2 | +1.3", "source_section": "Table 2", "grounding_status": "Pass", "stance": "supports"}],
    (PAPER_A, 1): [{"source_text": "The controller reduces fatigue load on turbine models T1, T2 and T3.", "source_section": "Results"}],
    (PAPER_A, 2): [{"source_text": "T1 | -12.4 | -9.1", "source_section": "Table 2"}],
    (PAPER_B, 0): [{"source_text": "Method M beats the baseline on task X by 3 points", "source_section": "Table 2"}],
}
PIECE_A0 = "the load falls on model T3 under gusty wind"
NOT_BACKED_A0 = {"pieces": [{
    "piece_id": 1, "answer": "not_backed",
    "cells": [{"table": 2, "row_label": "T3", "column_label": "Gusty wind", "value": "+1.3"}],
}]}
TABLECHECK_DIR = "exp1_medium_tablecheck_1"


def _lister(claim_text: str) -> str:
    items = {C_A0: [{"text": PIECE_A0, "kind": "count"}]}.get(claim_text.strip(), [])
    return json.dumps({"items": items})


class TableSdk(FakeSdk):
    """FakeSdk plus the table checker call, told apart by its response schema. table_fn(user_text) returns the
    response text, or raises."""

    def __init__(self, table_fn=None, **kwargs):
        kwargs.setdefault("lister_fn", _lister)
        super().__init__(**kwargs)
        self.table_fn = table_fn or (lambda text: json.dumps(NOT_BACKED_A0))

    async def _generate(self, *, model, contents, config):
        if getattr(config.response_schema, "__name__", None) != "TableCheckResponse":
            return await super()._generate(model=model, contents=contents, config=config)
        self.requested_models.append(model)
        text = self.table_fn(replay_fakes._text_of(contents))
        self.calls.append(("table_checker", model, contents, config))
        return SimpleNamespace(text=text, parsed=None, usage_metadata=replay_fakes._usage(3_000, 150, 500))


def _setup(tmp_path, monkeypatch, sdk):
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, sdk)
    for path in (tmp_path / "run1").glob("*.json"):
        fixture = json.loads(path.read_text(encoding="utf-8"))
        for claim in fixture["claims"]:
            spans = SPANS.get((path.stem, claim["index"]))
            if spans is not None:
                claim["evidence_spans"] = spans
        path.write_text(json.dumps(fixture), encoding="utf-8")
    return claims_path


def _args(claims_path, **overrides) -> argparse.Namespace:
    values = dict(
        level="medium", claims=str(claims_path), papers=None, repeat=1, estimate=False, dry_run=False, max_inr=None,
        cache=False, scope_check=False, table_check=True,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def _go(tmp_path, monkeypatch, sdk=None, **overrides):
    sdk = sdk or TableSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    return asyncio.run(replay_audit._main(_args(claims_path, **overrides))), sdk


def _out(tmp_path, paper_id, folder=TABLECHECK_DIR) -> dict:
    return json.loads((tmp_path / "out" / folder / f"{paper_id}.json").read_text(encoding="utf-8"))


def _summary(tmp_path, folder=TABLECHECK_DIR) -> dict:
    return json.loads((tmp_path / "out" / folder / "_summary.json").read_text(encoding="utf-8"))


# --- the flag ---------------------------------------------------------------------------------------------------

def test_the_flag_defaults_off_and_is_a_cli_option():
    parser = replay_audit._build_parser()
    assert parser.parse_args(["--level", "medium"]).table_check is False
    assert parser.parse_args(["--level", "medium", "--table-check", "--cache"]).table_check is True


def test_table_check_cannot_be_combined_with_scope_check(tmp_path, monkeypatch):
    claims_path = _setup(tmp_path, monkeypatch, TableSdk())
    with pytest.raises(ValueError, match="cannot be combined"):
        asyncio.run(replay_audit._main(_args(claims_path, cache=True, scope_check=True)))


def test_flag_off_prompt_hash_is_the_frozen_one_and_no_new_file_is_hashed_into_it():
    assert prompt_version.get_prompt_version(
        fewshot_fix=False, fewshot_shapes=False, extractor_second_pass=False, extractor_pass2_clean=False,
    ) == replay_audit.EXPECTED_PROMPT_HASH == "cb3272cce551"
    hashed = {str(name) for name in prompt_version.PROMPT_FILENAMES} | {p.name for p in prompt_version.EXTRA_HASHED_FILES}
    assert not any("table_check" in name for name in hashed)
    assert table_check.CHECKER_PROMPT_PATH.parent.name == "step4"   # not in the product prompts folder


def test_flag_off_output_is_byte_identical_with_and_without_the_new_argument(tmp_path, monkeypatch):
    def run(root, **overrides):
        root.mkdir()
        sdk = TableSdk()
        claims_path = _setup(root, monkeypatch, sdk)
        args = _args(claims_path, **overrides)
        if "table_check" not in overrides:
            del args.table_check          # a caller from before the flag existed
        assert asyncio.run(replay_audit._main(args)) == 0
        folder = root / "out" / "exp1_medium_1"
        return sdk, {p.name: p.read_bytes() for p in sorted(folder.glob("*.json"))}, root

    sdk_old, files_old, root_old = run(tmp_path / "old")
    sdk_off, files_off, root_off = run(tmp_path / "off", table_check=False)
    assert files_old == files_off and set(files_off) == {f"{PAPER_A}.json", f"{PAPER_B}.json", "_summary.json"}
    assert sdk_old.kinds() == sdk_off.kinds() == ["audit", "structure"] * 5
    for root in (root_old, root_off):
        assert not (root / "out" / TABLECHECK_DIR).exists()
        claim = _out(root, PAPER_A, "exp1_medium_1")["claims"][0]
        assert "table_check" not in claim and "audit_model_served" not in claim
        assert "table_check" not in _out(root, PAPER_A, "exp1_medium_1")["header"]["replay"]
        summary = _summary(root, "exp1_medium_1")
        assert "table_check" not in summary and "run_config" not in summary
        assert {r["stage"] for r in summary["records"]} == {"audit"}


# --- routed, fallback and unrouted claims ---------------------------------------------------------------------------

def test_calls_labels_and_trace_per_claim(tmp_path, monkeypatch):
    rc, sdk = _go(tmp_path, monkeypatch)
    assert rc == 0
    # A0 routed -> lister + checker (no audit); A1 unrouted -> audit; A2 routed, zero pieces -> lister + fallback
    # audit; paper B has no found table -> audit for both claims
    assert sdk.kinds() == (
        ["lister", "table_checker"] + ["audit", "structure"] + ["lister", "audit", "structure"]
        + ["audit", "structure"] * 2
    )
    a0, a1, a2 = _out(tmp_path, PAPER_A)["claims"]
    assert a0["label"] == "not_supported" and a0["audit_model_served"] == MODEL
    assert a0["claim_text_verbatim"] == C_A0 and a0["claim_summary"] == "Fatigue load falls on all models."
    assert [(s["source_text"], s["source_section"]) for s in a0["evidence_spans"]] == [("T3 | -11.2 | +1.3", "Table 2")]
    t0 = a0["table_check"]
    assert (t0["routed"], t0["source"], t0["checker_label"], t0["cited"]) == (True, "checker", "not_supported", [2])
    assert (t0["n_pieces"], t0["n_failed"], t0["n_could_not_check"]) == (1, 1, 0)
    assert t0["pieces"][0]["answer"] == "not_backed" and t0["pieces"][0]["state"] == "failed"
    assert t0["pieces"][0]["cells"] == NOT_BACKED_A0["pieces"][0]["cells"]

    assert a1["label"] == "supported" and a1["audit_model_served"] == MODEL
    assert a1["table_check"] == {"routed": False, "source": "audit", "reason": "no_table_mention", "cited": []}

    assert a2["label"] == "partially_supported"       # the canned auditor's label is final
    t2 = a2["table_check"]
    assert (t2["routed"], t2["source"], t2["fallback_reason"], t2["checker_label"]) == (
        True, "fallback_audit", "zero_pieces", None,
    )

    b0, b1 = _out(tmp_path, PAPER_B)["claims"]
    assert b0["table_check"]["reason"] == b1["table_check"]["reason"] == "no_found_table"
    assert b0["table_check"]["cited"] == [2] and b1["label"] == "not_supported"

    header = _out(tmp_path, PAPER_A)["header"]["replay"]
    assert header["table_check"] == {
        "lister_hash": table_check.lister_hash(), "checker_hash": table_check.checker_hash(),
        "finder_commit": table_check.FINDER_COMMIT,
    }
    assert not (tmp_path / "out" / "exp1_medium_1").exists()


def test_the_checker_sees_the_claim_its_pieces_and_the_table_block_but_not_the_whole_paper(tmp_path, monkeypatch):
    _, sdk = _go(tmp_path, monkeypatch)
    [(_, model, contents, config)] = [c for c in sdk.calls if c[0] == "table_checker"]
    sent = replay_fakes._text_of(contents)
    assert model == table_check_calls.CHECKER_MODEL and config.cached_content is None
    assert C_A0 in sent and f"1. [count] {PIECE_A0}" in sent
    assert "=== Table 2 ===\nTable 2: Fatigue load change (percent)" in sent and "T3 | -11.2 | +1.3" in sent
    assert "Abstract. We study pitch control" not in sent


def test_could_not_check_runs_todays_audit_and_its_label_is_final(tmp_path, monkeypatch):
    def not_a_table_piece(text):
        return json.dumps({"pieces": [{"piece_id": 1, "answer": "not_a_table_piece", "cells": []}]})

    rc, sdk = _go(tmp_path, monkeypatch, sdk=TableSdk(table_fn=not_a_table_piece))
    assert rc == 0
    assert sdk.kinds()[:4] == ["lister", "table_checker", "audit", "structure"]
    a0 = _out(tmp_path, PAPER_A)["claims"][0]
    assert a0["label"] == "supported"
    assert (a0["table_check"]["source"], a0["table_check"]["fallback_reason"]) == ("fallback_audit", "could_not_check")
    assert a0["table_check"]["n_failed"] == 0 and a0["table_check"]["checker_label"] is None
    records = _summary(tmp_path)["records"]
    assert [(r["stage"], r["is_audit"]) for r in records[:4]] == [
        ("lister", False), ("table_checker", False), ("audit_fallback", True), ("audit_fallback", False),
    ]


def test_a_guard_failure_never_lowers_the_label(tmp_path, monkeypatch):
    def invented_value(text):
        return json.dumps({"pieces": [{
            "piece_id": 1, "answer": "not_backed",
            "cells": [{"table": 2, "row_label": "T3", "column_label": "Gusty wind", "value": "+7.7"}],
        }]})

    rc, _ = _go(tmp_path, monkeypatch, sdk=TableSdk(table_fn=invented_value))
    a0 = _out(tmp_path, PAPER_A)["claims"][0]
    assert rc == 0 and a0["label"] == "supported" and a0["table_check"]["source"] == "fallback_audit"
    assert a0["table_check"]["pieces"][0]["guard_reasons"] == ["value_missing"]
    assert _summary(tmp_path)["table_check"]["guard_failures"] == 1


def test_checker_invalid_twice_is_one_retry_then_fallback_and_is_counted(tmp_path, monkeypatch):
    rc, sdk = _go(tmp_path, monkeypatch, sdk=TableSdk(table_fn=lambda text: "not json"))
    assert rc == 0
    assert sdk.kinds()[:5] == ["lister", "table_checker", "table_checker", "audit", "structure"]
    block = _summary(tmp_path)["table_check"]
    assert (block["checker_failures"], block["lister_failures"], block["fallback_claims"]) == (1, 0, 2)
    assert block["fallback_reasons"] == {"could_not_check": 1, "zero_pieces": 1}
    assert _out(tmp_path, PAPER_A)["claims"][0]["table_check"]["checker_failed"] is True


def test_a_routed_claim_without_frozen_spans_runs_todays_audit(tmp_path, monkeypatch):
    cites_in_text = "Table 2 shows the controller reduces fatigue load on all three turbine models."
    monkeypatch.delitem(SPANS, (PAPER_A, 0))                                   # the fixture claim has no spans
    monkeypatch.setitem(replay_fakes.LABEL_BY_CLAIM, cites_in_text, "supported")
    sdk = TableSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    path = tmp_path / "run1" / f"{PAPER_A}.json"
    fixture = json.loads(path.read_text(encoding="utf-8"))
    fixture["claims"][0]["claim_text_verbatim"] = cites_in_text
    path.write_text(json.dumps(fixture), encoding="utf-8")

    assert asyncio.run(replay_audit._main(_args(claims_path))) == 0
    assert sdk.kinds()[:2] == ["audit", "structure"]       # no lister, no checker: nothing to carry into grounding
    a0 = _out(tmp_path, PAPER_A)["claims"][0]
    assert a0["table_check"] == {"routed": False, "source": "audit", "reason": "no_spans", "cited": [2]}
    assert a0["label"] == "supported"
    assert _summary(tmp_path)["table_check"]["unrouted"]["no_spans"] == 1


# --- summary, cost, run_config --------------------------------------------------------------------------------------

def test_summary_block_counts_and_every_call_kind_is_priced(tmp_path, monkeypatch):
    rc, _ = _go(tmp_path, monkeypatch)
    assert rc == 0
    summary = _summary(tmp_path)
    block = summary["table_check"]
    assert (block["claims"], block["routed_claims"], block["pieces"], block["failed_pieces"]) == (5, 2, 1, 1)
    assert block["unrouted"] == {"no_table_mention": 1, "no_found_table": 2}
    assert block["answers"] == {"not_backed": 1} and block["checker_labels"] == {"not_supported": 1}
    assert (block["fallback_claims"], block["fallback_reasons"]) == (1, {"zero_pieces": 1})
    assert block["config"]["enabled"] is True and block["config"]["finder_commit"] == "f7ca8a3"
    assert block["config"]["block_cap_hits"] == {
        "per_table_cap_tables": {}, "join_cap_dropped_tables": {}, "papers_with_no_found_table": 1,
    }

    by_call = block["by_call"]
    assert {kind: usage["calls"] for kind, usage in by_call.items()} == {
        "audit": 3, "audit_fallback": 1, "lister": 2, "table_checker": 1,
    }
    audit_usd = pricing.cost_usd(40_000, 120, 300)
    assert by_call["audit"]["cost_usd"] == pytest.approx(3 * audit_usd, abs=1e-4)
    assert by_call["audit_fallback"]["cost_usd"] == pytest.approx(audit_usd, abs=1e-4)
    assert by_call["lister"]["cost_usd"] == pytest.approx(2 * pricing.cost_usd(500, 60, 100), abs=1e-4)
    assert by_call["table_checker"]["cost_usd"] == pytest.approx(pricing.cost_usd(3_000, 150, 500), abs=1e-4)
    total = (
        4 * audit_usd + 4 * pricing.cost_usd(1_400, 250, 800) + 2 * pricing.cost_usd(500, 60, 100)
        + pricing.cost_usd(3_000, 150, 500)
    )
    assert summary["cost_usd"] == pytest.approx(total, abs=1e-3)

    # the scorer's per-claim audit cost counts audit + fallback audit + lister + checker, over the 5 claims
    cost = score_table_check.folder_cost(tmp_path, summary, [])
    counted_usd = 4 * audit_usd + 2 * pricing.cost_usd(500, 60, 100) + pricing.cost_usd(3_000, 150, 500)
    assert cost["claims"] == 5 and cost["calls_by_kind"] == {"audit": 3, "audit_fallback": 1, "lister": 2, "table_checker": 1}
    assert cost["audit_inr_per_claim"] == pytest.approx(counted_usd * pricing.INR_PER_USD / 5, abs=1e-3)


def test_the_scorer_and_the_replay_use_the_same_call_kinds():
    assert score_table_check.KIND_AUDIT == replay_audit.STAGE_AUDIT
    assert score_table_check.KIND_AUDIT_FALLBACK == replay_audit.STAGE_AUDIT_FALLBACK
    assert score_table_check.KIND_LISTER == table_check_calls.LISTER_CALL_KIND
    assert score_table_check.KIND_CHECKER == table_check_calls.CHECKER_CALL_KIND
    assert replay_audit.TABLE_CHECK_CALL_KINDS == score_table_check.COUNTED_KINDS


def test_max_inr_counts_the_lister_and_the_checker(tmp_path, monkeypatch):
    # the lister alone (INR 0.10) stays under the cap; the checker call takes the run over it
    rc, sdk = _go(tmp_path, monkeypatch, max_inr=0.15)
    assert rc == replay_audit.EXIT_CAP_HIT
    assert sdk.kinds() == ["lister", "table_checker"]
    assert _summary(tmp_path)["status"] == "VOID_CAP_HIT"


def test_cache_still_applies_to_the_audit_calls_only(tmp_path, monkeypatch):
    rc, sdk = _go(tmp_path, monkeypatch, cache=True)
    assert rc == 0 and len(sdk.created) == 2 and len(sdk.deleted) == 2
    for kind, _, _, config in sdk.calls:
        assert bool(config.cached_content) == (kind == "audit")
    assert _summary(tmp_path)["cache"]["audit_calls"] == 4


def test_table_check_config_records_the_flag_hashes_finder_and_cap_hits(monkeypatch):
    blocks = {p: table_check.build_table_blocks(text) for p, text in PAPER_TEXTS.items()}
    config = replay_audit._table_check_config(blocks)
    assert config["enabled"] is True
    assert (config["lister_hash"], config["checker_hash"]) == (table_check.lister_hash(), table_check.checker_hash())
    assert config["finder_commit"] == "f7ca8a3" and config["join_cap_chars"] == 60_000
    assert config["checker_model"] == "gemini-3.6-flash"

    monkeypatch.setattr(table_check, "JOIN_CAP_CHARS", 10)
    dropped = {p: table_check.build_table_blocks(text) for p, text in PAPER_TEXTS.items()}
    assert replay_audit._table_check_config(dropped)["block_cap_hits"]["join_cap_dropped_tables"] == {PAPER_A: 1}


def test_a_non_default_run_records_the_table_check_block_in_run_config(tmp_path):
    ledger = replay_audit._TableLedger(stats=table_check.TableCheckStats(), blocks={}, config={"enabled": True, "lister_hash": "l",
                                       "checker_hash": "c", "finder_commit": "f", "block_cap_hits": {}})
    options = replay_audit._RunOptions(backend=replay_audit.llm_backend.AISTUDIO, tag="made-up", run_config={"backend": "x"})
    replay_audit._print_summary(tmp_path, [], run_options=options, table_ledger=ledger)
    summary = json.loads((tmp_path / "_summary.json").read_text(encoding="utf-8"))
    assert summary["run_config"] == {"backend": "x", "table_check": ledger.config}
    assert options.run_config == {"backend": "x"}     # the shared options are not mutated
    assert options.out_dir("medium", 2, False, table_check_on=True).name == "exp1_medium_made-up_tablecheck_2"
    assert options.out_dir("medium", 2, False).name == "exp1_medium_made-up_2"


def test_an_existing_tablecheck_folder_is_never_overwritten(tmp_path, monkeypatch, capsys):
    claims_path = _setup(tmp_path, monkeypatch, TableSdk())
    (tmp_path / "out" / TABLECHECK_DIR).mkdir(parents=True)
    assert asyncio.run(replay_audit._main(_args(claims_path))) == 1
    assert "already exist" in capsys.readouterr().out


# --- --estimate -----------------------------------------------------------------------------------------------------

def test_estimate_includes_lister_checker_and_the_fallback_range_and_builds_no_client(tmp_path, monkeypatch, capsys):
    claims_path = _setup(tmp_path, monkeypatch, TableSdk())

    def fail():
        raise AssertionError("--estimate must not build a client")

    monkeypatch.setattr(engine, "_build_client", fail)
    assert asyncio.run(replay_audit._main(_args(claims_path, estimate=True))) == 0
    out = capsys.readouterr().out
    assert "--estimate --table-check: 5 claims, 2 routed, 3 unrouted" in out
    assert "ASSUMPTION (fallback rate)" in out and "LOW end = 0%" in out and "HIGH end = 100%" in out
    assert "ASSUMPTION (lister" in out and "ASSUMPTION (checker" in out and "ESTIMATED (checker input)" in out
    assert "table-check total: USD" in out and "suggested --max-inr with --table-check" in out
    assert f"lister {table_check.lister_hash()}, checker {table_check.checker_hash()}" in out
    assert not (tmp_path / "out").exists()


def test_estimate_low_end_drops_the_routed_audits_and_high_end_keeps_every_audit(capsys):
    spans = ({"source_text": "x", "source_section": "Table 2"},)
    targets = [
        replay_audit.ReplayTarget(PAPER_A, i, "c", "s", evidence_spans=spans if i < 2 else ()) for i in range(5)
    ]
    blocks = {PAPER_A: table_check.build_table_blocks(PAPER_TEXTS[PAPER_A])}
    low, high = replay_audit._print_table_check_estimate(targets, "medium", 3, blocks)
    capsys.readouterr()
    stats = replay_audit._load_measured_token_stats()
    claim_low, claim_high = replay_audit._estimate_one_claim_cost_usd(stats, "medium")
    lister = pricing.cost_usd(
        replay_audit.ASSUMED_LISTER_INPUT_TOKENS, replay_audit.ASSUMED_LISTER_OUTPUT_TOKENS,
        replay_audit.ASSUMED_LISTER_THOUGHT_TOKENS,
    )
    checker = pricing.cost_usd(
        len(blocks[PAPER_A].text) / 4 + replay_audit.ASSUMED_TABLE_CHECKER_OVERHEAD_TOKENS,
        replay_audit.ASSUMED_TABLE_CHECKER_OUTPUT_TOKENS, stats["audit_thought_medium"],
    )
    assert low == pytest.approx((3 * claim_low + 2 * (lister + checker)) * 3)
    assert high == pytest.approx((5 * claim_high + 2 * (lister + checker)) * 3)
    assert high > low
