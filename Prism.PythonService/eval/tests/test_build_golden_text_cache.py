"""Unit tests for eval/build_golden_text_cache.py. Offline: the Postgres lookups, the PDF lookup and the product's
text extraction are injected fakes (the run-id lookup runs against a fake pool); nothing real is read and
nothing outside tmp_path is written."""
import asyncio
import json

import pytest

from eval import build_golden_text_cache as mod
from extraction import grounding

PAPER_1 = "arxiv-1.0v1"
PAPER_2 = "arxiv-2.0v1"
SHA_1 = "a" * 64
SHA_2 = "b" * 64
TEXTS = {"cot.pdf": "Chain of thought text.\n\nSecond paragraph.", "react.pdf": "ReAct text.\n\nMore."}
QUOTES = {"cot.pdf": "Chain of thought text.", "react.pdf": "ReAct text."}
ABSENT = "zzz qqq xxx www vvv uuu ttt sss rrr"   # nothing like the texts above: far below the threshold


def _span(quote, status="Pass", stance="supports"):
    return {"source_text": quote, "source_section": "s", "grounding_status": status, "stance": stance}


def _claims(pdf, *extra):
    """One claim: a quote that is in the text (passed Stage 1 originally), one that is not (failed it), + extra."""
    return [{"evidence_spans": [_span(QUOTES[pdf]), _span(ABSENT, "Fail", None), *extra]}]


def _matrix(path, paper_ids):
    path.write_text(json.dumps({
        "metadata": {"pass_threshold": {"refusal_rate": 0.7, "positive_hit_floor": 10}},
        "papers": [
            {"paper_id": pid, "filename": f"{pid}.pdf", "title": pid,
             "expected_matrix": [{"id": f"{pid}-1", "expected_label": "supported", "grounding_negative": False}]}
            for pid in paper_ids
        ],
    }), encoding="utf-8")


def _fixture(folder, paper_id, run_id, claims):
    (folder / f"{paper_id}.json").write_text(
        json.dumps({"header": {"extraction_run_id": run_id}, "claims": claims, "matches": []}), encoding="utf-8")


class Fakes:
    """Records the calls the builder makes and serves canned runs, lookups, PDFs and texts."""

    def __init__(self, texts=None, fail_pdf_for=None, not_found=(), lookups=None, load_error=None):
        self.runs = {"run-1": {"content_hash": SHA_1, "file_name": "cot.pdf"},
                     "run-2": {"content_hash": SHA_2, "file_name": "react.pdf"}}
        self.texts = TEXTS if texts is None else texts
        self.fail_pdf_for = fail_pdf_for
        self.not_found = set(not_found)          # header ids load_run reports as "not found in DB"
        self.lookups = lookups or {}             # header id -> what lookup_run returns
        self.load_error = load_error             # raised by load_run instead (any exception)
        self.load_run_calls, self.lookup_calls, self.resolve_calls, self.extract_calls = [], [], [], []

    async def load_run(self, run_id, refresh):
        self.load_run_calls.append((run_id, refresh))
        if self.load_error is not None:
            raise self.load_error
        if run_id in self.not_found:
            raise SystemExit(f"extraction run {run_id} not found in DB")
        return self.runs[run_id]

    async def lookup_run(self, run_id):
        self.lookup_calls.append(run_id)
        return self.lookups.get(run_id)

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
    _fixture(fixtures, PAPER_1, "run-1", _claims("cot.pdf"))
    _fixture(fixtures, PAPER_2, "run-2", _claims("react.pdf"))
    (fixtures / "arxiv-8888.00009v1.json").write_text("{not json", encoding="utf-8")   # another set's file
    matrix = tmp_path / "matrix_eval.json"
    _matrix(matrix, [PAPER_1, PAPER_2])
    return matrix, fixtures, tmp_path / "golden_text"


def _build(golden, fakes, with_lookup=True):
    matrix, fixtures, text_dir = golden
    messages = []
    written = asyncio.run(mod.build(
        matrix, fixtures, text_dir, load_run=fakes.load_run, resolve_pdf=fakes.resolve_pdf,
        extract_text=fakes.extract_text, lookup_run=fakes.lookup_run if with_lookup else None, log=messages.append,
    ))
    return written, messages


def _text_dir(golden):
    return golden[2]


# --- the existing DB-run path is unchanged ------------------------------------------------------

def test_writes_one_utf8_file_per_matrix_paper_named_like_the_dev_text_cache(golden):
    texts = {"cot.pdf": "Naïve – text. Chain of thought text.\n\nTwo.", "react.pdf": "ReAct text."}
    written, _ = _build(golden, Fakes(texts=texts))
    assert sorted(p.name for p in written) == ["1.0v1.txt", "2.0v1.txt"]
    assert (_text_dir(golden) / "1.0v1.txt").read_bytes() == texts["cot.pdf"].encode("utf-8")
    assert (_text_dir(golden) / "2.0v1.txt").read_bytes() == b"ReAct text."


def test_a_found_run_never_touches_the_lookup_and_the_cache_is_not_refreshed(golden):
    fakes = Fakes()
    _, messages = _build(golden, fakes)
    assert fakes.lookup_calls == []
    assert fakes.load_run_calls == [("run-1", False), ("run-2", False)]
    assert fakes.resolve_calls == [("cot.pdf", SHA_1), ("react.pdf", SHA_2)]
    assert fakes.extract_calls == [str(mod.Path("/pdfs/cot.pdf")), str(mod.Path("/pdfs/react.pdf"))]
    assert all("found via document_extractors.id" in m for m in messages if "pdf=" in m)


def test_not_found_without_a_lookup_still_exits_as_before(golden):
    fakes = Fakes(not_found=["run-1"])
    with pytest.raises(SystemExit, match="run-1 not found in DB"):
        _build(golden, fakes, with_lookup=False)
    assert not _text_dir(golden).exists()


# --- Branch A: the fallback lookup --------------------------------------------------------------

def _looked_up(sha, name, found_by="document_extractors.latest_run_id"):
    return {"content_hash": sha, "file_name": name, "found_by": found_by}


def test_a_not_found_run_is_resolved_through_the_lookup_and_its_sha_picks_the_pdf(golden):
    fakes = Fakes(not_found=["run-1", "run-2"], lookups={
        "run-1": _looked_up(SHA_1, "cot.pdf"),
        "run-2": _looked_up(SHA_2, "react.pdf", "paper_claims.extraction_run_id"),
    })
    written, messages = _build(golden, fakes)
    assert len(written) == 2
    assert fakes.lookup_calls == ["run-1", "run-2"]
    assert fakes.resolve_calls == [("cot.pdf", SHA_1), ("react.pdf", SHA_2)]
    assert any("run run-1 found via document_extractors.latest_run_id" in m for m in messages)
    assert any("run run-2 found via paper_claims.extraction_run_id" in m for m in messages)


def test_only_the_found_ones_fall_back(golden):
    fakes = Fakes(not_found=["run-2"], lookups={"run-2": _looked_up(SHA_2, "react.pdf")})
    _build(golden, fakes)
    assert fakes.lookup_calls == ["run-2"]


def test_a_run_found_nowhere_stops_for_all_papers_and_writes_nothing(golden):
    fakes = Fakes(not_found=["run-2"], lookups={})      # run-1 resolves normally, run-2 is found nowhere
    with pytest.raises(mod.GoldenTextError, match="run-2 is not a document_extractors.id, a document_extractors.latest_run_id"):
        _build(golden, fakes)
    assert not _text_dir(golden).exists()
    assert fakes.lookup_calls == ["run-2"]


def test_another_systemexit_is_not_a_fallback(golden):
    fakes = Fakes(load_error=SystemExit("no local PDF for something"), lookups={"run-1": _looked_up(SHA_1, "cot.pdf")})
    with pytest.raises(SystemExit, match="no local PDF"):
        _build(golden, fakes)
    assert fakes.lookup_calls == []


def test_another_error_is_not_a_fallback(golden):
    fakes = Fakes(load_error=RuntimeError("database is down"), lookups={"run-1": _looked_up(SHA_1, "cot.pdf")})
    with pytest.raises(RuntimeError, match="database is down"):
        _build(golden, fakes)
    assert fakes.lookup_calls == []


def test_a_sha256_mismatch_after_the_lookup_refuses_and_writes_nothing(golden):
    fakes = Fakes(not_found=["run-1", "run-2"], fail_pdf_for="react.pdf", lookups={
        "run-1": _looked_up(SHA_1, "cot.pdf"), "run-2": _looked_up(SHA_2, "react.pdf"),
    })
    with pytest.raises(mod.GoldenTextError, match="react.pdf matches sha256"):
        _build(golden, fakes)
    assert not _text_dir(golden).exists()


# --- lookup_run_by_run_id against a fake pool ---------------------------------------------------

class _Ctx:
    def __init__(self, value):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *exc):
        return False


class FakePool:
    """Answers each lookup by the column its SQL filters on: rows = {"latest_run_id": [...], "paper_claims": [...]}."""

    def __init__(self, rows):
        self.rows, self.executed, self.opened, self.closed = rows, [], False, False

    async def open(self):
        self.opened = True

    async def close(self):
        self.closed = True

    def connection(self):
        return _Ctx(self)

    def cursor(self):
        return _Ctx(self)

    async def execute(self, sql, params):
        key = "latest_run_id" if "de.latest_run_id" in sql else "paper_claims"
        self.executed.append((key, params))
        self._result = self.rows.get(key, [])

    async def fetchall(self):
        return self._result


def _lookup(rows, run_id="run-x"):
    pool = FakePool(rows)
    result = asyncio.run(mod.lookup_run_by_run_id(run_id, pool_factory=lambda: pool))
    return result, pool


def test_the_lookup_tries_latest_run_id_first_and_stops_there():
    result, pool = _lookup({"latest_run_id": [(SHA_1, "cot.pdf")], "paper_claims": [(SHA_2, "other.pdf")]})
    assert result == {"content_hash": SHA_1, "file_name": "cot.pdf", "found_by": "document_extractors.latest_run_id"}
    assert pool.executed == [("latest_run_id", ("run-x",))]
    assert pool.opened and pool.closed


def test_the_lookup_falls_back_to_paper_claims():
    result, pool = _lookup({"latest_run_id": [], "paper_claims": [(SHA_2, "react.pdf")]})
    assert result == {"content_hash": SHA_2, "file_name": "react.pdf", "found_by": "paper_claims.extraction_run_id"}
    assert [key for key, _ in pool.executed] == ["latest_run_id", "paper_claims"]


def test_the_lookup_finding_nothing_returns_none_and_closes_the_pool():
    result, pool = _lookup({})
    assert result is None and [key for key, _ in pool.executed] == ["latest_run_id", "paper_claims"] and pool.closed


def test_several_rows_for_one_file_count_as_one():
    result, _ = _lookup({"paper_claims": [(SHA_1, "cot.pdf")] * 5})
    assert result["file_name"] == "cot.pdf"


def test_two_different_files_for_one_run_are_refused_and_the_pool_is_still_closed():
    pool = FakePool({"latest_run_id": [(SHA_1, "cot.pdf"), (SHA_2, "react.pdf")]})
    with pytest.raises(mod.GoldenTextError, match="2 different files"):
        asyncio.run(mod.lookup_run_by_run_id("run-x", pool_factory=lambda: pool))
    assert pool.closed


def test_a_file_without_a_content_hash_is_refused():
    with pytest.raises(mod.GoldenTextError, match="no content_hash"):
        _lookup({"latest_run_id": [(None, "cot.pdf")]})


def test_the_lookup_sql_follows_the_run_id_through_file_id_to_file_records():
    (first_name, first_sql), (second_name, second_sql) = mod.RUN_ID_LOOKUPS
    assert (first_name, second_name) == ("document_extractors.latest_run_id", "paper_claims.extraction_run_id")
    for sql in (first_sql, second_sql):
        assert "JOIN   file_records fr ON fr.file_id = de.file_id" in sql and "fr.content_hash, fr.file_name" in sql
    assert "de.latest_run_id = %s" in first_sql and "pc.extraction_run_id = %s" in second_sql
    assert "JOIN   document_extractors de ON de.id = pc.document_extractor_id" in second_sql


# --- the Stage-1 guard ----------------------------------------------------------------------------

def _paper_fixture(golden, paper_id, run_id, claims):
    _fixture(golden[1], paper_id, run_id, claims)


def test_the_guard_passes_when_every_frozen_verdict_is_reproduced_including_a_span_that_failed_originally(golden):
    written, messages = _build(golden, Fakes())
    assert len(written) == 2
    assert sum("Stage-1 guard passed with normalize=False (2 frozen spans reproduced, both directions)" in m for m in messages) == 2


def test_a_span_that_passed_originally_but_scores_below_now_is_listed_and_nothing_is_written(golden):
    _paper_fixture(golden, PAPER_1, "run-1", _claims("cot.pdf", _span("Words the PDF text does not carry at all, qqq.")))
    with pytest.raises(mod.GoldenTextError) as exc:
        _build(golden, Fakes())
    message = str(exc.value)
    assert "nothing was written for any paper" in message
    assert f"{PAPER_1}: Stage-1 guard FAILED (3 frozen spans)" in message
    assert "claim 0 span 2: score" in message and "< 88, but the frozen span passed Stage 1 (status Pass, stance supports)" in message
    assert "normalize=False: 1 mismatching spans" in message and "normalize=True: 1 mismatching spans" in message
    assert not _text_dir(golden).exists()


def test_a_span_that_failed_originally_but_scores_at_or_above_now_is_listed(golden):
    claims = [{"evidence_spans": [_span(QUOTES["cot.pdf"], "Fail", None)]}]    # the quote IS in the text now
    _paper_fixture(golden, PAPER_1, "run-1", claims)
    with pytest.raises(mod.GoldenTextError, match=r"claim 0 span 0: score 100\.0 >= 88, but the frozen span failed Stage 1"):
        _build(golden, Fakes())
    assert not _text_dir(golden).exists()


def test_every_mismatch_of_every_paper_is_listed_in_one_message(golden):
    _paper_fixture(golden, PAPER_1, "run-1", _claims("cot.pdf", _span("Nothing like the text, qqq www.")))
    _paper_fixture(golden, PAPER_2, "run-2", [{"evidence_spans": [_span(QUOTES["react.pdf"], "Fail", None)]}])
    with pytest.raises(mod.GoldenTextError) as exc:
        _build(golden, Fakes())
    message = str(exc.value)
    assert f"{PAPER_1}: Stage-1 guard FAILED" in message and f"{PAPER_2}: Stage-1 guard FAILED" in message
    assert message.count("claim 0 span") >= 4          # both settings, both papers


def test_all_or_nothing_one_failing_paper_blocks_the_good_one(golden):
    _paper_fixture(golden, PAPER_2, "run-2", [{"evidence_spans": [_span(QUOTES["react.pdf"], "Fail", None)]}])
    with pytest.raises(mod.GoldenTextError):
        _build(golden, Fakes())
    assert not _text_dir(golden).exists()           # PAPER_1 passed its guard and still was not written


def test_the_second_setting_is_tried_only_after_the_first_fails_and_is_reported(golden, monkeypatch):
    calls = []

    def stage1(quote, text, normalize):
        calls.append(normalize)
        return 95.0 if normalize else 10.0          # the quote reproduces only with normalisation on

    monkeypatch.setattr(grounding, "_stage1_score", stage1)
    claims = [{"evidence_spans": [_span("quote A"), _span("quote B")]}]
    _paper_fixture(golden, PAPER_1, "run-1", claims)
    _paper_fixture(golden, PAPER_2, "run-2", claims)
    _, messages = _build(golden, Fakes())
    assert sum("Stage-1 guard passed with normalize=True (2 frozen spans" in m for m in messages) == 2
    assert calls == [False, False, True, True] * 2          # False for every span first, True only afterwards


def test_normalize_true_is_not_computed_when_normalize_false_reproduces_everything(golden, monkeypatch):
    seen = []
    real = grounding._stage1_score
    monkeypatch.setattr(grounding, "_stage1_score", lambda q, t, n: seen.append(n) or real(q, t, n))
    _build(golden, Fakes())
    assert seen and set(seen) == {False}


def test_one_setting_must_reproduce_every_span_never_a_mix_per_span(golden, monkeypatch):
    scores = {("quote A", False): 95.0, ("quote A", True): 10.0,      # A reproduces only without normalisation
              ("quote B", False): 10.0, ("quote B", True): 95.0,      # B reproduces only with it
              ("quote C", False): 95.0, ("quote C", True): 95.0}      # the other paper reproduces either way
    monkeypatch.setattr(grounding, "_stage1_score", lambda q, t, n: scores[(q, n)])
    _paper_fixture(golden, PAPER_1, "run-1", [{"evidence_spans": [_span("quote A"), _span("quote B")]}])
    _paper_fixture(golden, PAPER_2, "run-2", [{"evidence_spans": [_span("quote C")]}])
    with pytest.raises(mod.GoldenTextError) as exc:
        _build(golden, Fakes())
    message = str(exc.value)
    assert "normalize=False: 1 mismatching spans" in message and "normalize=True: 1 mismatching spans" in message
    assert "claim 0 span 1: score 10.0 < 88" in message and "claim 0 span 0: score 10.0 < 88" in message
    assert not _text_dir(golden).exists()


def test_the_threshold_is_productions_RAPIDFUZZ_THRESHOLD(golden, monkeypatch):
    monkeypatch.setattr(grounding, "_stage1_score", lambda q, t, n: 90.0)
    claims = [{"evidence_spans": [_span("a quote")]}]
    for pid, run in ((PAPER_1, "run-1"), (PAPER_2, "run-2")):
        _paper_fixture(golden, pid, run, claims)
    written, _ = _build(golden, Fakes())            # 90 >= 88: the stored pass is reproduced
    assert len(written) == 2
    for path in written:
        path.unlink()
    monkeypatch.setattr(grounding, "RAPIDFUZZ_THRESHOLD", 95)
    with pytest.raises(mod.GoldenTextError, match="score 90.0 < 95"):
        _build(golden, Fakes())


def test_a_skipped_span_without_a_stance_counts_as_having_passed_stage_one(golden):
    claims = [{"evidence_spans": [_span(QUOTES["cot.pdf"], "Skipped", None)]}]    # reached the audit, which errored
    _paper_fixture(golden, PAPER_1, "run-1", claims)
    written, _ = _build(golden, Fakes())
    assert len(written) == 2


def test_a_fail_with_a_stance_counts_as_having_passed_stage_one(golden):
    claims = [{"evidence_spans": [_span(QUOTES["cot.pdf"], "Fail", "refutes")]}]  # failed the LLM audit, not Stage 1
    _paper_fixture(golden, PAPER_1, "run-1", claims)
    written, _ = _build(golden, Fakes())
    assert len(written) == 2


@pytest.mark.parametrize("claims", [[], [{"evidence_spans": []}], [{"claim_text_verbatim": "no spans key"}], None])
def test_a_fixture_with_no_frozen_span_stops_the_run(golden, claims):
    _paper_fixture(golden, PAPER_1, "run-1", claims)
    with pytest.raises(mod.GoldenTextError, match="no frozen evidence spans"):
        _build(golden, Fakes())
    assert not _text_dir(golden).exists()


@pytest.mark.parametrize("span", [
    {"source_text": "a quote", "source_section": "s", "stance": None},                    # no grounding_status
    {"source_text": "  ", "source_section": "s", "grounding_status": "Pass", "stance": "supports"},   # no quote
    {"source_section": "s", "grounding_status": "Pass", "stance": "supports"},            # no source_text key
])
def test_a_span_that_cannot_be_checked_stops_the_run(golden, span):
    _paper_fixture(golden, PAPER_1, "run-1", [{"evidence_spans": [span]}])
    with pytest.raises(mod.GoldenTextError, match="no source_text or no frozen grounding_status"):
        _build(golden, Fakes())
    assert not _text_dir(golden).exists()


# --- the guards that were already there ------------------------------------------------------------

def test_a_sha256_mismatch_refuses_and_writes_nothing_even_for_the_papers_before_it(golden):
    fakes = Fakes(fail_pdf_for="react.pdf")   # the second paper fails after the first one succeeded
    with pytest.raises(mod.GoldenTextError, match="react.pdf matches sha256"):
        _build(golden, fakes)
    assert not _text_dir(golden).exists()


def test_an_existing_text_file_is_refused_before_any_work(golden):
    text_dir = _text_dir(golden)
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
    (golden[1] / f"{PAPER_2}.json").write_text(json.dumps({"header": {}, "claims": _claims("react.pdf")}), encoding="utf-8")
    fakes = Fakes()
    with pytest.raises(mod.GoldenTextError, match="no extraction_run_id"):
        _build(golden, fakes)
    assert fakes.load_run_calls == []


def test_a_missing_fixture_file_is_refused(golden):
    (golden[1] / f"{PAPER_1}.json").unlink()
    with pytest.raises(mod.GoldenTextError, match="no fixture file"):
        _build(golden, Fakes())


@pytest.mark.parametrize("bad_text, message", [("", "is empty"), ("   \n", "is empty"), ("a\r\nb", "carriage returns")])
def test_empty_text_and_text_with_carriage_returns_are_refused_and_nothing_is_written(golden, bad_text, message):
    fakes = Fakes(texts={"cot.pdf": TEXTS["cot.pdf"], "react.pdf": bad_text})
    with pytest.raises(mod.GoldenTextError, match=message):
        _build(golden, fakes)
    assert not _text_dir(golden).exists()


def test_the_log_names_the_pdf_the_sha_prefix_and_the_size(golden):
    _, messages = _build(golden, Fakes())
    first = next(m for m in messages if "1.0v1" in m and "pdf=" in m)
    assert "pdf=cot.pdf" in first and f"sha256={SHA_1[:12]}" in first and f"{len(TEXTS['cot.pdf'])} chars" in first


def test_the_default_paths_are_the_golden_constants_of_replay_audit():
    from eval import replay_audit
    args = mod._build_parser().parse_args([])
    assert (args.matrix_path, args.fixture_dir, args.text_dir) == (
        replay_audit.GOLDEN_MATRIX_PATH, replay_audit.GOLDEN_FIXTURE_DIR, replay_audit.GOLDEN_TEXT_CACHE_DIR,
    )
    assert "scratch" in args.text_dir.parts   # under the folder the repo-root .gitignore excludes
