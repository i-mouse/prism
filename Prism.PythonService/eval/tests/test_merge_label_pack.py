"""Synthetic-fixture tests for eval/merge_label_pack.py. No LLM calls, no
network, no real K6/K7 data (fake in-memory/tmp data only).

Run only these tests (plus the rest of eval/tests/):
  uv run pytest eval/tests/test_merge_label_pack.py -v
"""
import csv
from pathlib import Path

import pytest

from eval import merge_label_pack as mlp
from eval import score_label_pack as slp


def _write_csv(path: Path, rows: list[tuple[str, str, str]]) -> Path:
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["item_id", "label", "note"])
        for row in rows:
            writer.writerow(row)
    return path


def _k6_template(tmp_path: Path, item_ids: list[str], name: str = "k6_labels.csv") -> Path:
    return _write_csv(tmp_path / name, [(item_id, "", "") for item_id in item_ids])


def _read_rows(path: Path) -> dict[str, tuple[str, str]]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return {row["item_id"]: (row["label"], row["note"]) for row in csv.DictReader(f)}


# ---------------------------------------------------------------------------
# 1-3: core merge_item rules
# ---------------------------------------------------------------------------

def test_both_ais_agree_uses_ai_label():
    result = mlp.merge_item("k6", "A", "A", None)
    assert result["final_label"] == "A"
    assert result["category"] == "agreed"
    assert result["note"] == "ai_agreed"


def test_ais_disagree_uses_nitin_label():
    result = mlp.merge_item("k6", "A", "B", "D")
    assert result["final_label"] == "D"
    assert result["category"] == "disagreed"
    assert result["note"] == "nitin_disagreement"


def test_one_ai_unsure_uses_nitin_label():
    result = mlp.merge_item("k6", "A", "unsure", "A")
    assert result["final_label"] == "A"
    assert result["category"] == "disagreed"


def test_disagreement_missing_from_review_raises():
    with pytest.raises(ValueError, match="missing from the review"):
        mlp.merge_item("k6", "A", "B", None)


# ---------------------------------------------------------------------------
# 4: K6 claim/not-claim agreement rule, incl. the agreed-not-claim edge case
# ---------------------------------------------------------------------------

def test_k6_a_and_a_agree():
    result = mlp.merge_item("k6", "A", "A", None)
    assert result["category"] == "agreed"
    assert result["final_label"] == "A"


def test_k6_b_and_c_agree_as_not_claim_edge_case():
    result = mlp.merge_item("k6", "B", "C", None)
    assert result["category"] == "agreed"
    assert result["final_label"] == "B"  # ChatGPT's letter, per decision
    assert result["note"] == "agreed_not_claim chatgpt=B gemini=C"


def test_k6_a_and_b_disagree():
    result = mlp.merge_item("k6", "A", "B", "A")
    assert result["category"] == "disagreed"


# ---------------------------------------------------------------------------
# 5: K7 exact-label agreement rule
# ---------------------------------------------------------------------------

def test_k7_same_and_same_agree():
    result = mlp.merge_item("k7", "same", "same", None)
    assert result["category"] == "agreed"
    assert result["final_label"] == "same"
    assert result["note"] == "ai_agreed"


def test_k7_same_and_broader_disagree():
    result = mlp.merge_item("k7", "same", "broader", "broader")
    assert result["category"] == "disagreed"
    assert result["final_label"] == "broader"


# ---------------------------------------------------------------------------
# 6: spot-check PASS/FAIL gate, via merge_pack
# ---------------------------------------------------------------------------

def _k6_pack_with_spot_check_differs(n_differ: int) -> dict:
    """10 agreed A/A items used as the spot-check pool; n_differ of them get
    a Nitin review label in the opposite (not-claim) bucket."""
    item_ids = [f"L{i:03d}" for i in range(10)]
    chatgpt = {item_id: "A" for item_id in item_ids}
    gemini = {item_id: "A" for item_id in item_ids}
    review = {}
    for i, item_id in enumerate(item_ids):
        review[item_id] = "B" if i < n_differ else "A"
    return mlp.merge_pack("k6", chatgpt, gemini, review, item_ids)


def test_spot_check_2_of_10_differ_passes():
    result = _k6_pack_with_spot_check_differs(2)
    assert result["spot_check_total"] == 10
    assert result["spot_check_differ"] == 2
    assert result["spot_check_pass"] is True


def test_spot_check_3_of_10_differ_fails():
    result = _k6_pack_with_spot_check_differs(3)
    assert result["spot_check_differ"] == 3
    assert result["spot_check_pass"] is False


def test_main_writes_file_on_spot_check_pass(tmp_path, monkeypatch):
    item_ids = [f"L{i:03d}" for i in range(10)]
    chatgpt = _write_csv(tmp_path / "chatgpt.csv", [(i, "A", "") for i in item_ids])
    gemini = _write_csv(tmp_path / "gemini.csv", [(i, "A", "") for i in item_ids])
    review_rows = [(item_ids[i], "B" if i < 2 else "A", "") for i in range(10)]
    review = _write_csv(tmp_path / "review.csv", review_rows)
    labels = _k6_template(tmp_path, item_ids)

    monkeypatch.setattr("sys.argv", [
        "merge_label_pack", "--mode", "k6",
        "--chatgpt", str(chatgpt), "--gemini", str(gemini),
        "--review", str(review), "--labels", str(labels),
    ])
    mlp.main()
    rows = _read_rows(labels)
    assert all(label == "A" for label, _note in rows.values())


def test_main_does_not_write_file_on_spot_check_fail(tmp_path, monkeypatch, capsys):
    item_ids = [f"L{i:03d}" for i in range(10)]
    chatgpt = _write_csv(tmp_path / "chatgpt.csv", [(i, "A", "") for i in item_ids])
    gemini = _write_csv(tmp_path / "gemini.csv", [(i, "A", "") for i in item_ids])
    review_rows = [(item_ids[i], "B" if i < 3 else "A", "") for i in range(10)]
    review = _write_csv(tmp_path / "review.csv", review_rows)
    labels = _k6_template(tmp_path, item_ids)
    before = labels.read_text(encoding="utf-8-sig")

    monkeypatch.setattr("sys.argv", [
        "merge_label_pack", "--mode", "k6",
        "--chatgpt", str(chatgpt), "--gemini", str(gemini),
        "--review", str(review), "--labels", str(labels),
    ])
    with pytest.raises(SystemExit):
        mlp.main()
    assert labels.read_text(encoding="utf-8-sig") == before  # untouched
    out = capsys.readouterr().out
    assert "FAIL" in out
    for item_id in item_ids[:3]:
        assert item_id in out


# ---------------------------------------------------------------------------
# 7: Nitin "unsure" on a spot-check item always counts as a differ
# ---------------------------------------------------------------------------

def test_k6_spot_check_nitin_unsure_counts_as_not_claim():
    assert mlp.spot_check_differs("k6", "unsure", "A") is True  # unsure -> notclaim bucket != claim
    assert mlp.spot_check_differs("k6", "unsure", "B") is False  # unsure -> notclaim bucket == notclaim


def test_k7_spot_check_nitin_unsure_counts_as_not_same():
    assert mlp.spot_check_differs("k7", "unsure", "same") is True
    assert mlp.spot_check_differs("k7", "unsure", "broader") is True  # unsure never equals a real label


# ---------------------------------------------------------------------------
# 8: missing item, duplicate id, unknown label -> error, no file written
# ---------------------------------------------------------------------------

def test_missing_item_in_chatgpt_raises(tmp_path):
    item_ids = ["L001", "L002"]
    chatgpt = {"L001": "A"}  # L002 missing
    gemini = {"L001": "A", "L002": "A"}
    with pytest.raises(ValueError, match="chatgpt vs labels template"):
        mlp.merge_pack("k6", chatgpt, gemini, {}, item_ids)


def test_duplicate_item_id_in_csv_raises(tmp_path):
    path = _write_csv(tmp_path / "dup.csv", [("L001", "A", ""), ("L001", "B", "")])
    with pytest.raises(ValueError, match="duplicate item_id"):
        mlp.read_label_csv(path, mlp.K6_LABELS, require_labels=True)


def test_unknown_label_value_raises(tmp_path):
    path = _write_csv(tmp_path / "bad.csv", [("L001", "Z", "")])
    with pytest.raises(ValueError, match="not in allowed set"):
        mlp.read_label_csv(path, mlp.K6_LABELS, require_labels=True)


def test_main_missing_item_leaves_template_untouched(tmp_path, monkeypatch):
    chatgpt = _write_csv(tmp_path / "chatgpt.csv", [("L001", "A", "")])
    gemini = _write_csv(tmp_path / "gemini.csv", [("L001", "A", ""), ("L002", "A", "")])
    review = _write_csv(tmp_path / "review.csv", [])
    labels = _k6_template(tmp_path, ["L001", "L002"])
    before = labels.read_text(encoding="utf-8-sig")

    monkeypatch.setattr("sys.argv", [
        "merge_label_pack", "--mode", "k6",
        "--chatgpt", str(chatgpt), "--gemini", str(gemini),
        "--review", str(review), "--labels", str(labels),
    ])
    with pytest.raises(ValueError):
        mlp.main()
    assert labels.read_text(encoding="utf-8-sig") == before


# ---------------------------------------------------------------------------
# 9: an item is never dropped, regardless of any upstream NOT_FOUND flag
# (the flag itself lives only in the pack HTML / sealed key, never in these
# CSVs - this module's only obligation is to never drop the item_id)
# ---------------------------------------------------------------------------

def test_item_is_kept_in_output_even_when_standing_in_for_a_not_found_item():
    item_ids = ["L001", "L002"]  # L002 stands in for a NOT_FOUND item
    chatgpt = {"L001": "A", "L002": "A"}
    gemini = {"L001": "A", "L002": "A"}
    result = mlp.merge_pack("k6", chatgpt, gemini, {}, item_ids, expected_spot_check_total=None)
    output_ids = [item_id for item_id, _label, _note in result["rows"]]
    assert output_ids == item_ids  # present, not dropped, in template order


# ---------------------------------------------------------------------------
# 10: any input path containing "_key" is refused
# ---------------------------------------------------------------------------

def test_key_path_refused_as_chatgpt_arg(tmp_path, monkeypatch):
    key_dir = tmp_path / "_key"
    key_dir.mkdir()
    fake_key = _write_csv(key_dir / "k6_chatgpt.csv", [("L001", "A", "")])
    gemini = _write_csv(tmp_path / "gemini.csv", [("L001", "A", "")])
    review = _write_csv(tmp_path / "review.csv", [])
    labels = _k6_template(tmp_path, ["L001"])

    monkeypatch.setattr("sys.argv", [
        "merge_label_pack", "--mode", "k6",
        "--chatgpt", str(fake_key), "--gemini", str(gemini),
        "--review", str(review), "--labels", str(labels),
    ])
    with pytest.raises(ValueError, match="_key"):
        mlp.main()


def test_key_in_filename_alone_is_refused(tmp_path):
    with pytest.raises(ValueError, match="_key"):
        mlp._refuse_key_path(tmp_path / "k6_key.json")


# ---------------------------------------------------------------------------
# Decision #2: refuse to overwrite a template that already has labels
# ---------------------------------------------------------------------------

def test_refuses_to_write_if_template_already_has_a_label(tmp_path):
    path = _write_csv(tmp_path / "k6_labels.csv", [("L001", "A", ""), ("L002", "", "")])
    with pytest.raises(ValueError, match="already has non-blank label"):
        mlp.read_template(path)


# ---------------------------------------------------------------------------
# Decision #3: every output row carries a non-empty provenance note
# ---------------------------------------------------------------------------

def test_every_output_row_has_a_provenance_note():
    item_ids = ["L001", "L002", "L003"]
    chatgpt = {"L001": "A", "L002": "B", "L003": "A"}
    gemini = {"L001": "A", "L002": "C", "L003": "unsure"}
    review = {"L003": "A"}
    result = mlp.merge_pack("k6", chatgpt, gemini, review, item_ids, expected_spot_check_total=None)
    notes = {item_id: note for item_id, _label, note in result["rows"]}
    assert all(notes[item_id] for item_id in item_ids)
    assert notes["L001"] == "ai_agreed"
    assert notes["L002"] == "agreed_not_claim chatgpt=B gemini=C"
    assert notes["L003"] == "nitin_disagreement"


# ---------------------------------------------------------------------------
# Phase A fix 1: output format matches build_label_pack._write_csv exactly,
# and round-trips cleanly through score_label_pack.load_labels
# ---------------------------------------------------------------------------

def test_output_round_trips_through_score_label_pack_load_labels(tmp_path, monkeypatch):
    item_ids = [f"L{i:03d}" for i in range(10)]
    chatgpt = _write_csv(tmp_path / "chatgpt.csv", [(i, "A", "") for i in item_ids])
    gemini = _write_csv(tmp_path / "gemini.csv", [(i, "A", "") for i in item_ids])
    review = _write_csv(tmp_path / "review.csv", [(item_ids[i], "A", "") for i in range(10)])
    labels = _k6_template(tmp_path, item_ids)

    monkeypatch.setattr("sys.argv", [
        "merge_label_pack", "--mode", "k6",
        "--chatgpt", str(chatgpt), "--gemini", str(gemini),
        "--review", str(review), "--labels", str(labels),
    ])
    mlp.main()

    loaded, errors = slp.load_labels(labels, slp.K6_LABELS)
    assert errors == []
    assert loaded == {item_id: "A" for item_id in item_ids}


# ---------------------------------------------------------------------------
# Phase A fix 2: review strictness - blank label, unknown review item_id,
# spot-check total not exactly 10
# ---------------------------------------------------------------------------

def test_review_blank_label_refused(tmp_path, monkeypatch):
    item_ids = [f"L{i:03d}" for i in range(10)]
    chatgpt = _write_csv(tmp_path / "chatgpt.csv", [(i, "A", "") for i in item_ids])
    gemini = _write_csv(tmp_path / "gemini.csv", [(i, "A", "") for i in item_ids])
    # one review row present but never filled in
    review_rows = [(item_ids[i], "A" if i else "", "") for i in range(10)]
    review = _write_csv(tmp_path / "review.csv", review_rows)
    labels = _k6_template(tmp_path, item_ids)
    before = labels.read_text(encoding="utf-8-sig")

    monkeypatch.setattr("sys.argv", [
        "merge_label_pack", "--mode", "k6",
        "--chatgpt", str(chatgpt), "--gemini", str(gemini),
        "--review", str(review), "--labels", str(labels),
    ])
    with pytest.raises(ValueError, match="label is empty"):
        mlp.main()
    assert labels.read_text(encoding="utf-8-sig") == before


def test_review_item_id_not_in_template_refused():
    item_ids = ["L001", "L002"]
    chatgpt = {"L001": "A", "L002": "A"}
    gemini = {"L001": "A", "L002": "A"}
    review = {"L999": "A"}  # not in the template at all
    with pytest.raises(ValueError, match="not in labels template"):
        mlp.merge_pack("k6", chatgpt, gemini, review, item_ids, expected_spot_check_total=None)


def test_spot_check_total_not_10_refused():
    item_ids = [f"L{i:03d}" for i in range(5)]
    chatgpt = {item_id: "A" for item_id in item_ids}
    gemini = {item_id: "A" for item_id in item_ids}
    review = {item_id: "A" for item_id in item_ids}  # only 5 agreed+reviewed items, not 10
    with pytest.raises(ValueError, match="expected exactly 10"):
        mlp.merge_pack("k6", chatgpt, gemini, review, item_ids)
