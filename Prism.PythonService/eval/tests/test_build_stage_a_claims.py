"""Unit tests for eval/build_stage_a_claims.py, mainly its --full-check mode.

Offline: build() is patched with invented rows and the expected row counts are patched down, so no
dev_eval / match map / fixture is read and nothing outside tmp_path is written."""
import json
import sys

import pytest

from eval import build_stage_a_claims as mod


def _entry(row_id, paper_id, claim_index):
    return {"row_id": row_id, "paper_id": paper_id, "claim_index": claim_index}


@pytest.fixture
def selected(monkeypatch):
    """2 refusal rows + 3 S rows. P1-S1 shares P1-R1's claim, so 4 distinct claims."""
    rows = [
        _entry("P2-S1", "arxiv-2.0v1", 0),
        _entry("P1-R2", "arxiv-1.0v1", 9),
        _entry("P1-S1", "arxiv-1.0v1", 4),
        _entry("P1-R1", "arxiv-1.0v1", 4),
        _entry("P10-S2", "arxiv-2.0v1", 3),
    ]
    monkeypatch.setattr(mod, "build", lambda *args, **kwargs: list(rows))
    monkeypatch.setattr(mod, "FULL_CHECK_EXPECTED_R_ROWS", 2)
    monkeypatch.setattr(mod, "FULL_CHECK_EXPECTED_S_ROWS", 3)
    return rows


def _build_full_check():
    return mod.build_full_check(None, None, None)


# --- build_full_check ---------------------------------------------------------

def test_dedupes_by_paper_and_claim_and_keeps_sorted_row_ids(selected):
    entries, _ = _build_full_check()
    assert entries == [
        {"row_ids": ["P1-R1", "P1-S1"], "paper_id": "arxiv-1.0v1", "claim_index": 4},
        {"row_ids": ["P1-R2"], "paper_id": "arxiv-1.0v1", "claim_index": 9},
        {"row_ids": ["P2-S1"], "paper_id": "arxiv-2.0v1", "claim_index": 0},
        {"row_ids": ["P10-S2"], "paper_id": "arxiv-2.0v1", "claim_index": 3},
    ]
    assert sum(len(e["row_ids"]) for e in entries) == len(selected)  # no row lost, none duplicated


def test_shared_claims_are_returned(selected):
    _, shared = _build_full_check()
    assert shared == [{"row_ids": ["P1-R1", "P1-S1"], "paper_id": "arxiv-1.0v1", "claim_index": 4}]


def test_no_shared_claims_gives_an_empty_list(selected, monkeypatch):
    rows = [_entry("P1-R1", "a", 0), _entry("P1-R2", "a", 1), _entry("P1-S1", "a", 2), _entry("P1-S2", "a", 3),
            _entry("P1-S3", "a", 4)]
    monkeypatch.setattr(mod, "build", lambda *args, **kwargs: list(rows))
    entries, shared = _build_full_check()
    assert len(entries) == 5 and shared == []


def test_wrong_refusal_row_count_raises(selected, monkeypatch):
    monkeypatch.setattr(mod, "FULL_CHECK_EXPECTED_R_ROWS", 3)
    with pytest.raises(ValueError, match="expected 3 refusal rows with a claim, found 2"):
        _build_full_check()


def test_wrong_s_row_count_raises(selected, monkeypatch):
    monkeypatch.setattr(mod, "FULL_CHECK_EXPECTED_S_ROWS", 4)
    with pytest.raises(ValueError, match="expected 4 S rows with a claim, found 3"):
        _build_full_check()


def test_unrecognised_row_id_raises(selected, monkeypatch):
    rows = list(selected) + [_entry("X-1", "arxiv-3.0v1", 0)]
    monkeypatch.setattr(mod, "build", lambda *args, **kwargs: list(rows))
    with pytest.raises(ValueError, match="X-1"):
        _build_full_check()


@pytest.mark.parametrize("bad_id", ["P1-R1x", "xP1-S1", "P1-S", "P-R1"])
def test_row_id_patterns_are_anchored(selected, monkeypatch, bad_id):
    rows = list(selected) + [_entry(bad_id, "arxiv-3.0v1", 0)]
    monkeypatch.setattr(mod, "build", lambda *args, **kwargs: list(rows))
    with pytest.raises(ValueError, match="neither refusal"):
        _build_full_check()


def test_group_by_claim_is_the_shared_dedupe():
    entries, shared = mod.group_by_claim([_entry("B-2", "p", 1), _entry("B-1", "p", 1), _entry("A-1", "a", 0)])
    assert entries == [
        {"row_ids": ["A-1"], "paper_id": "a", "claim_index": 0},
        {"row_ids": ["B-1", "B-2"], "paper_id": "p", "claim_index": 1},
    ]
    assert shared == [entries[1]]


def test_check_new_output_path(tmp_path, monkeypatch):
    stage_a = tmp_path / "stage_a.json"
    monkeypatch.setattr(mod, "DEFAULT_OUTPUT_PATH", stage_a)
    existing = tmp_path / "exists.json"
    existing.write_text("x", encoding="utf-8")
    assert "requires an explicit --output-path" in mod.check_new_output_path(None)
    assert mod.check_new_output_path(None, flag="other").startswith("other requires")
    assert "must not write the Stage A file" in mod.check_new_output_path(stage_a)
    assert "already exists" in mod.check_new_output_path(existing)
    assert mod.check_new_output_path(tmp_path / "new.json") is None


# --- the --full-check CLI -------------------------------------------------------

@pytest.fixture
def stage_a(tmp_path, monkeypatch):
    """The Stage A file, redirected into tmp_path (and pre-filled) so the tests can prove it is never touched."""
    path = tmp_path / "exp1_stage_a_claims.json"
    path.write_text("STAGE-A-UNTOUCHED", encoding="utf-8")
    monkeypatch.setattr(mod, "DEFAULT_OUTPUT_PATH", path)
    return path


def _main(monkeypatch, *argv):
    monkeypatch.setattr(sys, "argv", ["build_stage_a_claims", *argv])
    mod.main()


def test_full_check_requires_an_explicit_output_path(selected, stage_a, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        _main(monkeypatch, "--full-check")
    assert exc.value.code == 1
    assert "requires an explicit --output-path" in capsys.readouterr().out
    assert stage_a.read_text(encoding="utf-8") == "STAGE-A-UNTOUCHED"


def test_full_check_refuses_the_stage_a_file(selected, stage_a, monkeypatch, capsys):
    with pytest.raises(SystemExit) as exc:
        _main(monkeypatch, "--full-check", "--output-path", str(stage_a))
    assert exc.value.code == 1
    assert "must not write the Stage A file" in capsys.readouterr().out
    assert stage_a.read_text(encoding="utf-8") == "STAGE-A-UNTOUCHED"


def test_full_check_refuses_an_existing_output_file(selected, stage_a, tmp_path, monkeypatch, capsys):
    out = tmp_path / "full.json"
    out.write_text("KEEP", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        _main(monkeypatch, "--full-check", "--output-path", str(out))
    assert exc.value.code == 1
    assert "already exists" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == "KEEP"


def test_full_check_writes_entries_and_prints_count_and_shared_claims(selected, stage_a, tmp_path, monkeypatch, capsys):
    out = tmp_path / "full.json"
    with pytest.raises(SystemExit) as exc:
        _main(monkeypatch, "--full-check", "--output-path", str(out))
    assert exc.value.code == 0
    entries, _ = _build_full_check()
    assert json.loads(out.read_text(encoding="utf-8")) == entries
    text = capsys.readouterr().out
    assert "Full-check set: 4 claims (2 refusal rows + 3 S rows, 1 shared claims)" in text
    assert "shared: arxiv-1.0v1 claim #4: P1-R1, P1-S1" in text
    assert f"wrote {out} (4 claims)" in text
    assert stage_a.read_text(encoding="utf-8") == "STAGE-A-UNTOUCHED"


def test_full_check_count_mismatch_writes_no_file(selected, stage_a, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mod, "FULL_CHECK_EXPECTED_S_ROWS", 99)
    out = tmp_path / "full.json"
    with pytest.raises(SystemExit) as exc:
        _main(monkeypatch, "--full-check", "--output-path", str(out))
    assert exc.value.code == 1
    assert "expected 99 S rows with a claim, found 3" in capsys.readouterr().out
    assert not out.exists()
    assert stage_a.read_text(encoding="utf-8") == "STAGE-A-UNTOUCHED"


# --- legacy mode (no flag) is unchanged -----------------------------------------

def test_default_output_path_is_still_the_stage_a_file():
    assert mod.DEFAULT_OUTPUT_PATH.name == "exp1_stage_a_claims.json"
    assert mod.DEFAULT_OUTPUT_PATH.parent.name == "evals"


def test_legacy_mode_writes_the_flat_row_id_list_to_the_default_path(selected, stage_a, monkeypatch, capsys):
    _main(monkeypatch)
    assert json.loads(stage_a.read_text(encoding="utf-8")) == selected
    out = capsys.readouterr().out
    assert "Resolved 5 Stage A claims:" in out
    assert f"wrote {stage_a} (5 claims)" in out


def test_legacy_mode_honours_an_explicit_output_path(selected, stage_a, tmp_path, monkeypatch):
    out = tmp_path / "elsewhere.json"
    _main(monkeypatch, "--output-path", str(out))
    assert json.loads(out.read_text(encoding="utf-8")) == selected
    assert stage_a.read_text(encoding="utf-8") == "STAGE-A-UNTOUCHED"
