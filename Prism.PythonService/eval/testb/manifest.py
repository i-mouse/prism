"""CLI: sha256 manifest of a test-B output directory (eval.testb.one_call's --out),
for Phase-3 reporting without re-opening any paper or claim text.

Usage (from Prism.PythonService):
  uv run python -m eval.testb.manifest --in DIR --out docs/evals/testb_2026-11-19/manifest.json
"""
import argparse
import json
from pathlib import Path

from eval.blind_review import sha256_file


def build_manifest(in_dir: Path) -> dict:
    """{"files": {relative/path: sha256}, "summaries": {relative/path/to/_summary.json: its contents}}.
    No text is read from any file other than the _summary.json values themselves."""
    files = {}
    summaries = {}
    for path in sorted(in_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(in_dir).as_posix()
        files[rel] = sha256_file(path)
        if path.name == "_summary.json":
            summaries[rel] = json.loads(path.read_text(encoding="utf-8"))
    return {"files": files, "summaries": summaries}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--in", dest="in_dir", type=Path, required=True)
    parser.add_argument("--out", dest="out_path", type=Path, required=True)
    args = parser.parse_args(argv)

    manifest = build_manifest(args.in_dir)
    args.out_path.parent.mkdir(parents=True, exist_ok=True)
    args.out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {args.out_path.resolve()} ({len(manifest['files'])} files, {len(manifest['summaries'])} summaries)")


if __name__ == "__main__":
    main()
