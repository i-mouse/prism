"""Held-out mode (metadata.held_out=true in the loaded eval file): the runner
prints raw x/N counts with no percentage and no threshold/floor verdict, and
its exit code means only "the run is usable" (something scored, map fully
covered). The same data loaded from a file without held_out keeps the golden
gating behaviour. Offline - fixture mode, no matcher, no DB."""
import argparse
import asyncio
import json
from pathlib import Path

from eval import matrix_runner


def _write_eval_file(path: Path, held_out: bool) -> None:
    metadata: dict = {"name": "Synthetic"}
    if held_out:
        metadata["held_out"] = True
    path.write_text(
        json.dumps(
            {
                "metadata": metadata,
                "papers": [
                    {
                        "paper_id": "paper-a",
                        "filename": "paper-a.pdf",
                        "expected_matrix": [
                            {"id": "E1", "expected_label": "supported", "grounding_negative": False},
                            {"id": "E2", "expected_label": "not_supported", "grounding_negative": True},
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _write_fixture(fixture_dir: Path) -> None:
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "paper-a.json").write_text(
        json.dumps(
            {
                "header": {"prompt_hash": "abc123", "paper_id": "paper-a", "filename": "paper-a.pdf"},
                "claims": [{"index": 0, "label": "supported", "claim_summary": "x", "grounding_status": "Pass"}],
                "matches": [{"expected_id": "E1", "actual_index": 0}, {"expected_id": "E2", "actual_index": None}],
            }
        ),
        encoding="utf-8",
    )


def _write_match_map(path: Path, complete: bool) -> None:
    rows = {"E1": {"claim_fingerprint": "f1"}, "E2": {"confirmed_no_match": True} if complete else {}}
    path.write_text(
        json.dumps({"metadata": {"prompt_hash": None, "fixture_file": None, "schema_version": 1}, "rows": rows}),
        encoding="utf-8",
    )


def _run(tmp_path, monkeypatch, held_out: bool, complete_map: bool) -> int:
    matrix_path = tmp_path / "eval.json"
    fixture_dir = tmp_path / "fixtures"
    match_map_path = tmp_path / "custom_map.json"
    _write_eval_file(matrix_path, held_out)
    _write_fixture(fixture_dir)
    _write_match_map(match_map_path, complete_map)

    monkeypatch.setattr(matrix_runner, "get_prompt_version", lambda: "abc123")
    monkeypatch.setattr(
        matrix_runner, "_write_log", lambda *a, **k: Path(matrix_runner.__file__).parent.parent / "logs" / "test.json"
    )

    args = argparse.Namespace(
        source="fixture",
        paper="all",
        repeat=1,
        matrix_path=matrix_path,
        fixture_dir=fixture_dir,
        match_map_path=match_map_path,
        verbose=False,
    )
    return asyncio.run(matrix_runner._run(args))


def test_held_out_prints_raw_counts_without_verdict(tmp_path, monkeypatch, capsys):
    exit_code = _run(tmp_path, monkeypatch, held_out=True, complete_map=True)

    out = capsys.readouterr().out
    assert "HELD-OUT" in out
    assert "Refusal-family:    0/1" in out
    assert "Strict-label:      0/1" in out
    assert "Positive hits:     1/1" in out
    assert "False rejections:  0/1" in out
    assert "%" not in out
    assert "PASS" not in out
    assert "FAIL" not in out
    assert "floor" not in out
    assert "[OK]" not in out
    # Positive hits 1 < default floor 10 and refusal 0/1 < default 0.70 would
    # fail the golden gate; held-out exit 0 only means "usable run".
    assert exit_code == 0


def test_held_out_incomplete_map_withholds_refusal_count_and_exits_1(tmp_path, monkeypatch, capsys):
    exit_code = _run(tmp_path, monkeypatch, held_out=True, complete_map=False)

    out = capsys.readouterr().out
    assert "REFUSAL-FAMILY COUNT WITHHELD — match map coverage 1/2." in out
    assert "Refusal-family:" not in out
    assert "%" not in out
    assert exit_code == 1


def test_same_data_without_held_out_keeps_golden_gate(tmp_path, monkeypatch, capsys):
    exit_code = _run(tmp_path, monkeypatch, held_out=False, complete_map=True)

    out = capsys.readouterr().out
    assert "HELD-OUT" not in out
    assert "Refusal-family rate: 0/1 (0%) [FAIL vs 70% threshold]" in out
    assert "BELOW FLOOR - mark invalid" in out
    assert exit_code == 1


def test_warnings_name_the_loaded_match_map(tmp_path, monkeypatch, capsys):
    _run(tmp_path, monkeypatch, held_out=True, complete_map=True)
    capsys.readouterr()

    (tmp_path / "custom_map.json").write_text("{not json", encoding="utf-8")
    args = argparse.Namespace(
        source="fixture",
        paper="all",
        repeat=1,
        matrix_path=tmp_path / "eval.json",
        fixture_dir=tmp_path / "fixtures",
        match_map_path=tmp_path / "custom_map.json",
        verbose=False,
    )
    asyncio.run(matrix_runner._run(args))

    out = capsys.readouterr().out
    assert "WARNING: custom_map.json could not be used" in out
    assert "match_map.json" not in out
