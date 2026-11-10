"""Byte-identical regression for eval/replay_audit.py with the scope check off.

Runs a whole replay (cache off and cache on) on invented papers and claims with
every model, cache and grounding call faked, and compares everything the run
writes - each file under the output directory byte for byte, plus stdout - to a
snapshot saved from the code as it was before the scope check was added.

Volatile fields and how they are pinned (all in tests/replay_fakes.py unless
noted):
  - header.replay.generated_at (time.strftime) and _summary.json
    records[].latency_s (time.monotonic): replay_audit.time is a stub with a
    fixed strftime and a deterministic counter.
  - cache lifetime_s / storage_usd: context_cache.time is the same stub.
  - cache names and token counts: constants from the fake SDK.
  - temp paths in stdout ("wrote <tmp>/..."): replaced by normalise_snapshot_text
    below, the one place any normalising happens.
  - the engine's timestamped log files are written under tmp_path/logs and are
    not part of the snapshot.

The scope-check flag is deliberately absent from the args namespace, exactly as
before the flag existed.

Snapshots are in tests/snapshots/. If one is missing, the test writes it and
fails ("snapshot written, re-run"); that only ever happens when blessing.
"""
import argparse
import asyncio
import json
from pathlib import Path

import pytest

from eval import replay_audit

import replay_fakes

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"


def normalise_snapshot_text(text: str, tmp_path: Path) -> str:
    """The only normalisation: the run's temp directory becomes <TMP>, with
    forward slashes, so stdout does not depend on the machine or the OS."""
    return text.replace(str(tmp_path), "<TMP>").replace("\\", "/")


def _args(claims_path: Path, cache: bool) -> argparse.Namespace:
    return argparse.Namespace(
        level="medium", claims=str(claims_path), papers=None, repeat=1, estimate=False,
        dry_run=False, max_inr=None, cache=cache,
    )


def _run(tmp_path, monkeypatch, capsys, cache: bool) -> dict:
    sdk = replay_fakes.FakeSdk()
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, sdk)
    rc = asyncio.run(replay_audit._main(_args(claims_path, cache)))
    assert rc == 0
    assert set(sdk.kinds()) == {"audit", "structure"}  # no scope call can exist with the flag off
    out_root = tmp_path / "out"
    files = {
        path.relative_to(out_root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(out_root.rglob("*")) if path.is_file()
    }
    return {"files": files, "stdout": normalise_snapshot_text(capsys.readouterr().out, tmp_path)}


@pytest.mark.parametrize("cache", [False, True], ids=["cache_off", "cache_on"])
def test_flag_off_replay_output_is_byte_identical(tmp_path, monkeypatch, capsys, cache):
    actual = _run(tmp_path, monkeypatch, capsys, cache)
    snapshot_path = SNAPSHOT_DIR / f"replay_flag_off_cache_{'on' if cache else 'off'}.json"
    rendered = json.dumps(actual, indent=2, sort_keys=True) + "\n"
    if not snapshot_path.exists():
        SNAPSHOT_DIR.mkdir(exist_ok=True)
        snapshot_path.write_text(rendered, encoding="utf-8", newline="\n")
        pytest.fail(f"snapshot written to {snapshot_path}; re-run to confirm it passes")
    assert rendered == snapshot_path.read_text(encoding="utf-8")
