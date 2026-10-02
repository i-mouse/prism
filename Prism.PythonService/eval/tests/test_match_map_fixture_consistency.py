"""match_map.json is the authoritative human pairing of golden rows to
extracted claims; the frozen matches in docs/evals/fixtures/*.json are what
fixture-mode scoring actually reads. Nothing at runtime forces the two to
agree, so this test does - against the real committed files, offline (no
LLM calls, no DB).
"""
from pathlib import Path

import pytest

from eval.data_source import read_from_fixture, read_matches_from_fixture
from eval.match_map import fingerprint_claim_text, load_match_map
from eval.matrix_loader import load_matrix

EVALS_DIR = Path(__file__).parent.parent.parent.parent / "docs" / "evals"
MATRIX = load_matrix(EVALS_DIR / "matrix_eval.json")
GOLDEN_IDS = {row.id for paper in MATRIX.papers for row in paper.expected_rows}


def _disagreements(paper) -> list[str]:
    match_map = load_match_map(EVALS_DIR / "match_map.json", GOLDEN_IDS)
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


@pytest.mark.parametrize("paper", MATRIX.papers, ids=lambda p: p.paper_id)
def test_fixture_frozen_matches_equal_match_map(paper):
    errors = _disagreements(paper)
    assert not errors, "match_map.json and fixture frozen matches disagree:\n  " + "\n  ".join(errors)
