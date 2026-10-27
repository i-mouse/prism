"""Shared offline fakes for the replay_audit tests that run the whole replay
pipeline (snapshot and scope-check tests).

Everything here is invented: tiny made-up paper text and claims, a fake
google-genai client that returns canned responses, a deterministic grounding
stand-in and pinned clocks. Nothing reads raw_text_cache/ or any real paper, and
nothing touches the network.

The fake client tells calls apart by their config, not by importing the scope
modules, so this file works on code that has no scope check yet.
"""
import json
import re
from types import SimpleNamespace

from eval import replay_audit
from extraction import context_cache, engine, grounding
from extraction.schemas import ClaimFinal, ClaimLabel, EvidenceSpanFinal, GroundingStatus

MODEL = "gemini-3.6-flash"
PAPER_A = "arxiv-9999.00001v1"
PAPER_B = "arxiv-9999.00002v1"

PAPER_TEXTS = {
    PAPER_A: (
        "Abstract. We study pitch control for wind turbines.\n\n"
        "Results. The controller reduces fatigue load on turbine models T1, T2 and T3.\n"
        "Table 2: Fatigue load change (percent)\n"
        "Model | Low wind | Gusty wind\n"
        "T1 | -12.4 | -9.1\n"
        "T2 | -10.8 | -7.7\n"
        "T3 | -11.2 | +1.3\n"
        "Limitations. On T3 the gusty-wind load rose slightly (+1.3 percent).\n"
    ),
    PAPER_B: (
        "Abstract. We compare optimisers on two toy tasks.\n\n"
        "Results. Method M beats the baseline on task X by 3 points and on task Y by 5 points.\n"
    ),
}

# (paper_id, claim_index, claim_text_verbatim, claim_summary, label the canned auditor gives it)
CLAIMS = [
    (PAPER_A, 0, "The controller reduces fatigue load on all three turbine models.", "Fatigue load falls on all models.", "supported"),
    (PAPER_A, 1, "The controller reduces fatigue load under both low and gusty wind.", "Load falls in both wind regimes.", "supported"),
    (PAPER_A, 2, "Gusty wind is harder than low wind for every model.", "Gusty wind is harder.", "partially_supported"),
    (PAPER_B, 0, "Method M beats the baseline on both tasks.", "M beats the baseline.", "supported"),
    (PAPER_B, 1, "Method M is the fastest method.", "M is fastest.", "not_supported"),
]
LABEL_BY_CLAIM = {text: label for _, _, text, _, label in CLAIMS}

AUDIT_CANARY = "AUDITOR-REASONING-CANARY"

_CLAIM_RE = re.compile(r"CLAIM_TEXT_VERBATIM: (.*)")
_VERDICT_RE = re.compile(r"VERDICT: (\w+)")


def _usage(prompt, output, thought, cached=0):
    return SimpleNamespace(
        prompt_token_count=prompt, candidates_token_count=output, thoughts_token_count=thought,
        total_token_count=prompt + output + thought, cached_content_token_count=cached,
        tool_use_prompt_token_count=0,
    )


def _text_of(contents) -> str:
    return "\n".join(part.text for content in contents for part in content.parts)


class FakeSdk:
    """Fake google-genai client. `calls` records (kind, model, contents, config)
    for every generate_content; `kind` is audit / structure / lister / checker.

    lister_fn(claim_text) and checker_fn(user_text) return the response text for
    the scope calls (default: no scope items, so the checker is never called); an
    exception they raise is raised from generate_content.
    """

    def __init__(self, tokens=40_000, create_error=None, lister_fn=None, checker_fn=None):
        self.tokens = tokens
        self.create_error = create_error
        self.lister_fn = lister_fn or (lambda claim: json.dumps({"items": []}))
        self.checker_fn = checker_fn or (lambda text: json.dumps({"items": []}))
        self.created: list = []
        self.deleted: list[str] = []
        self.calls: list = []
        self.requested_models: list[str] = []  # every generate_content attempt, including ones that raise
        self._n_caches = 0
        self.client = SimpleNamespace(aio=SimpleNamespace(
            caches=SimpleNamespace(create=self._create, delete=self._delete),
            models=SimpleNamespace(generate_content=self._generate),
        ))

    async def _create(self, *, model, config):
        if self.create_error is not None:
            raise self.create_error
        self._n_caches += 1
        self.created.append(config)
        return SimpleNamespace(
            name=f"cachedContents/fake{self._n_caches}", usage_metadata=SimpleNamespace(total_token_count=self.tokens),
        )

    async def _delete(self, *, name):
        self.deleted.append(name)

    async def _generate(self, *, model, contents, config):
        self.requested_models.append(model)
        schema_name = getattr(config.response_schema, "__name__", None)
        text_in = _text_of(contents)
        cached = bool(config.cached_content)
        if schema_name is None:
            kind = "audit"
            claim = _CLAIM_RE.search(text_in).group(1)
            label = LABEL_BY_CLAIM[claim]
            text = f"Reasoning about the claim. {AUDIT_CANARY}\nVERDICT: {label}\nQUOTE: q\nSECTION: Results"
            usage = _usage(self.tokens, 120, 300, 39_500 if cached else 0)
        elif schema_name == "ClaimLLM":
            kind = "structure"
            claim = _CLAIM_RE.search(text_in).group(1)
            label = _VERDICT_RE.search(text_in).group(1)
            text = json.dumps({
                "claim_text_verbatim": claim, "claim_summary": "summary", "label": label,
                "evidence_spans": [{"source_text": "Results.", "source_section": "Results"}],
            })
            usage = _usage(1_400, 250, 800)
        elif schema_name == "ScopeListResponse":
            kind = "lister"
            text = self.lister_fn(text_in)
            usage = _usage(500, 60, 100)
        elif schema_name == "ScopeCheckResponse":
            kind = "checker"
            text = self.checker_fn(text_in)
            usage = _usage(self.tokens, 200, 400, 39_500 if cached else 0)
        else:
            raise AssertionError(f"unexpected response_schema {schema_name}")
        self.calls.append((kind, model, contents, config))
        return SimpleNamespace(text=text, parsed=None, usage_metadata=usage)

    def kinds(self) -> list[str]:
        return [kind for kind, *_ in self.calls]


async def fake_ground(extraction, paper_text, chat_id, **kwargs):
    """Deterministic stand-in for grounding.ground_extraction."""
    finals = []
    for claim in extraction.claims:
        failed = claim.label == ClaimLabel.NOT_SUPPORTED
        finals.append(ClaimFinal(
            claim_text_verbatim=claim.claim_text_verbatim, claim_summary=claim.claim_summary, label=claim.label,
            evidence_spans=[
                EvidenceSpanFinal(
                    source_text=span.source_text, source_section=span.source_section,
                    grounding_status=GroundingStatus.FAIL if failed else GroundingStatus.PASS,
                    stance="neutral" if failed else "supports",
                )
                for span in claim.evidence_spans
            ],
            grounding_status=GroundingStatus.FAIL if failed else GroundingStatus.PASS,
            missing=failed, reason="canned",
        ))
    return finals


def pin_clocks(monkeypatch, step: float = 0.5) -> None:
    """Pins every volatile time source of a replay run: replay_audit's
    time.monotonic (call latency) and time.strftime (header generated_at), and
    context_cache's time.monotonic (cache lifetime). One shared counter, so the
    values depend only on call order."""
    ticks = iter(i * step for i in range(1, 100_000))
    stub = SimpleNamespace(
        monotonic=lambda: next(ticks),
        strftime=lambda fmt, t=None: "2026-01-01T00:00:00Z",
        gmtime=lambda *a: None,
    )
    monkeypatch.setattr(replay_audit, "time", stub)
    monkeypatch.setattr(context_cache, "time", stub)


def setup_replay(tmp_path, monkeypatch, sdk: FakeSdk, claims=CLAIMS):
    """Points replay_audit at invented fixtures and paper text under tmp_path,
    swaps the SDK client and grounding for fakes, pins the clocks. Returns the
    claims-file path."""
    fixture_dir = tmp_path / "run1"
    fixture_dir.mkdir()
    cache_dir = tmp_path / "raw_text_cache"
    cache_dir.mkdir()
    papers: dict[str, list] = {}
    for paper_id, index, text, summary, _label in claims:
        papers.setdefault(paper_id, []).append({"index": index, "claim_text_verbatim": text, "claim_summary": summary})
    for paper_id, paper_claims in papers.items():
        (fixture_dir / f"{paper_id}.json").write_text(json.dumps({
            "header": {"title": f"invented {paper_id}"}, "matches": [], "claims": paper_claims,
        }), encoding="utf-8")
        (cache_dir / f"{paper_id[len('arxiv-'):]}.txt").write_text(PAPER_TEXTS[paper_id], encoding="utf-8")
    claims_path = tmp_path / "claims.json"
    claims_path.write_text(json.dumps([
        {"paper_id": paper_id, "claim_index": index} for paper_id, index, *_ in claims
    ]), encoding="utf-8")

    monkeypatch.setattr(replay_audit, "FIXTURE_DIR", fixture_dir)
    monkeypatch.setattr(replay_audit, "RAW_TEXT_CACHE_DIR", cache_dir)
    monkeypatch.setattr(replay_audit, "OUTPUT_ROOT", tmp_path / "out")
    monkeypatch.setattr(
        replay_audit, "get_prompt_version",
        lambda scope_check=False: "scopehash001" if scope_check else replay_audit.EXPECTED_PROMPT_HASH,
    )
    monkeypatch.setattr(engine, "LOGS_DIR", tmp_path / "logs")
    monkeypatch.setattr(engine, "BACKOFF_SECONDS", (0, 0, 0))
    monkeypatch.setattr(engine.settings, "llm_claim_audit_model", MODEL)
    monkeypatch.setattr(engine, "_build_client", lambda: sdk.client)
    monkeypatch.setattr(grounding, "ground_extraction", fake_ground)
    pin_clocks(monkeypatch)
    return claims_path
