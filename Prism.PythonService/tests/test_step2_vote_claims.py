"""eval/step2/vote_claims.py on three invented replay folders: RAW and EFFECTIVE labels per run, the 2-of-3 vote of each
(RAW is the primary result), fallback-served audits and the INVALID checks. No real fixture folder is read."""
import json

import pytest

from eval.step2 import vote_claims

PAPER = "arxiv-9999.00001v1"
AUDITOR = "gemini-3.6-flash"
FALLBACK = "gemini-3.1-flash-lite"
S, P, N = "supported", "partially_supported", "not_supported"


def _folder(root, n, claims, *, config=None, status="OK", prompt_hash="h1", scope=None):
    """claims = [(index, label, missing, served)]. Returns the folder path."""
    folder = root / f"exp1_x_{n}"
    folder.mkdir(parents=True)
    run_config = config if config is not None else {
        "backend": "vertex", "auditor_model": AUDITOR, "thinking_level": "medium", "other_models": {"a": "b"},
    }
    (folder / "_summary.json").write_text(json.dumps({"status": status, "run_config": run_config, "records": []}), encoding="utf-8")
    (folder / f"{PAPER}.json").write_text(json.dumps({
        "header": {"prompt_hash": prompt_hash, "claims_scope": scope if scope is not None else [c[0] for c in claims]},
        "claims": [{"index": i, "label": label, "missing": missing, "audit_model_served": served}
                   for i, label, missing, served in claims],
        "matches": [],
    }), encoding="utf-8")
    return folder


def _claims_file(tmp_path, indices):
    path = tmp_path / "claims.json"
    path.write_text(json.dumps([{"paper_id": PAPER, "claim_index": i, "row_ids": [f"R{i}"]} for i in indices]), encoding="utf-8")
    return path


def _three(tmp_path, per_run):
    """per_run = three lists of (index, label) or (index, label, missing) or (index, label, missing, served)."""
    folders = []
    for n, claims in enumerate(per_run, start=1):
        full = [(c + (False, AUDITOR)[len(c) - 2:]) if len(c) < 4 else c for c in claims]
        folders.append(_folder(tmp_path, n, full))
    return folders


def _collect(tmp_path, per_run, indices):
    folders = _three(tmp_path, per_run)
    return vote_claims.collect(_claims_file(tmp_path, indices), folders)


# --- votes ---------------------------------------------------------------------------------------------

@pytest.mark.parametrize("labels, expected", [
    ([N, P, S], vote_claims.VOTE_FLAGGED),
    ([P, P, S], vote_claims.VOTE_FLAGGED),
    ([N, N, N], vote_claims.VOTE_FLAGGED),
    ([S, S, P], vote_claims.VOTE_SUPPORTED),
    ([S, S, S], vote_claims.VOTE_SUPPORTED),
    ([S, N, S], vote_claims.VOTE_SUPPORTED),
])
def test_two_of_three_votes(labels, expected):
    assert vote_claims.vote(labels) == expected


def test_split_case_when_neither_side_has_two_votes():
    # With three valid labels one side always has 2 of 3, so a split needs fewer than three labels.
    assert vote_claims.vote([S, N]) == vote_claims.VOTE_SPLIT
    assert vote_claims.vote([]) == vote_claims.VOTE_SPLIT


def test_per_claim_labels_votes_and_totals(tmp_path):
    payload, invalid = _collect(tmp_path, [
        [(0, N), (1, S), (2, S)],
        [(0, P), (1, S), (2, N)],
        [(0, S), (1, S), (2, N)],
    ], [0, 1, 2])
    assert invalid == []
    by_index = {c["claim_index"]: c for c in payload["claims"]}
    assert by_index[0]["raw"] == [N, P, S] and by_index[0]["raw_vote"] == vote_claims.VOTE_FLAGGED
    assert by_index[1]["raw"] == [S, S, S] and by_index[1]["raw_vote"] == vote_claims.VOTE_SUPPORTED
    assert by_index[2]["raw"] == [S, N, N] and by_index[2]["raw_vote"] == vote_claims.VOTE_FLAGGED
    assert by_index[0]["row_ids"] == ["R0"]
    assert by_index[0]["served"] == [AUDITOR] * 3
    totals = payload["totals"]
    assert totals["claims"] == 3 and totals["raw"] == {"caught": 2, "supported": 1, "split": 0}
    assert totals["audits"] == 9 and totals["fallback_served_audits"] == 0


# --- RAW and EFFECTIVE ---------------------------------------------------------------------------------

def test_missing_claim_is_effective_not_supported_and_raw_keeps_its_label(tmp_path):
    payload, invalid = _collect(tmp_path, [[(0, S, True)], [(0, S, False)], [(0, S, False)]], [0])
    assert invalid == []
    claim = payload["claims"][0]
    assert claim["raw"] == [S, S, S]
    assert claim["effective"] == [N, S, S]


def test_a_claim_whose_raw_and_effective_votes_differ_is_reported_in_both_columns(tmp_path):
    # RAW: supported in all three runs. EFFECTIVE: grounding rejected it in runs 1 and 2 -> not_supported twice.
    payload, invalid = _collect(tmp_path, [[(0, S, True)], [(0, S, True)], [(0, S, False)]], [0])
    assert invalid == []
    claim = payload["claims"][0]
    assert claim["raw_vote"] == vote_claims.VOTE_SUPPORTED
    assert claim["effective_vote"] == vote_claims.VOTE_FLAGGED
    totals = payload["totals"]
    assert totals["raw"] == {"caught": 0, "supported": 1, "split": 0}
    assert totals["effective"] == {"caught": 1, "supported": 0, "split": 0}

    text = vote_claims.format_report(payload)
    assert "RAW       S S S" in text and "-> supported >= 2/3" in text
    assert "EFFECTIVE N N S" in text and "-> flagged >= 2/3" in text
    assert text.index("RAW       S S S") < text.index("EFFECTIVE N N S")      # RAW is printed first
    assert "RAW       caught 0 of 1" in text
    assert "EFFECTIVE caught 1 of 1" in text and "report-only" in text


def test_raw_flagged_and_effective_flagged_are_counted_in_their_own_totals(tmp_path):
    payload, _ = _collect(tmp_path, [[(0, P, False)], [(0, S, False)], [(0, N, False)]], [0])
    assert payload["totals"]["raw"]["caught"] == 1 and payload["totals"]["effective"]["caught"] == 1


# --- fallback ------------------------------------------------------------------------------------------

def test_fallback_served_audits_are_counted(tmp_path):
    payload, invalid = _collect(tmp_path, [
        [(0, N, False, FALLBACK), (1, S, False, AUDITOR)],
        [(0, N, False, AUDITOR), (1, S, False, FALLBACK)],
        [(0, N, False, FALLBACK), (1, S, False, AUDITOR)],
    ], [0, 1])
    assert invalid == []
    assert payload["totals"]["fallback_served_audits"] == 3
    assert payload["totals"]["audits"] == 6
    assert [c["fallback"] for c in payload["claims"]] == [[True, False, True], [False, True, False]]
    assert "fallback-served audits: 3 of 6" in vote_claims.format_report(payload)


# --- INVALID -------------------------------------------------------------------------------------------

def test_exactly_three_fixture_dirs_are_required(tmp_path):
    folders = _three(tmp_path, [[(0, S)], [(0, S)], [(0, S)]])
    payload, invalid = vote_claims.collect(_claims_file(tmp_path, [0]), folders[:2])
    assert payload == {} and "exactly 3" in invalid[0]
    assert vote_claims.main(["--claims", str(_claims_file(tmp_path, [0])), "--fixture-dir", str(folders[0])]) == 1


def test_a_claim_missing_from_a_folder_is_invalid(tmp_path):
    folders = [
        _folder(tmp_path, 1, [(0, S, False, AUDITOR), (1, S, False, AUDITOR)]),
        _folder(tmp_path, 2, [(0, S, False, AUDITOR)], scope=[0, 1]),
        _folder(tmp_path, 3, [(0, S, False, AUDITOR), (1, S, False, AUDITOR)]),
    ]
    _, invalid = vote_claims.collect(_claims_file(tmp_path, [0, 1]), folders)
    assert any("lacks claims [1]" in reason for reason in invalid)


def test_run_configs_that_differ_are_invalid(tmp_path):
    other = {"backend": "vertex", "auditor_model": AUDITOR, "thinking_level": "high", "other_models": {"a": "b"}}
    folders = [
        _folder(tmp_path, 1, [(0, S, False, AUDITOR)]),
        _folder(tmp_path, 2, [(0, S, False, AUDITOR)], config=other),
        _folder(tmp_path, 3, [(0, S, False, AUDITOR)]),
    ]
    _, invalid = vote_claims.collect(_claims_file(tmp_path, [0]), folders)
    assert any("thinking_level" in reason for reason in invalid)


def test_claims_scope_that_differs_from_the_claims_file_is_invalid(tmp_path):
    folders = [
        _folder(tmp_path, 1, [(0, S, False, AUDITOR)], scope=[0, 5]),
        _folder(tmp_path, 2, [(0, S, False, AUDITOR)]),
        _folder(tmp_path, 3, [(0, S, False, AUDITOR)]),
    ]
    _, invalid = vote_claims.collect(_claims_file(tmp_path, [0]), folders)
    assert any("claims_scope" in reason for reason in invalid)


def test_prompt_hashes_that_differ_between_folders_are_invalid(tmp_path):
    folders = [
        _folder(tmp_path, 1, [(0, S, False, AUDITOR)]),
        _folder(tmp_path, 2, [(0, S, False, AUDITOR)], prompt_hash="h2"),
        _folder(tmp_path, 3, [(0, S, False, AUDITOR)]),
    ]
    _, invalid = vote_claims.collect(_claims_file(tmp_path, [0]), folders)
    assert any("prompt_hash" in reason for reason in invalid)


def test_a_folder_with_a_failed_status_or_an_unknown_label_is_invalid(tmp_path):
    folders = [
        _folder(tmp_path, 1, [(0, "maybe", False, AUDITOR)]),
        _folder(tmp_path, 2, [(0, S, False, AUDITOR)], status="VOID_CAP_HIT"),
        _folder(tmp_path, 3, [(0, S, False, AUDITOR)]),
    ]
    _, invalid = vote_claims.collect(_claims_file(tmp_path, [0]), folders)
    assert any("not a replay label" in reason for reason in invalid)
    assert any("VOID_CAP_HIT" in reason for reason in invalid)


def test_a_missing_folder_is_invalid_and_main_exits_1(tmp_path, capsys):
    folders = _three(tmp_path, [[(0, S)], [(0, S)], [(0, S)]])
    folders[2] = tmp_path / "no_such_folder"
    args = ["--claims", str(_claims_file(tmp_path, [0]))]
    for f in folders:
        args += ["--fixture-dir", str(f)]
    assert vote_claims.main(args) == 1
    assert "INVALID" in capsys.readouterr().out


# --- main / json ---------------------------------------------------------------------------------------

def test_main_prints_the_report_and_json_out_matches_the_totals(tmp_path, capsys):
    folders = _three(tmp_path, [[(0, S, True), (1, N)], [(0, S, True), (1, N)], [(0, S), (1, S)]])
    out = tmp_path / "res" / "votes.json"
    args = ["--claims", str(_claims_file(tmp_path, [0, 1])), "--json-out", str(out)]
    for f in folders:
        args += ["--fixture-dir", str(f)]

    assert vote_claims.main(args) == 0

    printed = capsys.readouterr().out
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert "RAW       caught 1 of 2" in printed and "EFFECTIVE caught 2 of 2" in printed
    assert saved["totals"]["raw"]["caught"] == 1 and saved["totals"]["effective"]["caught"] == 2
    assert [c["claim_index"] for c in saved["claims"]] == [0, 1]
