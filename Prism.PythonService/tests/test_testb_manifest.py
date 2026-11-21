"""eval/testb/manifest.py: sha256 of every file under a run dir, plus any _summary.json
contents found within it. No other file's text is ever read."""
import hashlib
import json

from eval.testb.manifest import build_manifest


def test_manifest_hashes_every_file_and_reads_only_summary_json(tmp_path):
    run_dir = tmp_path / "run_1"
    run_dir.mkdir()
    paper_path = run_dir / "arxiv-FAKE1.json"
    paper_path.write_text(json.dumps({"status": "OK", "raw_text": "secret claim text"}), encoding="utf-8")
    summary_path = run_dir / "_summary.json"
    summary_path.write_text(json.dumps({"run_index": 1, "status": "OK"}), encoding="utf-8")

    manifest = build_manifest(run_dir)

    assert manifest["files"]["arxiv-FAKE1.json"] == hashlib.sha256(paper_path.read_bytes()).hexdigest()
    assert manifest["files"]["_summary.json"] == hashlib.sha256(summary_path.read_bytes()).hexdigest()
    assert manifest["summaries"]["_summary.json"] == {"run_index": 1, "status": "OK"}
    # the paper file's content never appears anywhere in the manifest except as a hash
    assert "secret claim text" not in json.dumps(manifest)
