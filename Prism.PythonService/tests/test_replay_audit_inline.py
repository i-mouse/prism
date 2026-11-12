"""eval/replay_audit.py: inline claims in a --claims file (claim_text_verbatim + claim_summary, claim_index >= 1000, no
run-1 lookup) and --out-tag. Offline: fake SDK and invented text from tests/replay_fakes.py, nothing real is read.

A run with no inline entry and no --out-tag must stay as it was; the existing test_replay_audit*.py files are the
rest of that check."""
import argparse
import asyncio
import json

import pytest

from eval import replay_audit
from extraction import engine
from extraction.prompt_version import get_prompt_version

import replay_fakes
from replay_fakes import MODEL, PAPER_A, PAPER_B, FakeSdk

VERTEX = {"backend": "vertex", "vertex_project": "proj-x", "vertex_location": "global"}
FOLDER = f"exp1_medium_{MODEL}-vertex"   # + [-TAG]_<n>
TAG = "exp3p2"
CLAIM_A0 = replay_fakes.CLAIMS[0]        # (paper, index, text, summary, label): a text the fake auditor knows


def _args(claims_path, **overrides) -> argparse.Namespace:
    values = {
        "level": "medium", "claims": str(claims_path), "papers": None, "repeat": 1, "estimate": False,
        "dry_run": False, "max_inr": None, "cache": False,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _run(claims_path, **overrides) -> int:
    return asyncio.run(replay_audit._main(_args(claims_path, **overrides)))


def _setup(tmp_path, monkeypatch, sdk):
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, sdk)
    for name, value in (
        ("llm_claim_audit_fallback_model", "gemini-3.1-flash-lite"),
        ("llm_grounding_model", "groq/openai/gpt-oss-20b"),
        ("llm_grounding_fallback_model", "gemini/gemini-3.1-flash-lite"),
        ("ai_api_key", "test-aistudio-key"),
    ):
        monkeypatch.setattr(engine.settings, name, value)
    return claims_path


def _folders(tmp_path) -> list[str]:
    out = tmp_path / "out"
    return sorted(p.name for p in out.iterdir()) if out.exists() else []


def _inline(paper_id=PAPER_A, index=1000, text=CLAIM_A0[2], summary=CLAIM_A0[3]) -> dict:
    return {"paper_id": paper_id, "claim_index": index, "claim_text_verbatim": text, "claim_summary": summary}


def _write_claims(tmp_path, entries) -> object:
    path = tmp_path / "inline_claims.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


# --- _load_targets -------------------------------------------------------------------------------------

def test_inline_entry_loads_without_run1_lookup(tmp_path, monkeypatch):
    replay_fakes.setup_replay(tmp_path, monkeypatch, FakeSdk())   # run-1 fixtures exist (the paper id check needs them)

    def _no_lookup(paper_id):
        raise AssertionError("the run-1 fixture must not be read for an inline-only paper")

    monkeypatch.setattr(replay_audit, "_read_fixture", _no_lookup)
    targets = replay_audit._load_targets(_write_claims(tmp_path, [_inline()]), None)

    assert len(targets) == 1
    assert (targets[0].paper_id, targets[0].claim_index, targets[0].inline) == (PAPER_A, 1000, True)
    assert targets[0].claim_text_verbatim == CLAIM_A0[2]
    assert targets[0].claim_summary == CLAIM_A0[3]


@pytest.mark.parametrize("missing", ["claim_summary", "claim_text_verbatim"])
def test_inline_entry_with_one_text_field_alone_raises(tmp_path, monkeypatch, missing):
    replay_fakes.setup_replay(tmp_path, monkeypatch, FakeSdk())
    entry = _inline()
    del entry[missing]
    with pytest.raises(ValueError, match=f"{PAPER_A}.*1000|claim_text_verbatim and claim_summary"):
        replay_audit._load_targets(_write_claims(tmp_path, [entry]), None)


@pytest.mark.parametrize("index", [0, 5, 999])
def test_inline_index_below_1000_raises(tmp_path, monkeypatch, index):
    replay_fakes.setup_replay(tmp_path, monkeypatch, FakeSdk())
    with pytest.raises(ValueError, match="1000"):
        replay_audit._load_targets(_write_claims(tmp_path, [_inline(index=index)]), None)


def test_duplicate_paper_claim_pair_raises(tmp_path, monkeypatch):
    replay_fakes.setup_replay(tmp_path, monkeypatch, FakeSdk())
    with pytest.raises(ValueError, match="more than once"):
        replay_audit._load_targets(_write_claims(tmp_path, [_inline(index=1001), _inline(index=1001)]), None)


def test_mixed_inline_and_indexed_entries_load_in_file_order(tmp_path, monkeypatch):
    replay_fakes.setup_replay(tmp_path, monkeypatch, FakeSdk())
    entries = [
        {"paper_id": PAPER_A, "claim_index": 2},
        _inline(index=1001),
        {"paper_id": PAPER_A, "claim_index": 0},
        {"paper_id": PAPER_B, "claim_index": 1},
    ]
    targets = replay_audit._load_targets(_write_claims(tmp_path, entries), None)

    assert [(t.paper_id, t.claim_index, t.inline) for t in targets] == [
        (PAPER_A, 2, False), (PAPER_A, 1001, True), (PAPER_A, 0, False), (PAPER_B, 1, False),
    ]
    assert targets[0].claim_text_verbatim == replay_fakes.CLAIMS[2][2]      # the indexed ones still come from run 1
    assert targets[1].claim_text_verbatim == CLAIM_A0[2]


def test_an_indexed_only_claims_file_loads_as_before(tmp_path, monkeypatch):
    replay_fakes.setup_replay(tmp_path, monkeypatch, FakeSdk())
    entries = [{"paper_id": PAPER_A, "claim_index": 1}, {"paper_id": PAPER_A, "claim_index": 1}]
    targets = replay_audit._load_targets(_write_claims(tmp_path, entries), None)
    assert [(t.claim_index, t.inline) for t in targets] == [(1, False), (1, False)]   # repeats were never rejected here


# --- whole runs ----------------------------------------------------------------------------------------

def test_inline_run_marks_the_header_and_audits_the_inline_claim(tmp_path, monkeypatch):
    sdk = FakeSdk()
    _setup(tmp_path, monkeypatch, sdk)
    claims_path = _write_claims(tmp_path, [_inline()])

    assert _run(claims_path, **VERTEX) == 0

    paper = json.loads((tmp_path / "out" / f"{FOLDER}_1" / f"{PAPER_A}.json").read_text("utf-8"))
    assert paper["header"]["replay"]["inline_claims"] is True
    assert paper["header"]["claims_scope"] == [1000]
    assert [c["index"] for c in paper["claims"]] == [1000]
    assert paper["claims"][0]["label"] == CLAIM_A0[4]
    assert sdk.kinds().count("audit") == 1


def test_default_run_header_has_no_inline_claims_key(tmp_path, monkeypatch):
    claims_path = _setup(tmp_path, monkeypatch, FakeSdk())
    assert _run(claims_path) == 0
    paper = json.loads((tmp_path / "out" / "exp1_medium_1" / f"{PAPER_A}.json").read_text("utf-8"))
    assert "inline_claims" not in paper["header"]["replay"]


def test_vertex_run_without_inline_claims_has_no_inline_claims_key(tmp_path, monkeypatch):
    claims_path = _setup(tmp_path, monkeypatch, FakeSdk())
    assert _run(claims_path, **VERTEX) == 0
    paper = json.loads((tmp_path / "out" / f"{FOLDER}_1" / f"{PAPER_A}.json").read_text("utf-8"))
    assert "inline_claims" not in paper["header"]["replay"]


def test_a_bad_inline_entry_aborts_the_run_before_any_request(tmp_path, monkeypatch, capsys):
    sdk = FakeSdk()
    _setup(tmp_path, monkeypatch, sdk)
    claims_path = _write_claims(tmp_path, [_inline(index=3)])

    assert _run(claims_path, **VERTEX) == 1

    assert "ABORT" in capsys.readouterr().out
    assert sdk.calls == [] and _folders(tmp_path) == []


def test_default_run_output_is_identical_with_out_tag_none(tmp_path, monkeypatch):
    """out_tag=None (what the parser gives without the flag) is the same as an args object that never had it."""
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)

    def papers() -> dict[str, bytes]:
        folder = tmp_path / "out" / "exp1_medium_1"
        return {p.name: p.read_bytes() for p in sorted(folder.glob("arxiv-*.json"))}

    assert _run(claims_path) == 0
    without_attribute = papers()
    assert set(without_attribute) == {f"{PAPER_A}.json", f"{PAPER_B}.json"}

    for path in (tmp_path / "out" / "exp1_medium_1").glob("*.json"):
        path.unlink()
    assert _run(claims_path, out_tag=None) == 0
    assert _folders(tmp_path) == ["exp1_medium_1"]
    assert papers() == without_attribute


# --- --out-tag -----------------------------------------------------------------------------------------

def test_out_tag_names_the_output_folders(tmp_path, monkeypatch):
    claims_path = _setup(tmp_path, monkeypatch, FakeSdk())
    assert _run(claims_path, repeat=2, out_tag=TAG, **VERTEX) == 0
    assert _folders(tmp_path) == [f"{FOLDER}-{TAG}_1", f"{FOLDER}-{TAG}_2"]


def test_out_tag_leaves_the_untagged_baseline_folder_alone(tmp_path, monkeypatch):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    baseline = tmp_path / "out" / f"{FOLDER}_1"
    baseline.mkdir(parents=True)
    (baseline / "marker.txt").write_text("KEEP", encoding="utf-8")

    assert _run(claims_path, out_tag=TAG, **VERTEX) == 0   # the untagged folder exists, the tagged one does not

    assert _folders(tmp_path) == [f"{FOLDER}-{TAG}_1", f"{FOLDER}_1"]
    assert [p.name for p in baseline.iterdir()] == ["marker.txt"]


def test_out_tag_existing_folder_aborts_before_any_request(tmp_path, monkeypatch, capsys):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    existing = tmp_path / "out" / f"{FOLDER}-{TAG}_1"
    existing.mkdir(parents=True)
    (existing / "marker.txt").write_text("KEEP", encoding="utf-8")

    assert _run(claims_path, out_tag=TAG, **VERTEX) == 1

    assert "refusing to overwrite" in capsys.readouterr().out
    assert sdk.calls == []
    assert [p.name for p in existing.iterdir()] == ["marker.txt"]


def test_out_tag_estimate_fails_when_the_tagged_folder_exists(tmp_path, monkeypatch, capsys):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    (tmp_path / "out" / f"{FOLDER}-{TAG}_1").mkdir(parents=True)

    assert _run(claims_path, estimate=True, out_tag=TAG, **VERTEX) == 1

    out = capsys.readouterr().out
    assert "refusing to overwrite" in out and "--estimate:" not in out
    assert sdk.calls == []


def test_out_tag_estimate_passes_when_the_tagged_folders_are_free(tmp_path, monkeypatch, capsys):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, estimate=True, repeat=3, out_tag=TAG, **VERTEX) == 0
    assert "--estimate:" in capsys.readouterr().out
    assert sdk.calls == [] and _folders(tmp_path) == []


def test_estimate_without_out_tag_ignores_existing_folders(tmp_path, monkeypatch, capsys):
    """Today's behaviour, unchanged: only a tagged run checks the folders at --estimate."""
    claims_path = _setup(tmp_path, monkeypatch, FakeSdk())
    (tmp_path / "out" / f"{FOLDER}_1").mkdir(parents=True)
    assert _run(claims_path, estimate=True, **VERTEX) == 0
    assert "--estimate:" in capsys.readouterr().out


def test_out_tag_is_refused_on_a_default_run(tmp_path, monkeypatch, capsys):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, out_tag=TAG) == 1
    assert "--out-tag" in capsys.readouterr().out
    assert sdk.calls == [] and _folders(tmp_path) == []


@pytest.mark.parametrize("bad", ["a_b", "a/b", "a b", "", "x.y"])
def test_out_tag_rejects_other_characters(tmp_path, monkeypatch, capsys, bad):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, out_tag=bad, **VERTEX) == 1
    assert "--out-tag" in capsys.readouterr().out
    assert sdk.calls == [] and _folders(tmp_path) == []


def test_parser_out_tag_defaults_to_none():
    parser = replay_audit._build_parser()
    assert parser.parse_args(["--level", "medium"]).out_tag is None
    assert parser.parse_args(["--level", "medium", "--out-tag", TAG]).out_tag == TAG


# --- the frozen prompt ---------------------------------------------------------------------------------

def test_flag_off_prompt_hash_is_cb3272cce551():
    assert replay_audit.EXPECTED_PROMPT_HASH == "cb3272cce551"
    assert get_prompt_version() == "cb3272cce551"
