"""Unit tests for eval/build_golden_text_cache.py. Offline: the Postgres lookup, the PDF lookup and the
product's text extraction are injected fakes; nothing real is read and nothing outside tmp_path is written."""
import asyncio
import json

import pytest

from eval import build_golden_text_cache as mod

PAPER_1 = "arxiv-1.0v1"
PAPER_2 = "arxiv-2.0v1"
SHA_1 = "a" * 64
SHA_2 = "b" * 64
TEXTS = {"cot.pdf": "Chain of thought text.\n\nSecond paragraph.", "react.pdf": "ReAct text.\n\nMore."}


def _matrix(path, paper_ids):
    path.write_text(json.dumps({
        "metadata": {"pass_threshold": {"refusal_rate": 0.7, "positive_hit_floor": 10}},
        "papers": [
            {"paper_id": pid, "filename": f"{pid}.pdf", "title": pid,
             "expected_matrix": [{"id": f"{pid}-1", "expected_label": "supported", "grounding_negative": False}]}
            for pid in paper_ids
        ],
    }), encoding="utf-8")


class Fakes:
    """Records the calls the builder makes and serves canned runs, PDFs and texts."""

    def __init__(self, texts=None, fail_pdf_for=None):
        self.runs = {"run-1": {"content_hash": SHA_1, "file_name": "cot.pdf"},
                     "run-2": {"content_hash": SHA_2, "file_name": "react.pdf"}}
        self.texts = TEXTS if texts is None else texts
        self.fail_pdf_for = fail_pdf_for
        self.load_run_calls, self.resolve_calls, self.extract_calls = [], [], []

    async def load_run(self, run_id, refresh):
        self.load_run_calls.append((run_id, refresh))
        return self.runs[run_id]

    def resolve_pdf(self, file_name, sha256):
        self.resolve_calls.append((file_name, sha256))
        if file_name == self.fail_pdf_for:
            raise SystemExit(f"no local PDF for {file_name} matches sha256 {sha256}")
        return mod.Path(f"/pdfs/{file_name}")

    def extract_text(self, pdf_path):
        self.extract_calls.append(pdf_path)
        return self.texts[mod.Path(pdf_path).name], {"pages": 1}


@pytest.fixture
def golden(tmp_path):
    fixtures = tmp_path / "fixtures"
    fixtures.mkdir()
    for pid, run in ((PAPER_1, "run-1"), (PAPER_2, "run-2")):
        (fixtures / f"{pid}.json").write_text(json.dumps({"header": {"extraction_run_id": run}, "claims": [], "matches": []}),
                                              encoding="utf-8")
    (fixtures / "arxiv-8888.00009v1.json").write_text("{not json", encoding="utf-8")   # another set's file
    matrix = tmp_path / "matrix_eval.json"
    _matrix(matrix, [PAPER_1, PAPER_2])
    return matrix, fixtures, tmp_path / "golden_text"


def _build(golden, fakes, **kwargs):
    matrix, fixtures, text_dir = golden
    messages = []
    written = asyncio.run(mod.build(
        matrix, fixtures, text_dir, load_run=fakes.load_run, resolve_pdf=fakes.resolve_pdf,
        extract_text=fakes.extract_text, log=messages.append, **kwargs,
    ))
    return written, messages


def test_writes_one_utf8_file_per_matrix_paper_named_like_the_dev_text_cache(golden):
    fakes = Fakes(texts={"cot.pdf": "Naïve – text.\n\nTwo.", "react.pdf": "R"})
    written, _ = _build(golden, fakes)
    _, _, text_dir = golden
    assert sorted(p.name for p in written) == ["1.0v1.txt", "2.0v1.txt"]
    assert (text_dir / "1.0v1.txt").read_bytes() == "Naïve – text.\n\nTwo.".encode("utf-8")
    assert (text_dir / "2.0v1.txt").read_bytes() == b"R"


def test_the_pdf_is_looked_up_by_the_runs_hash_and_file_name_and_the_cache_is_not_refreshed(golden):
    fakes = Fakes()
    _build(golden, fakes)
    assert fakes.load_run_calls == [("run-1", False), ("run-2", False)]
    assert fakes.resolve_calls == [("cot.pdf", SHA_1), ("react.pdf", SHA_2)]
    assert fakes.extract_calls == [str(mod.Path("/pdfs/cot.pdf")), str(mod.Path("/pdfs/react.pdf"))]


def test_a_sha256_mismatch_refuses_and_writes_nothing_even_for_the_papers_before_it(golden):
    fakes = Fakes(fail_pdf_for="react.pdf")   # the second paper fails after the first one succeeded
    with pytest.raises(mod.GoldenTextError, match="react.pdf matches sha256"):
        _build(golden, fakes)
    _, _, text_dir = golden
    assert not text_dir.exists()


def test_an_existing_text_file_is_refused_before_any_work(golden):
    _, _, text_dir = golden
    text_dir.mkdir()
    (text_dir / "2.0v1.txt").write_text("KEEP", encoding="utf-8")
    fakes = Fakes()
    with pytest.raises(mod.GoldenTextError, match="already exists"):
        _build(golden, fakes)
    assert fakes.load_run_calls == [] and fakes.extract_calls == []
    assert (text_dir / "2.0v1.txt").read_text(encoding="utf-8") == "KEEP"
    assert sorted(p.name for p in text_dir.iterdir()) == ["2.0v1.txt"]


def test_only_matrix_papers_are_processed(golden):
    fakes = Fakes()
    written, _ = _build(golden, fakes)   # the foreign fixture is invalid JSON: opening it would raise
    assert len(written) == 2 and len(fakes.load_run_calls) == 2


def test_a_fixture_without_an_extraction_run_id_is_refused(golden):
    _, fixtures, _ = golden
    (fixtures / f"{PAPER_2}.json").write_text(json.dumps({"header": {}, "claims": []}), encoding="utf-8")
    fakes = Fakes()
    with pytest.raises(mod.GoldenTextError, match="no extraction_run_id"):
        _build(golden, fakes)
    assert fakes.load_run_calls == []


def test_a_missing_fixture_file_is_refused(golden):
    _, fixtures, _ = golden
    (fixtures / f"{PAPER_1}.json").unlink()
    with pytest.raises(mod.GoldenTextError, match="no fixture file"):
        _build(golden, Fakes())


@pytest.mark.parametrize("bad_text, message", [("", "is empty"), ("   \n", "is empty"), ("a\r\nb", "carriage returns")])
def test_empty_text_and_text_with_carriage_returns_are_refused_and_nothing_is_written(golden, bad_text, message):
    fakes = Fakes(texts={"cot.pdf": TEXTS["cot.pdf"], "react.pdf": bad_text})
    with pytest.raises(mod.GoldenTextError, match=message):
        _build(golden, fakes)
    _, _, text_dir = golden
    assert not text_dir.exists()


def test_the_log_names_the_pdf_the_sha_prefix_and_the_size(golden):
    _, messages = _build(golden, Fakes())
    first = next(m for m in messages if "1.0v1" in m and "pdf=" in m)
    assert "pdf=cot.pdf" in first and f"sha256={SHA_1[:12]}" in first and f"{len(TEXTS['cot.pdf'])} chars" in first


def test_the_default_paths_are_the_golden_constants_of_replay_audit():
    from eval import replay_audit
    parser = mod._build_parser()
    args = parser.parse_args([])
    assert (args.matrix_path, args.fixture_dir, args.text_dir) == (
        replay_audit.GOLDEN_MATRIX_PATH, replay_audit.GOLDEN_FIXTURE_DIR, replay_audit.GOLDEN_TEXT_CACHE_DIR,
    )
    assert "scratch" in args.text_dir.parts   # under the folder the repo-root .gitignore excludes
