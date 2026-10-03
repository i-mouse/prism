"""match_map.json is the authoritative human pairing of golden rows to
extracted claims; the frozen matches in docs/evals/fixtures/*.json are what
fixture-mode scoring actually reads. Nothing at runtime forces the two to
agree, so this test does - against the real committed files, offline (no
LLM calls, no DB).

Runs once per (eval file, match map) pair: the golden matrix_eval.json /
match_map.json, and the sealed held-out heldout_eval.json /
heldout_match_map.json. The held-out case is skipped until its fixture has
been dumped; once it exists, the hand-filled map must agree with it.
"""
from pathlib import Path

import pytest

from eval.data_source import read_from_fixture, read_matches_from_fixture
from eval.match_map import fingerprint_claim_text, load_match_map
from eval.matrix_loader import load_matrix

EVALS_DIR = Path(__file__).parent.parent.parent.parent / "docs" / "evals"
EVAL_SETS = [
    ("matrix_eval.json", "match_map.json"),
    ("heldout_eval.json", "heldout_match_map.json"),
]


def _cases() -> list:
    cases = []
    for eval_file, map_file in EVAL_SETS:
        matrix = load_matrix(EVALS_DIR / eval_file)
        row_ids = {row.id for paper in matrix.papers for row in paper.expected_rows}
        for paper in matrix.papers:
            cases.append(pytest.param(paper, map_file, row_ids, matrix.held_out, id=paper.paper_id))
    return cases


def _disagreements(paper, map_file: str, row_ids: set[str]) -> list[str]:
    match_map = load_match_map(EVALS_DIR / map_file, row_ids)
    fixture_path = EVALS_DIR / "fixtures" / f"{paper.paper_id}.json"
    claims = read_from_fixture(fixture_path)
    frozen = {m.expected_id: m.actual_index for m in read_matches_from_fixture(fixture_path)}

    index_by_fingerprint: dict[str, list[int]] = {}
    for claim in claims:
        index_by_fingerprint.setdefault(fingerprint_claim_text(claim.claim_text_verbatim), []).append(claim.index)

    errors = []
    paper_ids = {row.id for row in paper.expected_rows}
    for stale_id in sorted(set(frozen) - paper_ids):
        errors.append(f"{stale_id}: frozen match in {fixture_path.name} has no golden row in this paper")

    for row in paper.expected_rows:
        entry = match_map.rows[row.id]
        frozen_index = frozen.get(row.id)

        if entry.confirmed_no_match:
            if frozen_index is not None:
                errors.append(f"{row.id}: map says confirmed_no_match, fixture frozen actual_index={frozen_index}")
        elif entry.claim_fingerprint is not None:
            indexes = index_by_fingerprint.get(entry.claim_fingerprint, [])
            if len(indexes) != 1:
                errors.append(
                    f"{row.id}: map fingerprint {entry.claim_fingerprint[:12]} resolves to "
                    f"{len(indexes)} claims in {fixture_path.name}, expected exactly 1"
                )
            elif frozen_index != indexes[0]:
                errors.append(f"{row.id}: map fingerprint -> claim {indexes[0]}, fixture frozen actual_index={frozen_index}")
        else:
            # persisted_claim_id alone can't be resolved offline (ids regenerate
            # on every extraction run), and an unadjudicated row has no pairing
            # for the frozen match to be checked against.
            errors.append(f"{row.id}: map has no claim_fingerprint or confirmed_no_match - cannot verify frozen match")
    return errors


@pytest.mark.parametrize("paper, map_file, row_ids, held_out", _cases())
def test_fixture_frozen_matches_equal_match_map(paper, map_file, row_ids, held_out):
    if held_out and not (EVALS_DIR / "fixtures" / f"{paper.paper_id}.json").exists():
        pytest.skip(f"held-out fixture for {paper.paper_id} not dumped yet")
    errors = _disagreements(paper, map_file, row_ids)
    assert not errors, f"{map_file} and fixture frozen matches disagree:\n  " + "\n  ".join(errors)
