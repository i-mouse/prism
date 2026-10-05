"""Offline tests for eval/check_prompt_leak.py. No LLM calls, no DB, no PDFs.

Uses the committed hash index (eval/leakcheck/index.json) and the committed
eval rows. Held-out text is only ever written to a tmp file and asserted
ABSENT from captured output - it is never printed by the tests themselves.
"""
import json
import re

import pytest

from eval import check_prompt_leak as cpl
from extraction import prompt_version


def _rows(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return [r for p in data["papers"] for r in p["expected_matrix"]]


def _plant(tmp_path, text, name="prompts/planted.md"):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"# Task\n\nSome neutral instructions.\n{text}\nMore neutral text.\n", encoding="utf-8")
    return path


@pytest.fixture(scope="module")
def sources():
    return cpl.paper_sources(cpl.load_index()) + cpl.row_sources()


def test_runtime_tree_is_clean(sources):
    failures, _ = cpl.run_check(sources=sources)
    assert failures == [], "\n".join(h.render() for h in failures)


def test_every_hashed_prompt_file_is_in_scope():
    in_scope = set(cpl.runtime_files())
    for f in prompt_version.PROMPT_FILENAMES:
        assert prompt_version.PROMPTS_DIR / f in in_scope
    for f in prompt_version.EXTRA_HASHED_FILES:
        assert f.resolve() in in_scope


def test_planted_golden_sentence_fails(tmp_path, sources):
    row = next(r for r in _rows(cpl.GOLDEN_ROWS_PATH) if r["id"] == "REACT-M13")
    path = _plant(tmp_path, row["claim_text_verbatim"])
    failures, _ = cpl.run_check(files=[path], root=tmp_path, sources=sources, allowlist=[])
    ngram_hits = [h for h in failures if h.kind == "ngram8"]
    assert {h.source for h in ngram_hits} >= {"paper:react", "row:REACT-M13"}
    assert all(h.file == "prompts/planted.md" and h.line == 4 for h in ngram_hits)


def test_planted_golden_name_fails(tmp_path, sources):
    path = _plant(tmp_path, "For example, a ReAct-style agent.")
    failures, _ = cpl.run_check(files=[path], root=tmp_path, sources=sources, allowlist=[])
    assert any(h.kind == "name" and h.detail == "react" and h.line == 4 for h in failures)


def test_planted_paper_table_number_fails(tmp_path, sources):
    path = _plant(tmp_path, "The reference row reports 67.5 on the task.")
    failures, _ = cpl.run_check(files=[path], root=tmp_path, sources=sources, allowlist=[])
    assert any(h.kind == "number" and h.source == "paper:react" and h.detail == "67.5" for h in failures)


def test_planted_heldout_row_fails_and_is_never_echoed(tmp_path, capsys):
    row_text = _rows(cpl.HELDOUT_ROWS_PATH)[0]["claim_text_verbatim"]
    path = _plant(tmp_path, row_text)
    allow = tmp_path / "allow.json"
    allow.write_text('{"entries": []}', encoding="utf-8")

    code = cpl.main([str(path), "--root", str(tmp_path), "--allowlist", str(allow)])
    out = capsys.readouterr()
    printed = out.out + out.err

    assert code == 1
    assert "held-out source" in printed
    # nothing of the planted held-out text appears: not verbatim, not any
    # 3-word window of it (case/punctuation-insensitive)
    assert row_text not in printed
    row_toks = cpl.normalize_tokens(row_text)
    printed_norm = " ".join(cpl.normalize_tokens(printed))
    for i in range(len(row_toks) - 2):
        window = " ".join(row_toks[i:i + 3])
        if re.fullmatch(r"[a-z]+ [a-z]+ [a-z]+", window) and len(window) > 12:
            assert window not in printed_norm, "held-out text leaked into output"


def test_allowlist_is_file_scoped(tmp_path, sources):
    path = _plant(tmp_path, "Built with a React UI.", name="main.py")
    entry = {"kind": "name", "file": "main.py", "match": "react", "reason": "frontend framework"}
    failures, _ = cpl.run_check(files=[path], root=tmp_path, sources=sources, allowlist=[entry])
    assert failures == []
    other = _plant(tmp_path, "Built with a React UI.", name="api.py")
    failures, _ = cpl.run_check(files=[other], root=tmp_path, sources=sources, allowlist=[entry])
    assert any(h.kind == "name" for h in failures)


def test_index_version_mismatch_refuses(tmp_path):
    index = json.loads(cpl.INDEX_PATH.read_text(encoding="utf-8"))
    index["header"]["normalizer_version"] = cpl.NORMALIZER_VERSION + 1
    stale = tmp_path / "index.json"
    stale.write_text(json.dumps(index), encoding="utf-8")
    with pytest.raises(cpl.IndexMismatch):
        cpl.load_index(stale)
    assert cpl.main(["--index", str(stale)]) == 2


def test_index_holds_no_plain_text():
    index = json.loads(cpl.INDEX_PATH.read_text(encoding="utf-8"))
    assert set(index["sources"]) == {"reflexion", "cot", "react", "heldout"}
    for src in index["sources"].values():
        for key in ("ngrams8", "names", "decimals"):
            assert re.fullmatch(r"[A-Za-z0-9+/=]*", src[key])  # base64 hashes only
