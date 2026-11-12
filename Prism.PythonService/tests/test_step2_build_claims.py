"""eval/step2/build_exp3_p2_claims.py on invented data: the pick rule, the r1/r2 text check, the output entries, the
overwrite guard and --check-text. Nothing real is read (no adjudication file, no key, no fixture, no paper text)."""
import csv
import json

import pytest

from eval.step2 import build_exp3_p2_claims as build

PAPER = "arxiv-9999.00001v1"
R1, R2 = "pass2_r1", "pass2_r2"


def _cand(r1=None, r2=None, paper=PAPER):
    """r1 / r2 = (pass, merged_index) or None for not present."""
    def run(spec):
        return {"present": False, "pass": None, "merged_index": None} if spec is None else \
            {"present": True, "pass": spec[0], "merged_index": spec[1]}
    return {"paper_id": paper, R1: run(r1), R2: run(r2)}


def _claims(texts):
    return [{"claim_text_verbatim": t, "claim_summary": f"summary of {t}", "pass": "pass2"} for t in texts]


def _loader(r1_texts, r2_texts):
    data = {R1: _claims(r1_texts), R2: _claims(r2_texts)}
    return lambda run, paper_id: data[run]


# --- select_pick ---------------------------------------------------------------------------------------

def test_picks_the_lowest_id_when_two_are_in_both_runs():
    key = {"C0308": _cand((2, 4), (2, 5)), "C0637": _cand((2, 1), (2, 2))}
    assert build.select_pick("P2-R4", ["C0637", "C0308"], key) == ("C0308", False)


def test_a_candidate_in_both_runs_beats_a_lower_id_in_one_run():
    key = {"C0001": _cand((2, 0), None), "C0002": _cand((2, 1), (2, 1))}
    assert build.select_pick("R", ["C0001", "C0002"], key) == ("C0002", False)


def test_a_pass1_candidate_is_excluded():
    key = {"C0001": _cand((1, 0), (1, 0)), "C0002": _cand((2, 1), (2, 1))}
    assert build.select_pick("R", ["C0001", "C0002"], key) == ("C0002", False)


def test_a_candidate_that_is_pass1_in_either_run_is_excluded():
    key = {"C0001": _cand((2, 0), (1, 0)), "C0002": _cand((2, 1), (2, 1))}
    assert build.select_pick("R", ["C0001", "C0002"], key) == ("C0002", False)


def test_none_in_both_runs_takes_the_lowest_r1_id_and_flags():
    key = {
        "C0003": _cand((2, 3), None), "C0005": _cand((2, 5), None),
        "C0009": _cand(None, (2, 9)),                      # r2 only: never taken
    }
    assert build.select_pick("R", ["C0009", "C0005", "C0003"], key) == ("C0003", True)


def test_no_pass2_candidate_in_r1_aborts():
    key = {"C0001": _cand((1, 0), (1, 0)), "C0009": _cand(None, (2, 9))}
    with pytest.raises(build.BuildError, match="no matched candidate"):
        build.select_pick("R", ["C0001", "C0009"], key)


def test_an_unknown_candidate_id_aborts():
    with pytest.raises(build.BuildError, match="C0404"):
        build.select_pick("R", ["C0404"], {})


# --- build_entries -------------------------------------------------------------------------------------

def test_entry_fields_and_claim_index_is_1000_plus_the_r1_index():
    key = {"C0233": _cand((2, 2), (2, 1))}
    load = _loader(["a", "b", "The claim text."], ["x", "The claim text."])
    entries = build.build_entries({"P2-R3": (PAPER, ["C0233"])}, key, load, row_ids=("P2-R3",))
    assert entries == [{
        "row_ids": ["P2-R3"], "paper_id": PAPER, "claim_index": 1002,
        "claim_text_verbatim": "The claim text.", "claim_summary": "summary of The claim text.",
        "candidate_id": "C0233", "r1_index": 2, "r2_index": 1, "flag": False,
    }]


def test_fallback_entry_has_r2_index_none_and_flag_true():
    key = {"C0003": _cand((2, 0), None)}
    entries = build.build_entries({"R1": (PAPER, ["C0003"])}, key, _loader(["only r1"], []), row_ids=("R1",))
    assert (entries[0]["r2_index"], entries[0]["flag"], entries[0]["claim_index"]) == (None, True, 1000)


def test_r1_r2_text_mismatch_aborts():
    key = {"C0001": _cand((2, 0), (2, 0))}
    with pytest.raises(build.BuildError, match="different text"):
        build.build_entries({"R1": (PAPER, ["C0001"])}, key, _loader(["Text one."], ["Text two."]), row_ids=("R1",))


def test_text_that_differs_only_by_normalization_is_not_a_mismatch():
    key = {"C0001": _cand((2, 0), (2, 0))}
    r1, r2 = ["It’s   a  claim."], ["It's a claim."]
    entries = build.build_entries({"R1": (PAPER, ["C0001"])}, key, _loader(r1, r2), row_ids=("R1",))
    assert entries[0]["claim_text_verbatim"] == r1[0]       # stored as in the r1 fixture


def test_a_row_without_a_match_or_missing_from_the_file_aborts():
    key = {"C0001": _cand((2, 0), (2, 0))}
    with pytest.raises(build.BuildError, match="no match"):
        build.build_entries({"R1": (PAPER, [])}, key, _loader(["t"], ["t"]), row_ids=("R1",))
    with pytest.raises(build.BuildError, match="not in the adjudication file"):
        build.build_entries({}, key, _loader(["t"], ["t"]), row_ids=("R1",))


def test_a_candidate_of_another_paper_aborts():
    key = {"C0001": _cand((2, 0), (2, 0), paper="arxiv-other")}
    with pytest.raises(build.BuildError, match="belongs to"):
        build.build_entries({"R1": (PAPER, ["C0001"])}, key, _loader(["t"], ["t"]), row_ids=("R1",))


def test_a_candidate_picked_by_two_rows_is_listed_once():
    key = {"C0001": _cand((2, 0), (2, 0))}
    rows = {"R1": (PAPER, ["C0001"]), "R2": (PAPER, ["C0001"])}
    entries = build.build_entries(rows, key, _loader(["t"], ["t"]), row_ids=("R1", "R2"))
    assert [e["row_ids"] for e in entries] == [["R1", "R2"]]


# --- check_text ----------------------------------------------------------------------------------------

PAPER_TEXT = "Intro. The controller reduces fatigue load on every model.\n\nResults. Gains were small."


def _entry(text, cid="C0001"):
    return {"row_ids": ["R1"], "paper_id": PAPER, "candidate_id": cid, "claim_text_verbatim": text}


def test_check_text_finds_a_present_claim_and_not_an_absent_one():
    found, absent = build.check_text(
        [_entry("The controller reduces fatigue load on every model."),
         _entry("Quantum spectroscopy yields unrelated astronomical results.", "C0002")],
        lambda paper_id: PAPER_TEXT,
    )
    assert found["found"] is True and found["score"] >= 88
    assert absent["found"] is False and absent["score"] < 88


def test_check_text_normalizes_both_sides():
    result = build.check_text([_entry("The controller reduces fatigue load on every model.")],
                              lambda paper_id: "The control-\nler reduces fatigue  load on every model.")
    assert result[0]["found"] is True


def test_check_text_loads_each_paper_once():
    calls = []
    build.check_text([_entry("The controller reduces fatigue load on every model."), _entry("Gains were small.", "C0002")],
                     lambda paper_id: calls.append(paper_id) or PAPER_TEXT)
    assert calls == [PAPER]


# --- main ----------------------------------------------------------------------------------------------

TEXTS = [f"Invented claim number {i} about turbine blade fatigue load." for i in range(6)] + [
    "Entirely unrelated quantum spectroscopy statement."
]


def _inputs(tmp_path):
    """7 rows (the fixed row list), one candidate each, both runs pass 2, merged index = row position."""
    key = {f"C{i:04d}": _cand((2, i), (2, i)) for i in range(7)}
    adjudication = tmp_path / "c1_adjudication.csv"
    with open(adjudication, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_ALL)
        writer.writerow(["row_id", "paper_id", "row_text", "match_ids", "note"])
        for i, row_id in enumerate(build.ROW_IDS):
            writer.writerow([row_id, PAPER, "row text", f"C{i:04d}", ""])
    key_path = tmp_path / "c1_key.json"
    key_path.write_text(json.dumps({"provenance": {}, "candidates": key}), encoding="utf-8")
    root = tmp_path / "exp3"
    for run in (R1, R2):
        (root / run).mkdir(parents=True)
        (root / run / f"{PAPER}_merged.json").write_text(json.dumps({"claims": _claims(TEXTS)}), encoding="utf-8")
    out = tmp_path / "claims.json"
    argv = ["--adjudication", str(adjudication), "--key", str(key_path), "--replay-root", str(root), "--out", str(out)]
    return argv, out


def test_main_writes_the_seven_entries(tmp_path):
    argv, out = _inputs(tmp_path)
    assert build.main(argv) == 0
    entries = json.loads(out.read_text(encoding="utf-8"))
    assert [e["row_ids"] for e in entries] == [[r] for r in build.ROW_IDS]
    assert [e["claim_index"] for e in entries] == [1000 + i for i in range(7)]
    assert all(e["flag"] is False and e["r1_index"] == e["r2_index"] for e in entries)
    assert set(entries[0]) == {"row_ids", "paper_id", "claim_index", "claim_text_verbatim", "claim_summary",
                               "candidate_id", "r1_index", "r2_index", "flag"}


def test_main_refuses_to_overwrite_a_different_file_without_force(tmp_path, capsys):
    argv, out = _inputs(tmp_path)
    out.write_text("[]", encoding="utf-8")
    assert build.main(argv) == 1
    assert "--force" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8") == "[]"
    assert build.main(argv + ["--force"]) == 0
    assert len(json.loads(out.read_text(encoding="utf-8"))) == 7


def test_main_with_an_identical_existing_output_is_not_an_error(tmp_path):
    argv, out = _inputs(tmp_path)
    assert build.main(argv) == 0
    before = out.read_bytes()
    assert build.main(argv) == 0
    assert out.read_bytes() == before


def test_main_aborts_and_writes_nothing_on_a_text_mismatch(tmp_path, capsys):
    argv, out = _inputs(tmp_path)
    changed = tmp_path / "exp3" / R2 / f"{PAPER}_merged.json"
    texts = list(TEXTS)
    texts[3] = "A different sentence altogether."
    changed.write_text(json.dumps({"claims": _claims(texts)}), encoding="utf-8")
    assert build.main(argv) == 1
    assert "different text" in capsys.readouterr().out
    assert not out.exists()


def test_check_text_exit_code_0_when_every_claim_is_found(tmp_path, capsys):
    argv, _out = _inputs(tmp_path)
    paper_text = " ".join(TEXTS)
    assert build.main(argv + ["--check-text"], load_text=lambda paper_id: paper_text) == 0
    assert "7 of 7 found" in capsys.readouterr().out


def test_check_text_exit_code_1_when_a_claim_is_not_found_and_no_paper_text_is_printed(tmp_path, capsys):
    argv, _out = _inputs(tmp_path)
    paper_text = "PAPER-TEXT-CANARY " + " ".join(TEXTS[:6])           # the 7th claim is not in it
    assert build.main(argv + ["--check-text"], load_text=lambda paper_id: paper_text) == 1
    printed = capsys.readouterr().out
    assert "found=NO" in printed and "6 of 7 found, 1 NOT FOUND" in printed
    assert "PAPER-TEXT-CANARY" not in printed
    assert "found=yes" in printed and "score=" in printed


def test_check_text_exit_code_1_when_the_paper_text_cannot_be_loaded(tmp_path, capsys):
    argv, _out = _inputs(tmp_path)

    def _missing(paper_id):
        raise OSError("no cached text")

    assert build.main(argv + ["--check-text"], load_text=_missing) == 1
    assert "cannot load paper text" in capsys.readouterr().out
