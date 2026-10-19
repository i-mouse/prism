"""Synthetic-fixture tests for eval/score_label_pack.py. No LLM calls, no
network.

Run only these tests (plus the rest of eval/tests/):
  uv run pytest eval/tests/test_score_label_pack.py -v
"""
import csv
import json
from pathlib import Path

import pytest

from eval import score_label_pack as slp


def _write_labels(tmp_path: Path, rows: list[tuple[str, str, str]]) -> Path:
    path = tmp_path / "labels.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["item_id", "label", "note"])
        for row in rows:
            writer.writerow(row)
    return path


def _key(item_ids: list[str], not_found: dict[str, bool] | None = None) -> dict[str, dict]:
    not_found = not_found or {}
    return {item_id: {"not_found": not_found.get(item_id, False)} for item_id in item_ids}


# ---------------------------------------------------------------------------
# load_labels / validate_against_key: refuse empty or out-of-set labels
# ---------------------------------------------------------------------------

def test_load_labels_rejects_empty_label(tmp_path):
    path = _write_labels(tmp_path, [("L001", "", "")])
    labels, errors = slp.load_labels(path, slp.K6_LABELS)
    assert "L001" not in labels
    assert errors


def test_load_labels_rejects_out_of_set_label(tmp_path):
    path = _write_labels(tmp_path, [("L001", "claim", "")])
    labels, errors = slp.load_labels(path, slp.K6_LABELS)
    assert "L001" not in labels
    assert errors


def test_validate_against_key_flags_missing_item(tmp_path):
    path = _write_labels(tmp_path, [("L001", "A", "")])
    labels, errors = slp.load_labels(path, slp.K6_LABELS)
    errors = slp.validate_against_key(labels, ["L001", "L002"], errors)
    assert any("L002" in e for e in errors)


def test_load_labels_accepts_full_valid_k6_set(tmp_path):
    path = _write_labels(tmp_path, [("L001", "A", ""), ("L002", "unsure", "")])
    labels, errors = slp.load_labels(path, slp.K6_LABELS)
    assert errors == []
    assert labels == {"L001": "A", "L002": "unsure"}


# ---------------------------------------------------------------------------
# K6 scoring: unsure as not-claim (gate) vs unsure as claim (report only)
# ---------------------------------------------------------------------------

def test_score_k6_unsure_counts_as_not_claim_for_gate():
    item_ids = [f"L{i:03d}" for i in range(30)]
    labels = {item_id: ("A" if i < 20 else "unsure") for i, item_id in enumerate(item_ids)}
    key = _key(item_ids)
    result = slp.score_k6(labels, key)
    assert result["counts"]["A"] == 20
    assert result["counts"]["unsure"] == 10
    assert result["precision_unsure_not_claim"] == pytest.approx(20 / 30)
    assert result["precision_unsure_claim"] == pytest.approx(30 / 30)
    assert result["pass"] is False  # 20/30 < 0.70 gate


def test_score_k6_pass_fail_edges_21_of_30_vs_20_of_30():
    item_ids = [f"L{i:03d}" for i in range(30)]

    labels_pass = {item_id: ("A" if i < 21 else "D") for i, item_id in enumerate(item_ids)}
    result_pass = slp.score_k6(labels_pass, _key(item_ids))
    assert result_pass["precision_unsure_not_claim"] == pytest.approx(0.70)
    assert result_pass["pass"] is True

    labels_fail = {item_id: ("A" if i < 20 else "D") for i, item_id in enumerate(item_ids)}
    result_fail = slp.score_k6(labels_fail, _key(item_ids))
    assert result_fail["pass"] is False


def test_score_k6_reports_not_found_count():
    item_ids = [f"L{i:03d}" for i in range(5)]
    labels = {item_id: "A" for item_id in item_ids}
    key = _key(item_ids, not_found={"L000": True, "L001": True})
    result = slp.score_k6(labels, key)
    assert result["not_found_count"] == 2


# ---------------------------------------------------------------------------
# K7 scoring: unsure counts as not-same; PASS/FAIL edges
# ---------------------------------------------------------------------------

def test_score_k7_unsure_counts_as_not_same():
    item_ids = [f"L{i:03d}" for i in range(5)]
    labels = {"L000": "same", "L001": "same", "L002": "same", "L003": "unsure", "L004": "same"}
    result = slp.score_k7(labels, _key(item_ids))
    assert result["not_same_count"] == 1
    assert result["pass"] is True


def test_score_k7_pass_fail_edges_1_vs_2_not_same():
    item_ids = [f"L{i:03d}" for i in range(30)]

    labels_pass = {item_id: "same" for item_id in item_ids}
    labels_pass[item_ids[0]] = "different"
    result_pass = slp.score_k7(labels_pass, _key(item_ids))
    assert result_pass["not_same_count"] == 1
    assert result_pass["pass"] is True

    labels_fail = dict(labels_pass)
    labels_fail[item_ids[1]] = "broader"
    result_fail = slp.score_k7(labels_fail, _key(item_ids))
    assert result_fail["not_same_count"] == 2
    assert result_fail["pass"] is False


# ---------------------------------------------------------------------------
# main(): end-to-end refusal on invalid/partial labels, writes score json
# ---------------------------------------------------------------------------

def test_main_refuses_to_score_partial_labels(tmp_path, capsys, monkeypatch):
    labels_path = _write_labels(tmp_path, [("L001", "A", ""), ("L002", "", "")])
    key_path = tmp_path / "k6_key.json"
    key_path.write_text(json.dumps({"items": {"L001": {"not_found": False}, "L002": {"not_found": False}}}), encoding="utf-8")

    monkeypatch.setattr(
        "sys.argv",
        ["score_label_pack", "--mode", "k6", "--labels", str(labels_path), "--key", str(key_path)],
    )
    with pytest.raises(SystemExit):
        slp.main()
    assert not (tmp_path / "k6_score.json").exists()


def test_main_writes_score_json_on_valid_labels(tmp_path, monkeypatch):
    item_ids = [f"L{i:03d}" for i in range(3)]
    labels_path = _write_labels(tmp_path, [(item_id, "A", "") for item_id in item_ids])
    key_path = tmp_path / "k6_key.json"
    key_path.write_text(
        json.dumps({"items": {item_id: {"not_found": False} for item_id in item_ids}}), encoding="utf-8"
    )

    monkeypatch.setattr(
        "sys.argv",
        ["score_label_pack", "--mode", "k6", "--labels", str(labels_path), "--key", str(key_path)],
    )
    slp.main()
    score_path = tmp_path / "k6_score.json"
    assert score_path.exists()
    data = json.loads(score_path.read_text(encoding="utf-8"))
    assert data["n"] == 3
    assert data["counts"]["A"] == 3
