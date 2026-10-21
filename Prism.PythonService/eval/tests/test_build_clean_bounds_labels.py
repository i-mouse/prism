"""Synthetic-fixture tests for eval/build_clean_bounds_labels.py. No LLM
calls, no network, no real K6/K7 data (fake in-memory/tmp data only).

Run only these tests (plus the rest of eval/tests/):
  uv run pytest eval/tests/test_build_clean_bounds_labels.py -v
"""
import csv
from pathlib import Path

import pytest

from eval import build_clean_bounds_labels as bcbl
from eval import score_label_pack as slp


def _write_csv(path: Path, rows: list[tuple[str, str, str]]) -> Path:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["item_id", "label", "note"])
        for row in rows:
            writer.writerow(row)
    return path


def _template(tmp_path: Path, item_ids: list[str], name: str = "k6_labels.csv") -> Path:
    return _write_csv(tmp_path / name, [(item_id, "", "") for item_id in item_ids])


def _read_rows(path: Path) -> dict[str, tuple[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {row["item_id"]: (row["label"], row["note"]) for row in csv.DictReader(f)}


# ---------------------------------------------------------------------------
# core merge_item_bounds rules
# ---------------------------------------------------------------------------

def test_k6_both_agree_claim_uses_ai_label_in_both_bounds():
    result = bcbl.merge_item_bounds("k6", "A", "A")
    assert result["category"] == "agreed"
    assert result["low_label"] == result["high_label"] == "A"
    assert result["low_note"] == result["high_note"] == "ai_agreed"


def test_k6_both_agree_not_claim_different_letters_edge_case():
    result = bcbl.merge_item_bounds("k6", "B", "C")
    assert result["category"] == "agreed"
    assert result["low_label"] == result["high_label"] == "B"  # ChatGPT's letter
    assert result["low_note"] == result["high_note"] == "agreed_not_claim chatgpt=B gemini=C"


def test_k6_disagree_gets_fixed_worst_and_best_labels():
    result = bcbl.merge_item_bounds("k6", "A", "B")
    assert result["category"] == "disagreed"
    assert result["low_label"] == "unsure"
    assert result["high_label"] == "A"
    assert result["low_note"] == "ai_disagreed_worst"
    assert result["high_note"] == "ai_disagreed_best"


def test_k6_either_unsure_counts_as_disagreement():
    result = bcbl.merge_item_bounds("k6", "A", "unsure")
    assert result["category"] == "disagreed"
    assert result["low_label"] == "unsure"
    assert result["high_label"] == "A"


def test_k7_same_and_same_agree():
    result = bcbl.merge_item_bounds("k7", "same", "same")
    assert result["category"] == "agreed"
    assert result["low_label"] == result["high_label"] == "same"
    assert result["low_note"] == result["high_note"] == "ai_agreed"


def test_k7_disagree_gets_fixed_worst_and_best_labels():
    result = bcbl.merge_item_bounds("k7", "same", "broader")
    assert result["category"] == "disagreed"
    assert result["low_label"] == "different"
    assert result["high_label"] == "same"
    assert result["low_note"] == "ai_disagreed_worst"
    assert result["high_note"] == "ai_disagreed_best"


def test_k7_either_unsure_counts_as_disagreement():
    result = bcbl.merge_item_bounds("k7", "same", "unsure")
    assert result["category"] == "disagreed"
    assert result["low_label"] == "different"
    assert result["high_label"] == "same"


# ---------------------------------------------------------------------------
# build_bounds_pack: counts, row ordering, never raises on disagreement
# ---------------------------------------------------------------------------

def test_build_bounds_pack_counts_and_rows():
    item_ids = ["L001", "L002"]
    chatgpt = {"L001": "A", "L002": "A"}
    gemini = {"L001": "A", "L002": "B"}
    result = bcbl.build_bounds_pack("k6", chatgpt, gemini, item_ids)
    assert result["agreed"] == 1
    assert result["disagreed"] == 1
    low = {item_id: (label, note) for item_id, label, note in result["low_rows"]}
    high = {item_id: (label, note) for item_id, label, note in result["high_rows"]}
    assert low["L001"] == ("A", "ai_agreed")
    assert high["L001"] == ("A", "ai_agreed")
    assert low["L002"] == ("unsure", "ai_disagreed_worst")
    assert high["L002"] == ("A", "ai_disagreed_best")


def test_build_bounds_pack_never_raises_on_disagreement():
    item_ids = ["L001"]
    chatgpt = {"L001": "A"}
    gemini = {"L001": "B"}
    result = bcbl.build_bounds_pack("k6", chatgpt, gemini, item_ids)  # no review file, no raise
    assert result["disagreed"] == 1


def test_build_bounds_pack_row_order_matches_template_order():
    item_ids = ["L003", "L001", "L002"]
    chatgpt = {item_id: "A" for item_id in item_ids}
    gemini = {item_id: "A" for item_id in item_ids}
    result = bcbl.build_bounds_pack("k6", chatgpt, gemini, item_ids)
    assert [item_id for item_id, _l, _n in result["low_rows"]] == item_ids
    assert [item_id for item_id, _l, _n in result["high_rows"]] == item_ids


# ---------------------------------------------------------------------------
# item-id mismatch / duplicate id raise, no file written
# ---------------------------------------------------------------------------

def test_missing_item_in_chatgpt_raises():
    item_ids = ["L001", "L002"]
    chatgpt = {"L001": "A"}  # L002 missing
    gemini = {"L001": "A", "L002": "A"}
    with pytest.raises(ValueError, match="chatgpt vs labels template"):
        bcbl.build_bounds_pack("k6", chatgpt, gemini, item_ids)


def test_extra_item_in_gemini_raises():
    item_ids = ["L001"]
    chatgpt = {"L001": "A"}
    gemini = {"L001": "A", "L999": "A"}  # L999 not in template
    with pytest.raises(ValueError, match="gemini vs labels template"):
        bcbl.build_bounds_pack("k6", chatgpt, gemini, item_ids)


def test_duplicate_item_id_in_csv_raises(tmp_path):
    path = _write_csv(tmp_path / "dup.csv", [("L001", "A", ""), ("L001", "B", "")])
    with pytest.raises(ValueError, match="duplicate item_id"):
        bcbl.read_label_csv(path, bcbl.K6_LABELS, require_labels=True)


# ---------------------------------------------------------------------------
# _key path refusal
# ---------------------------------------------------------------------------

def test_key_path_refused_as_chatgpt_arg(tmp_path, monkeypatch):
    key_dir = tmp_path / "_key"
    key_dir.mkdir()
    fake_key = _write_csv(key_dir / "k6_chatgpt.csv", [("L001", "A", "")])
    gemini = _write_csv(tmp_path / "gemini.csv", [("L001", "A", "")])
    template = _template(tmp_path, ["L001"])
    low_out = tmp_path / "k6_labels_low.csv"
    high_out = tmp_path / "k6_labels_high.csv"

    monkeypatch.setattr("sys.argv", [
        "build_clean_bounds_labels", "--mode", "k6",
        "--chatgpt", str(fake_key), "--gemini", str(gemini),
        "--template", str(template), "--low-out", str(low_out), "--high-out", str(high_out),
    ])
    with pytest.raises(ValueError, match="_key"):
        bcbl.main()


# ---------------------------------------------------------------------------
# main(): writes both files, every row gets a non-empty note, round-trips
# through score_label_pack.load_labels
# ---------------------------------------------------------------------------

def test_main_writes_both_bound_files_with_notes_and_round_trips(tmp_path, monkeypatch):
    item_ids = [f"L{i:03d}" for i in range(5)]
    # L000, L001 agree claim; L002 agreed-not-claim edge case; L003 disagree; L004 unsure
    chatgpt = _write_csv(tmp_path / "chatgpt.csv", [
        ("L000", "A", ""), ("L001", "A", ""), ("L002", "B", ""), ("L003", "A", ""), ("L004", "A", ""),
    ])
    gemini = _write_csv(tmp_path / "gemini.csv", [
        ("L000", "A", ""), ("L001", "A", ""), ("L002", "C", ""), ("L003", "B", ""), ("L004", "unsure", ""),
    ])
    template = _template(tmp_path, item_ids)
    low_out = tmp_path / "k6_labels_low.csv"
    high_out = tmp_path / "k6_labels_high.csv"

    monkeypatch.setattr("sys.argv", [
        "build_clean_bounds_labels", "--mode", "k6",
        "--chatgpt", str(chatgpt), "--gemini", str(gemini),
        "--template", str(template), "--low-out", str(low_out), "--high-out", str(high_out),
    ])
    bcbl.main()

    low_rows = _read_rows(low_out)
    high_rows = _read_rows(high_out)
    assert set(low_rows) == set(high_rows) == set(item_ids)
    assert all(note for _label, note in low_rows.values())
    assert all(note for _label, note in high_rows.values())

    assert low_rows["L000"] == ("A", "ai_agreed")
    assert low_rows["L002"] == ("B", "agreed_not_claim chatgpt=B gemini=C")
    assert low_rows["L003"] == ("unsure", "ai_disagreed_worst")
    assert high_rows["L003"] == ("A", "ai_disagreed_best")
    assert low_rows["L004"] == ("unsure", "ai_disagreed_worst")
    assert high_rows["L004"] == ("A", "ai_disagreed_best")

    # template itself is untouched (read-only input, never written to)
    template_rows = _read_rows(template)
    assert all(label == "" for label, _note in template_rows.values())

    for path, allowed in ((low_out, slp.K6_LABELS), (high_out, slp.K6_LABELS)):
        loaded, errors = slp.load_labels(path, allowed)
        assert errors == []
        assert set(loaded) == set(item_ids)


def test_main_k7_writes_both_bound_files(tmp_path, monkeypatch):
    item_ids = ["L000", "L001"]
    chatgpt = _write_csv(tmp_path / "chatgpt.csv", [("L000", "same", ""), ("L001", "same", "")])
    gemini = _write_csv(tmp_path / "gemini.csv", [("L000", "same", ""), ("L001", "broader", "")])
    template = _template(tmp_path, item_ids, name="k7_labels.csv")
    low_out = tmp_path / "k7_labels_low.csv"
    high_out = tmp_path / "k7_labels_high.csv"

    monkeypatch.setattr("sys.argv", [
        "build_clean_bounds_labels", "--mode", "k7",
        "--chatgpt", str(chatgpt), "--gemini", str(gemini),
        "--template", str(template), "--low-out", str(low_out), "--high-out", str(high_out),
    ])
    bcbl.main()

    low_rows = _read_rows(low_out)
    high_rows = _read_rows(high_out)
    assert low_rows["L000"] == ("same", "ai_agreed")
    assert low_rows["L001"] == ("different", "ai_disagreed_worst")
    assert high_rows["L001"] == ("same", "ai_disagreed_best")
