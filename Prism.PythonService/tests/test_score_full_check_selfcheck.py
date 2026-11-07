"""Opt-in self-check of eval/score_full_check.py on the REAL screen-arm folders: for each arm, the targets fixed
and the catches lost that score_full_check computes from the arm's three folders equal what eval.score_screen
reports for the same folders (its 18-row votes). Skipped unless FULL_CHECK_SELFCHECK_DIRS is set.

FULL_CHECK_SELFCHECK_DIRS holds the 9 folders (3 arms x 3 repeats), separated by os.pathsep (";" on Windows),
in this order - the folders are under docs/evals/fixtures/dev/:
  exp1_medium_gemini-3.6-flash-vertex_1, _2, _3
  exp1_medium_gemini-3.8-flash-vertex_1, _2, _3
  exp1_high_gemini-3.8-flash-vertex_1, _2, _3

PowerShell, from Prism.PythonService:
  $d = 'H:\\Work projects\\Prism\\docs\\evals\\fixtures\\dev'
  $env:FULL_CHECK_SELFCHECK_DIRS = ((1..3 | % { "$d\\exp1_medium_gemini-3.6-flash-vertex_$_" }) + (1..3 | % { "$d\\exp1_medium_gemini-3.8-flash-vertex_$_" }) + (1..3 | % { "$d\\exp1_high_gemini-3.8-flash-vertex_$_" })) -join ';'
  uv run pytest -q tests/test_score_full_check_selfcheck.py

It reads the repo's dev_eval / match map / run1 fixtures and the 9 folders, writes nothing and makes no LLM call.
"""
import os
from pathlib import Path

import pytest

from eval import score_full_check as sfc, score_screen
from eval.score_replay import DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR, resolve_adjudicated_rows

ENV_VAR = "FULL_CHECK_SELFCHECK_DIRS"
ARMS = ("exp1_medium 3.6-flash", "exp1_medium 3.8-flash", "exp1_high 3.8-flash")

pytestmark = pytest.mark.skipif(not os.environ.get(ENV_VAR), reason=f"{ENV_VAR} is not set")


def _arms() -> list[list[Path]]:
    dirs = [Path(p) for p in os.environ[ENV_VAR].split(os.pathsep) if p.strip()]
    assert len(dirs) == 9, f"{ENV_VAR} must hold 9 folders (3 arms x 3 repeats), found {len(dirs)}"
    return [dirs[0:3], dirs[3:6], dirs[6:9]]


@pytest.mark.parametrize("arm_index", range(3), ids=ARMS)
def test_votes_equal_score_screens_on_the_real_folders(arm_index):
    dirs = _arms()[arm_index]
    rows = resolve_adjudicated_rows(DEFAULT_DEV_EVAL_PATH, DEFAULT_MATCH_MAP_PATH, DEFAULT_RUN1_FIXTURE_DIR, row_type="R")
    invalid, labels, claims, configs = score_screen.collect(rows, dirs)
    assert invalid == [], invalid

    expected = score_screen.build_results(dirs, labels, claims, configs)["totals"]
    mine = sfc.r_votes(labels)
    assert mine["targets_fixed"] == expected["auditor_targets_caught_ids"]
    assert mine["catches_lost"] == expected["real_hits_lost_ids"]
    # and the row groups are the shipped ones: 8 targets (10 misses minus 2 parked), 7 catches
    targets = [r for r in score_screen.MISS_ROWS if r not in score_screen.PARKED_ROWS]
    assert len(targets) == 8 and len(score_screen.REAL_HITS) == 7
    assert set(mine["targets_fixed"]) <= set(targets)
