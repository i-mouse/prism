"""Shared, read-only plumbing for the Step 1 scripts: paths, the explicit list of full-check folders, folder guards
and a per-claim reader. Reuses eval.score_full_check / score_screen / score_replay for everything that is a vote or
a label; nothing here decides a verdict.
"""
import json
from dataclasses import dataclass
from pathlib import Path

from eval import score_screen
from eval.score_replay import _load_fixture

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
EVALS_DIR = REPO_ROOT / "docs" / "evals"
DEV_FIXTURE_DIR = EVALS_DIR / "fixtures" / "dev"
GOLDEN_REPLAY_DIR = EVALS_DIR / "golden_replay"
RUN1_FIXTURE_DIR = DEV_FIXTURE_DIR / "run1"
SCRATCH_DIR = REPO_ROOT / "Prism.PythonService" / "scratch"
DEFAULT_OUT_DIR = EVALS_DIR / "step1_2026-11-11"

FULL_CHECK_CLAIMS_PATH = EVALS_DIR / "exp1_full_check_claims.json"      # 84 dev claims
GOLDEN_CLAIMS_PATH = EVALS_DIR / "exp1_golden_claims.json"              # 22 golden claims
STAGE_A_CLAIMS_PATH = EVALS_DIR / "exp1_stage_a_claims.json"            # the 18-claim screen / exp1 set

SCREEN_DIR_NAME = "screen_2026-11-06"
FLAG_OFF_PROMPT_HASH = "cb3272cce551"
REPEATS = 3
EXPECTED_DEV_CLAIMS = 84
EXPECTED_GOLDEN_CLAIMS = 22
EXPECTED_ALL_CLAIMS = 106


@dataclass(frozen=True)
class ArmDef:
    name: str
    folder: str             # the "<level>_<model>" part of the folder name
    auditor_model: str
    thinking_level: str


ARM_B = ArmDef("B", "medium_gemini-3.6-flash", "gemini-3.6-flash", "medium")
ARM_C1 = ArmDef("C1", "medium_gemini-3.8-flash", "gemini-3.8-flash", "medium")
ARM_C2 = ArmDef("C2", "high_gemini-3.8-flash", "gemini-3.8-flash", "high")
ARMS = (ARM_B, ARM_C1, ARM_C2)


def full_check_dirs(arm: ArmDef, set_name: str) -> list[Path]:
    """The arm's 3 repeat folders of the 2026-11-08 full check. set_name is "dev" or "golden"."""
    if set_name == "dev":
        base = DEV_FIXTURE_DIR
    elif set_name == "golden":
        base = GOLDEN_REPLAY_DIR
    else:
        raise ValueError(f"set_name must be 'dev' or 'golden', got {set_name!r}")
    return [base / f"exp1_{arm.folder}-vertex_{n}" for n in range(1, REPEATS + 1)]


def screen_dirs(arm: ArmDef) -> list[Path]:
    """The same-named SCREEN folders (void). Only the noise script lists them, beside the table, never for T."""
    return [DEV_FIXTURE_DIR / SCREEN_DIR_NAME / f"exp1_{arm.folder}-vertex_{n}" for n in range(1, REPEATS + 1)]


def in_screen_folder(path: Path) -> bool:
    return SCREEN_DIR_NAME in Path(path).parts


def ensure_full_check_folders(dirs: list[Path], invalid: list[str]) -> None:
    """Full-check folders must never be the void screen folders."""
    for d in dirs:
        if in_screen_folder(d):
            invalid.append(f"{d}: this is a SCREEN folder (void), not a full-check folder")


# --- claims files --------------------------------------------------------------------------------------

def load_claims_file(path: Path) -> list[tuple[str, int, tuple[str, ...]]]:
    """[(paper_id, claim_index, row_ids)] from a replay_audit --claims file."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [(e["paper_id"], int(e["claim_index"]), tuple(e.get("row_ids") or ())) for e in data]


def check_claims_present(
    folder: Path, entries: list[tuple[str, int, tuple[str, ...]]], invalid: list[str],
) -> None:
    """Every claim of the claims file is in the folder's paper fixtures, and where a fixture carries a
    header.claims_scope it equals the claims file's indices for that paper (a screen folder would not)."""
    by_paper: dict[str, list[int]] = {}
    for paper_id, index, _ in entries:
        by_paper.setdefault(paper_id, []).append(index)
    for paper_id, indices in by_paper.items():
        fixture = _load_fixture(folder, paper_id)
        if fixture is None:
            invalid.append(f"{folder}: no fixture for {paper_id}")
            continue
        present = {c["index"] for c in fixture["claims"]}
        missing = sorted(set(indices) - present)
        if missing:
            invalid.append(f"{folder}: {paper_id} lacks claims {missing} of the claims file")
        scope = fixture["header"].get("claims_scope")
        if scope is not None and sorted(scope) != sorted(indices):
            invalid.append(f"{folder}: {paper_id} claims_scope {sorted(scope)} differs from the claims file {sorted(indices)}")


# --- per-claim reader ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class ClaimRead:
    raw: str                # the claim's final label, grounding ignored
    effective: str          # "not_supported" if the claim is missing (grounding rejection), else the label
    served: str | None      # audit_model_served


class FixtureCache:
    """Loads each (folder, paper) fixture once."""

    def __init__(self) -> None:
        self._fixtures: dict[tuple[str, str], dict | None] = {}

    def claim(self, folder: Path, paper_id: str, index: int) -> dict | None:
        key = (str(folder), paper_id)
        if key not in self._fixtures:
            self._fixtures[key] = _load_fixture(folder, paper_id)
        fixture = self._fixtures[key]
        if fixture is None:
            return None
        return next((c for c in fixture["claims"] if c["index"] == index), None)

    def read(self, folder: Path, paper_id: str, index: int, invalid: list[str]) -> ClaimRead | None:
        claim = self.claim(folder, paper_id, index)
        if claim is None:
            invalid.append(f"{folder}: {paper_id}#{index} has no claim data")
            return None
        raw = claim["label"]
        if raw not in score_screen.VALID_LABELS:
            invalid.append(f"{folder}: {paper_id}#{index} label {raw!r} is not a replay label")
            return None
        effective = "not_supported" if claim["missing"] else raw       # same rule as score_replay.row_details
        return ClaimRead(raw, effective, claim.get("audit_model_served"))


def check_arm_config(arm: ArmDef, configs: list[dict | None], label: str, invalid: list[str]) -> None:
    """A full-check arm's run_configs must be the arm's: vertex, the arm's auditor model and thinking level."""
    for config in configs:
        if config is None:
            continue    # already reported by the loader
        if config.get("backend") != "vertex":
            invalid.append(f"{label}: backend {config.get('backend')!r}, expected 'vertex'")
        if config.get("auditor_model") != arm.auditor_model:
            invalid.append(f"{label}: auditor_model {config.get('auditor_model')!r}, expected {arm.auditor_model!r}")
        if config.get("thinking_level") != arm.thinking_level:
            invalid.append(f"{label}: thinking_level {config.get('thinking_level')!r}, expected {arm.thinking_level!r}")


def prompt_hashes(folder: Path, paper_ids: list[str]) -> set[str]:
    """The prompt_hash values in a folder's paper fixtures."""
    hashes: set[str] = set()
    for paper_id in paper_ids:
        fixture = _load_fixture(folder, paper_id)
        if fixture is not None:
            hashes.add(str(fixture["header"].get("prompt_hash")))
    return hashes


def write_outputs(out_dir: Path, stem: str, text: str, payload: dict) -> list[Path]:
    """Writes <stem>.txt and <stem>.json in out_dir (created if needed). Returns the paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    txt, js = out_dir / f"{stem}.txt", out_dir / f"{stem}.json"
    txt.write_text(text, encoding="utf-8")
    js.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return [txt, js]
