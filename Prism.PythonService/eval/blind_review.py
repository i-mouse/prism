"""Generic helpers for building blind, human-adjudicated review packs and
scoring them once locked. No Experiment-3-specific logic lives here -
eval/exp3_b4.py owns every Exp-3 decision (what goes in a pool, what a
match means, which gate reads which value).

Pipeline shape this module supports: build a pack with opaque ids -> a
human fills in an answer file (CSV) by hand, blind to any identifying
field -> lock the filled answer file(s) (hash-pin them) -> score only
against a verified lock, so an answer file can't be edited after scoring
starts without detection.
"""
import hashlib
import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, TypeVar

from pydantic import BaseModel, model_validator

from extraction.grounding import normalize_for_match

T = TypeVar("T")


def assign_opaque_ids(items: list[T], prefix: str, seed: int, width: int = 4) -> list[tuple[str, T]]:
    """Shuffles a copy of items with random.Random(seed), then assigns
    sequential ids prefix+0001, prefix+0002, ... in the shuffled order.

    Stable across rebuilds only if the input list's own order is itself
    stable (e.g. always built by iterating files in sorted order) - this
    function does not sort; callers own that.
    """
    shuffled = list(items)
    random.Random(seed).shuffle(shuffled)
    return [(f"{prefix}{i + 1:0{width}d}", item) for i, item in enumerate(shuffled)]


def dedup_by_normalized_text(items: list[T], text_of) -> list[T]:
    """Keeps the first occurrence of each item whose normalize_for_match(text_of(item))
    has not been seen yet. Preserves input order."""
    seen: set[str] = set()
    out: list[T] = []
    for item in items:
        key = normalize_for_match(text_of(item))
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def seeded_sample(items: list[T], k: int, seed: int) -> list[T]:
    """random.Random(seed).sample(items, k), or all items (order-preserved,
    not shuffled) if there are fewer than k."""
    if len(items) <= k:
        return list(items)
    return random.Random(seed).sample(items, k)


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_lock(answer_paths: dict[str, Path], lock_path: Path) -> None:
    """Writes lock_path recording the sha256 of each named answer file plus
    a UTC timestamp. Every path in answer_paths must exist."""
    missing = [str(p) for p in answer_paths.values() if not p.exists()]
    if missing:
        raise FileNotFoundError(f"cannot lock: missing answer file(s): {missing}")
    lock = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": {name: {"path": str(path), "sha256": sha256_file(path)} for name, path in answer_paths.items()},
    }
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2), encoding="utf-8")


def verify_lock(lock_path: Path, answer_paths: dict[str, Path]) -> None:
    """Raises ValueError if lock_path is missing, if any named file's
    current sha256 does not match what was locked, or if a named file is
    missing from either the lock or the current answer_paths."""
    if not lock_path.exists():
        raise ValueError(f"no lock file at {lock_path} - run `lock` before `score`")
    lock = json.loads(lock_path.read_text(encoding="utf-8"))
    locked_files = lock.get("files", {})

    problems = []
    for name, path in answer_paths.items():
        if name not in locked_files:
            problems.append(f"{name}: not present in lock")
            continue
        if not path.exists():
            problems.append(f"{name}: file missing at {path}")
            continue
        current = sha256_file(path)
        if current != locked_files[name]["sha256"]:
            problems.append(f"{name}: sha256 mismatch (file changed since lock)")
    for name in locked_files:
        if name not in answer_paths:
            problems.append(f"{name}: present in lock but not checked by this scorer")

    if problems:
        raise ValueError(f"lock verification failed: {'; '.join(problems)}")


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[Optional[float], Optional[float]]:
    """95% (default z=1.96) Wilson score interval for a binomial proportion.
    Returns (None, None) when n == 0 (undefined, never divide-by-zero)."""
    if n == 0:
        return None, None
    p = successes / n
    denom = 1 + z**2 / n
    center = p + z**2 / (2 * n)
    margin = z * ((p * (1 - p) / n + z**2 / (4 * n**2)) ** 0.5)
    low = (center - margin) / denom
    high = (center + margin) / denom
    return max(0.0, low), min(1.0, high)


class C1Answer(BaseModel):
    """One hand-filled row of c1_adjudication.csv."""

    row_id: str
    paper_id: str
    match_ids: list[str] = []
    note: str = ""

    @model_validator(mode="before")
    @classmethod
    def _parse_match_ids(cls, data):
        if isinstance(data, dict) and isinstance(data.get("match_ids"), str):
            raw = data["match_ids"].strip()
            data = dict(data)
            if not raw or raw.lower() == "none":
                data["match_ids"] = []
            else:
                data["match_ids"] = [part.strip() for part in raw.split(";") if part.strip()]
        return data


class C8Answer(BaseModel):
    """One hand-filled row of c8_sheet.csv."""

    id: str
    label: Literal["claim", "not_claim", "unsure"]
    reason: Optional[Literal["method_setup", "background_related_work", "number_no_assertion", "other"]] = None
    duplicate: Optional[Literal["yes", "no"]] = None
    note: str = ""

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for field in ("reason", "duplicate"):
                if isinstance(data.get(field), str) and not data[field].strip():
                    data[field] = None
        return data

    @model_validator(mode="after")
    def _check_conditional_fields(self):
        if self.label != "claim" and self.reason is None:
            raise ValueError(f"{self.id}: reason is required when label is '{self.label}'")
        if self.label == "claim" and self.duplicate is None:
            raise ValueError(f"{self.id}: duplicate is required when label is 'claim'")
        return self


class K6Answer(BaseModel):
    """One hand-filled row of the clean-extraction attempt's K6 sheet (30
    kept cleaned pass-2 claims per run) - same label/reason/duplicate/note
    shape as C8Answer, reused as its own model (rather than aliased to
    C8Answer) since the two sheets are scored by different callers and may
    diverge later."""

    id: str
    label: Literal["claim", "not_claim", "unsure"]
    reason: Optional[Literal["method_setup", "background_related_work", "number_no_assertion", "other"]] = None
    duplicate: Optional[Literal["yes", "no"]] = None
    note: str = ""

    @model_validator(mode="before")
    @classmethod
    def _blank_strings_to_none(cls, data):
        if isinstance(data, dict):
            data = dict(data)
            for field in ("reason", "duplicate"):
                if isinstance(data.get(field), str) and not data[field].strip():
                    data[field] = None
        return data

    @model_validator(mode="after")
    def _check_conditional_fields(self):
        if self.label != "claim" and self.reason is None:
            raise ValueError(f"{self.id}: reason is required when label is '{self.label}'")
        if self.label == "claim" and self.duplicate is None:
            raise ValueError(f"{self.id}: duplicate is required when label is 'claim'")
        return self


class K7Answer(BaseModel):
    """One hand-filled row of the clean-extraction attempt's K7 sheet (30
    "same" drops per run, all if fewer) - a human's own independent
    judgment of the relation between the dropped candidate and the
    neighbour the filter matched it to as "same", checking the filter's
    own dedup safety."""

    id: str
    verdict: Literal["same", "broader", "narrower", "different"]
    note: str = ""


def provenance(input_paths: list[Path]) -> dict[str, str]:
    """sha256 of every input file a writer used, keyed by path string -
    embedded in every output file this module helps write."""
    return {str(p): sha256_file(p) for p in input_paths}
