"""Unit tests for eval/replay_clean.py's --filter-only mode.

Covers: --filter-only sends only the pass-2-tagged candidates from an
existing --from-run folder's merged.json to the filter, with pass-1 claims
passed through unchanged (same split extraction.pass2_clean.filter_merged_
claims already performs for the normal --pass1-run path - see tests/
test_pass2_clean.py); and it refuses to run when --from-run is missing or
equals --run-id, before touching anything on disk. No LLM calls, no DB, no
real PDFs - extraction.engine._call_gemini_structured and
eval.replay_clean._hash_check_and_load_text are faked.
"""
import argparse
import asyncio
import json
from pathlib import Path

from eval import replay_clean
from extraction import engine


def _write_merged_fixture(from_run_dir: Path, paper_id: str, pass1_texts: list[str], pass2_texts: list[str]) -> None:
    from_run_dir.mkdir(parents=True, exist_ok=True)
    header = {"paper_id": paper_id, "extraction_run_id": 1}
    claims = (
        [{"claim_text_verbatim": t, "claim_summary": t, "pass": "pass1"} for t in pass1_texts]
        + [{"claim_text_verbatim": t, "claim_summary": t, "pass": "pass2"} for t in pass2_texts]
    )
    (from_run_dir / f"{paper_id}_merged.json").write_text(
        json.dumps({"header": header, "claims": claims}), encoding="utf-8",
    )


def test_filter_only_judges_only_pass2_tagged_items_pass1_passes_through(monkeypatch, tmp_path):
    from_run_dir = tmp_path / "clean_pilot"
    monkeypatch.setattr(replay_clean, "OUTPUT_ROOT", tmp_path / "out")
    pass1_text = "Our first method claim stays as pass1."
    pass2_kept_text = "Our method achieves 90% accuracy on the benchmark."
    pass2_dropped_text = "This does not establish that the method generalizes beyond this benchmark."
    paper_text = f"{pass1_text} {pass2_kept_text} {pass2_dropped_text}"
    _write_merged_fixture(
        from_run_dir, "paperA",
        pass1_texts=[pass1_text],
        pass2_texts=[pass2_kept_text, pass2_dropped_text],
    )

    judged_candidates: list[str] = []

    async def fake_call_gemini_structured(
        messages, response_schema, chat_id, correlation_id, log_subdir, model_name, fallback_model, thinking_level=None,
    ):
        from extraction.pass2_clean import CleanFilterBatchLLM, CleanFilterItemLLM

        user_msg = next(m["content"] for m in messages if m["role"] == "user")
        payload = json.loads(user_msg)["candidates"]
        judged_candidates.extend(entry["candidate"] for entry in payload)
        items = []
        for entry in payload:
            if entry["candidate"] == pass2_dropped_text:
                items.append(CleanFilterItemLLM(
                    reasoning="limitation", is_paper_claim=False, reason_code="limitation_or_caveat", relations=[],
                ))
            else:
                items.append(CleanFilterItemLLM(
                    reasoning="result", is_paper_claim=True, reason_code="own_claim", relations=[],
                ))
        return CleanFilterBatchLLM(items=items)

    async def fake_hash_check(paper_id, header):
        return paper_text

    monkeypatch.setattr(engine, "_call_gemini_structured", fake_call_gemini_structured)
    monkeypatch.setattr(replay_clean, "_hash_check_and_load_text", fake_hash_check)

    out_dir, _ = asyncio.run(
        replay_clean._run_filter_only(from_run_dir, ["paperA"], "clean_filtered_r1", False, None, None)
    )

    # The pass-1 claim was never sent to the filter - only the two
    # pass-2-tagged candidates were.
    assert judged_candidates == [pass2_kept_text, pass2_dropped_text]

    filtered = json.loads((out_dir / "paperA_filtered.json").read_text(encoding="utf-8"))
    claim_texts = [c["claim_text_verbatim"] for c in filtered["claims"]]
    assert claim_texts == [pass1_text, pass2_kept_text]


def test_filter_only_refuses_when_from_run_dir_missing(monkeypatch, tmp_path):
    monkeypatch.setattr(replay_clean, "OUTPUT_ROOT", tmp_path)
    args = argparse.Namespace(
        filter_only=True, from_run="does_not_exist", run_id="clean_filtered_r1", papers=None,
        estimate=False, dry_run=False, max_inr=None, no_filter=False, pass1_run=None,
        pass2_thinking_level=None,
    )

    result = asyncio.run(replay_clean._main(args))

    assert result == 1
    assert not (tmp_path / "clean_filtered_r1").exists()


def test_filter_only_refuses_when_run_id_equals_from_run(monkeypatch, tmp_path):
    monkeypatch.setattr(replay_clean, "OUTPUT_ROOT", tmp_path)
    (tmp_path / "clean_pilot").mkdir()
    args = argparse.Namespace(
        filter_only=True, from_run="clean_pilot", run_id="clean_pilot", papers=None,
        estimate=False, dry_run=False, max_inr=None, no_filter=False, pass1_run=None,
        pass2_thinking_level=None,
    )

    result = asyncio.run(replay_clean._main(args))

    assert result == 1
