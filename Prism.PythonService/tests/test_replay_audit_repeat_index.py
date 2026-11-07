"""eval/replay_audit.py --repeat-index K: run only repeat K and write only folder _K, so a crashed repeat
can be re-run alone. Offline: fake SDK and invented text from tests/replay_fakes.py, nothing real is read.

The existing-folder guard belongs to non-default runs (--backend vertex / --auditor-model), so the guard
tests run on Vertex; the default-run test shows the flag does not change a default run's output."""
import argparse
import asyncio
import json

import pytest

from eval import replay_audit
from extraction import engine

import replay_fakes
from replay_fakes import MODEL, FakeSdk

VERTEX = dict(backend="vertex", vertex_project="proj-x", vertex_location="global")
FOLDER = f"exp1_medium_{MODEL}-vertex"   # + _<n>


def _args(claims_path, **overrides) -> argparse.Namespace:
    values = dict(
        level="medium", claims=str(claims_path), papers=None, repeat=1, estimate=False, dry_run=False,
        max_inr=None, cache=False,
    )
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


def test_without_the_flag_every_repeat_is_written(tmp_path, monkeypatch):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, repeat=2, **VERTEX) == 0
    assert _folders(tmp_path) == [f"{FOLDER}_1", f"{FOLDER}_2"]
    assert sdk.kinds().count("audit") == 2 * len(replay_fakes.CLAIMS)


def test_repeat_index_2_writes_only_folder_2(tmp_path, monkeypatch):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, repeat_index=2, **VERTEX) == 0
    assert _folders(tmp_path) == [f"{FOLDER}_2"]
    assert sdk.kinds().count("audit") == len(replay_fakes.CLAIMS)   # one repeat's worth of calls
    folder = tmp_path / "out" / f"{FOLDER}_2"
    assert (folder / "_summary.json").is_file()
    paper = json.loads((folder / f"{replay_fakes.PAPER_A}.json").read_text("utf-8"))
    assert paper["header"]["replay"]["repeat_index"] == 2


def test_an_existing_folder_is_still_refused_and_nothing_is_requested(tmp_path, monkeypatch, capsys):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    existing = tmp_path / "out" / f"{FOLDER}_2"
    existing.mkdir(parents=True)
    (existing / "marker.txt").write_text("KEEP", encoding="utf-8")

    assert _run(claims_path, repeat_index=2, **VERTEX) == 1

    assert "refusing to overwrite" in capsys.readouterr().out
    assert sdk.calls == []
    assert (existing / "marker.txt").read_text("utf-8") == "KEEP"
    assert sorted(p.name for p in existing.iterdir()) == ["marker.txt"]   # nothing was added
    assert _folders(tmp_path) == [f"{FOLDER}_2"]


def test_folders_of_other_repeats_do_not_block_a_single_repeat(tmp_path, monkeypatch):
    """The point of the flag: _1 and _3 are good, _2 crashed, so only _2 is re-run."""
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    for n in (1, 3):
        folder = tmp_path / "out" / f"{FOLDER}_{n}"
        folder.mkdir(parents=True)
        (folder / "marker.txt").write_text(f"KEEP{n}", encoding="utf-8")

    assert _run(claims_path, repeat_index=2, **VERTEX) == 0

    assert _folders(tmp_path) == [f"{FOLDER}_1", f"{FOLDER}_2", f"{FOLDER}_3"]
    for n in (1, 3):
        folder = tmp_path / "out" / f"{FOLDER}_{n}"
        assert sorted(p.name for p in folder.iterdir()) == ["marker.txt"]
        assert (folder / "marker.txt").read_text("utf-8") == f"KEEP{n}"


def test_repeat_index_with_repeat_above_one_aborts_before_any_request(tmp_path, monkeypatch, capsys):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, repeat=3, repeat_index=2, **VERTEX) == 1
    assert "--repeat-index" in capsys.readouterr().out
    assert sdk.calls == [] and _folders(tmp_path) == []


def test_repeat_index_with_repeat_one_is_allowed(tmp_path, monkeypatch):
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)
    assert _run(claims_path, repeat=1, repeat_index=3, **VERTEX) == 0
    assert _folders(tmp_path) == [f"{FOLDER}_3"]


def test_parser_accepts_1_to_3_defaults_to_none_and_rejects_the_rest():
    parser = replay_audit._build_parser()
    assert parser.parse_args(["--level", "high"]).repeat_index is None
    assert [parser.parse_args(["--level", "high", "--repeat-index", str(k)]).repeat_index for k in (1, 2, 3)] == [1, 2, 3]
    for bad in ("0", "4", "-1", "x"):
        with pytest.raises(SystemExit) as exc:
            parser.parse_args(["--level", "high", "--repeat-index", bad])
        assert exc.value.code == 2


def test_the_flag_does_not_change_a_default_run(tmp_path, monkeypatch):
    """A default (AI Studio) run writes exp1_medium_1 whether or not --repeat-index 1 is given, with the
    same paper files byte for byte (the summary carries call latencies from the shared pinned clock)."""
    sdk = FakeSdk()
    claims_path = _setup(tmp_path, monkeypatch, sdk)

    def papers() -> dict[str, bytes]:
        folder = tmp_path / "out" / "exp1_medium_1"
        return {p.name: p.read_bytes() for p in sorted(folder.glob("arxiv-*.json"))}

    assert _run(claims_path) == 0
    assert _folders(tmp_path) == ["exp1_medium_1"]
    without_flag = papers()
    assert set(without_flag) == {f"{replay_fakes.PAPER_A}.json", f"{replay_fakes.PAPER_B}.json"}

    (tmp_path / "out" / "exp1_medium_1" / "_summary.json").unlink()
    for path in (tmp_path / "out" / "exp1_medium_1").glob("*.json"):
        path.unlink()
    assert _run(claims_path, repeat_index=1) == 0
    assert _folders(tmp_path) == ["exp1_medium_1"]
    assert papers() == without_flag
