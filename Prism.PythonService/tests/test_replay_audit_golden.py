"""eval/replay_audit.py --set golden: the golden matrix's papers, replayed from their own fixtures and
text folder into their own output root. Offline: invented fixtures, matrix and paper text in tmp_path, the
fake SDK from tests/replay_fakes.py. Nothing real is read.

A file of another set (a stand-in for a held-out fixture, deliberately not valid JSON) sits in the golden
fixture folder in every test: reading it would fail loudly, so a pass also shows it was never opened."""
import argparse
import asyncio
import json
import shutil

import pytest

from eval import replay_audit
from extraction import engine

import replay_fakes
from replay_fakes import MODEL, PAPER_A, PAPER_B, PAPER_TEXTS, FakeSdk

FOREIGN = "arxiv-8888.00009v1"
MARKER = "GOLDEN-TEXT-MARKER"
VERTEX = dict(backend="vertex", vertex_project="proj-x", vertex_location="global")


def _args(claims_path, **overrides) -> argparse.Namespace:
    values = dict(
        level="medium", claims=str(claims_path), papers=None, repeat=1, estimate=False, dry_run=False,
        max_inr=None, cache=False,
    )
    values.update(overrides)
    return argparse.Namespace(**values)


def _run(claims_path, **overrides) -> int:
    return asyncio.run(replay_audit._main(_args(claims_path, **overrides)))


def _golden_matrix(paper_ids) -> dict:
    return {
        "metadata": {"pass_threshold": {"refusal_rate": 0.7, "positive_hit_floor": 10}},
        "papers": [
            {
                "paper_id": pid, "filename": f"{pid}.pdf", "title": pid,
                "expected_matrix": [{"id": f"{pid}-1", "expected_label": "supported", "grounding_negative": False}],
            }
            for pid in paper_ids
        ],
    }


@pytest.fixture
def golden(tmp_path, monkeypatch):
    """A dev setup (tests/replay_fakes.py) plus a separate golden set: fixtures, text (marked, so a read of
    the dev text is detectable), matrix and output root, all under tmp_path. Returns (sdk, claims_path)."""
    sdk = FakeSdk()
    claims_path = replay_fakes.setup_replay(tmp_path, monkeypatch, sdk)
    fixtures = tmp_path / "golden_fixtures"
    texts = tmp_path / "golden_text"
    fixtures.mkdir()
    texts.mkdir()
    for pid in (PAPER_A, PAPER_B):
        shutil.copy(tmp_path / "run1" / f"{pid}.json", fixtures / f"{pid}.json")
        (texts / f"{pid[len('arxiv-'):]}.txt").write_text(f"{MARKER} {PAPER_TEXTS[pid]}", encoding="utf-8")
    (fixtures / f"{FOREIGN}.json").write_text("{this is not json", encoding="utf-8")
    matrix = tmp_path / "matrix_eval.json"
    matrix.write_text(json.dumps(_golden_matrix([PAPER_A, PAPER_B])), encoding="utf-8")

    monkeypatch.setattr(replay_audit, "GOLDEN_FIXTURE_DIR", fixtures)
    monkeypatch.setattr(replay_audit, "GOLDEN_TEXT_CACHE_DIR", texts)
    monkeypatch.setattr(replay_audit, "GOLDEN_MATRIX_PATH", matrix)
    monkeypatch.setattr(replay_audit, "GOLDEN_OUTPUT_ROOT", tmp_path / "golden_out")
    for name, value in (
        ("llm_claim_audit_fallback_model", "gemini-3.1-flash-lite"),
        ("llm_grounding_model", "groq/openai/gpt-oss-20b"),
        ("llm_grounding_fallback_model", "gemini/gemini-3.1-flash-lite"),
        ("ai_api_key", "test-aistudio-key"),
    ):
        monkeypatch.setattr(engine.settings, name, value)
    return sdk, claims_path


def _claims_file(tmp_path, entries) -> object:
    path = tmp_path / "claims_foreign.json"
    path.write_text(json.dumps(entries), encoding="utf-8")
    return path


def _load(claims_path, papers=None):
    with replay_audit.active_dataset(replay_audit._golden_dataset()):
        return replay_audit._load_targets(claims_path, papers)


# --- which papers the golden set may load ----------------------------------------------------

def test_golden_targets_without_a_claims_file_are_exactly_the_matrix_papers(golden):
    targets = _load(None)
    assert {t.paper_id for t in targets} == {PAPER_A, PAPER_B}
    assert len(targets) == len(replay_fakes.CLAIMS)   # FOREIGN sits in the folder but is not listed


def test_golden_claims_file_targets_are_loaded_from_the_golden_fixtures(golden):
    _, claims_path = golden
    targets = _load(claims_path)
    assert {(t.paper_id, t.claim_index) for t in targets} == {(pid, i) for pid, i, *_ in replay_fakes.CLAIMS}


def test_a_foreign_id_in_the_claims_file_is_rejected_before_any_fixture_is_read(golden, tmp_path):
    entries = [{"paper_id": PAPER_A, "claim_index": 0}, {"paper_id": FOREIGN, "claim_index": 0}]
    with pytest.raises(replay_audit.PaperTextError, match="not a paper of the golden set"):
        _load(_claims_file(tmp_path, entries))   # FOREIGN's fixture is invalid JSON: a read would be a JSONDecodeError


def test_an_unknown_id_is_rejected(golden, tmp_path):
    with pytest.raises(replay_audit.PaperTextError, match="not a paper of the golden set"):
        _load(_claims_file(tmp_path, [{"paper_id": "arxiv-0000.00000v1", "claim_index": 0}]))


@pytest.mark.parametrize("bad_id", ["../etc/passwd", "a/b", "a\\b", "..", "."])
def test_path_like_ids_are_rejected(golden, tmp_path, bad_id):
    with pytest.raises(replay_audit.PaperTextError, match="not a plain paper id"):
        _load(_claims_file(tmp_path, [{"paper_id": bad_id, "claim_index": 0}]))


def test_papers_filter_only_narrows_the_allowlist(golden):
    assert _load(None, "8888") == []
    assert {t.paper_id for t in _load(None, "0001")} == {PAPER_A}


def test_an_allowed_id_without_a_fixture_file_is_rejected(golden, tmp_path):
    (tmp_path / "golden_fixtures" / f"{PAPER_B}.json").unlink()
    with pytest.raises(replay_audit.PaperTextError, match="no golden fixture file"):
        _load(None)


@pytest.mark.parametrize("body", ["[]", json.dumps({"claims": []}), json.dumps({"header": {}, "claims": []})])
def test_a_fixture_without_header_claims_and_matches_is_rejected(golden, tmp_path, body):
    (tmp_path / "golden_fixtures" / f"{PAPER_A}.json").write_text(body, encoding="utf-8")
    with pytest.raises(replay_audit.PaperTextError, match="lacks"):
        _load(None)


def test_load_paper_text_checks_the_set_too(golden):
    with replay_audit.active_dataset(replay_audit._golden_dataset()):
        assert replay_audit._load_paper_text(PAPER_A).startswith(MARKER)
        with pytest.raises(replay_audit.PaperTextError, match="not a paper of the golden set"):
            replay_audit._load_paper_text(FOREIGN)


def test_the_active_set_is_restored_after_the_block_and_after_an_exception(golden, tmp_path):
    dev_fixture_dir = replay_audit._fixture_dir()
    with replay_audit.active_dataset(replay_audit._golden_dataset()):
        assert replay_audit._fixture_dir() == tmp_path / "golden_fixtures"
    assert replay_audit._fixture_dir() == dev_fixture_dir
    with pytest.raises(RuntimeError):
        with replay_audit.active_dataset(replay_audit._golden_dataset()):
            raise RuntimeError("boom")
    assert replay_audit._fixture_dir() == dev_fixture_dir
    assert replay_audit._output_root() == tmp_path / "out" and replay_audit._text_dir() == tmp_path / "raw_text_cache"


# --- the golden run --------------------------------------------------------------------------

def test_a_golden_run_writes_under_the_golden_root_and_marks_the_header(golden, tmp_path):
    sdk, claims_path = golden
    assert _run(claims_path, dataset="golden") == 0
    folder = tmp_path / "golden_out" / "exp1_medium_1"
    assert sorted(p.name for p in folder.glob("arxiv-*.json")) == [f"{PAPER_A}.json", f"{PAPER_B}.json"]
    assert not (tmp_path / "out").exists()   # nothing went to the dev output root
    header = json.loads((folder / f"{PAPER_A}.json").read_text("utf-8"))["header"]
    assert header["replay"]["set"] == "golden" and header["replay"]["repeat_index"] == 1
    assert sdk.kinds().count("audit") == len(replay_fakes.CLAIMS)


def test_a_golden_vertex_run_names_the_folder_like_dev_but_under_the_golden_root(golden, tmp_path):
    sdk, claims_path = golden
    assert _run(claims_path, dataset="golden", **VERTEX) == 0
    folder = tmp_path / "golden_out" / f"exp1_medium_{MODEL}-vertex_1"
    summary = json.loads((folder / "_summary.json").read_text("utf-8"))
    assert summary["run_config"]["backend"] == "vertex"
    claim = json.loads((folder / f"{PAPER_A}.json").read_text("utf-8"))["claims"][0]
    assert claim["audit_model_served"] == MODEL
    assert not (tmp_path / "out").exists()


def test_a_golden_run_audits_the_golden_text_not_the_dev_text(golden):
    sdk, claims_path = golden
    assert _run(claims_path, dataset="golden") == 0
    from replay_fakes import _text_of
    audit_texts = [_text_of(contents) for kind, _model, contents, _config in sdk.calls if kind == "audit"]
    assert audit_texts and all(MARKER in text for text in audit_texts)


def test_missing_golden_text_aborts_with_zero_calls(golden, tmp_path, capsys):
    sdk, claims_path = golden
    (tmp_path / "golden_text" / f"{PAPER_B[len('arxiv-'):]}.txt").unlink()
    assert _run(claims_path, dataset="golden") == 1
    assert "no cached paper text" in capsys.readouterr().out
    assert sdk.calls == [] and not (tmp_path / "golden_out").exists()


def test_a_foreign_id_in_the_claims_file_aborts_the_run_with_zero_calls(golden, tmp_path, capsys):
    sdk, _ = golden
    claims = _claims_file(tmp_path, [{"paper_id": FOREIGN, "claim_index": 0}])
    assert _run(claims, dataset="golden") == 1
    assert "ABORT" in capsys.readouterr().out
    assert sdk.calls == [] and not (tmp_path / "golden_out").exists()


def test_a_legacy_fixture_aborts_the_run_with_zero_calls(golden, tmp_path, capsys):
    sdk, claims_path = golden
    (tmp_path / "golden_fixtures" / f"{PAPER_A}.json").write_text("[]", encoding="utf-8")
    assert _run(claims_path, dataset="golden") == 1
    assert "lacks" in capsys.readouterr().out
    assert sdk.calls == []


def test_an_unreadable_golden_matrix_aborts_the_run_with_zero_calls(golden, tmp_path, monkeypatch, capsys):
    sdk, claims_path = golden
    monkeypatch.setattr(replay_audit, "GOLDEN_MATRIX_PATH", tmp_path / "no_such_matrix.json")
    assert _run(claims_path, dataset="golden") == 1
    assert "cannot load the golden set" in capsys.readouterr().out
    assert sdk.calls == []


def test_dry_run_reports_golden_text_presence_and_makes_no_call(golden, tmp_path, capsys):
    sdk, claims_path = golden
    (tmp_path / "golden_text" / f"{PAPER_B[len('arxiv-'):]}.txt").unlink()
    assert _run(claims_path, dataset="golden", dry_run=True) == 0
    out = capsys.readouterr().out
    assert f"DRY-RUN cache {PAPER_A}: found" in out and f"DRY-RUN cache {PAPER_B}: MISSING" in out
    assert sdk.calls == [] and not (tmp_path / "golden_out").exists()


def test_estimate_with_the_golden_set_makes_no_call(golden, capsys):
    sdk, claims_path = golden
    assert _run(claims_path, dataset="golden", estimate=True) == 0
    assert "estimated cost" in capsys.readouterr().out and sdk.calls == []


# --- the dev set is what it was --------------------------------------------------------------

def test_explicit_set_dev_writes_the_same_files_as_no_flag(golden, tmp_path):
    sdk, claims_path = golden

    def papers() -> dict[str, bytes]:
        return {p.name: p.read_bytes() for p in sorted((tmp_path / "out" / "exp1_medium_1").glob("arxiv-*.json"))}

    assert _run(claims_path) == 0
    without_flag = papers()
    shutil.rmtree(tmp_path / "out")
    assert _run(claims_path, dataset="dev") == 0
    assert without_flag and papers() == without_flag
    assert not (tmp_path / "golden_out").exists()
    assert all("set" not in json.loads(raw)["header"]["replay"] for raw in without_flag.values())   # dev files carry no set marker


def test_parser_set_option():
    parser = replay_audit._build_parser()
    assert parser.parse_args(["--level", "high"]).dataset == "dev"
    assert parser.parse_args(["--level", "high", "--set", "golden"]).dataset == "golden"
    with pytest.raises(SystemExit) as exc:
        parser.parse_args(["--level", "high", "--set", "heldout"])
    assert exc.value.code == 2
