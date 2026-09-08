# LLM Model Variable Audit (2026-09-07)

## Fact Table

| File:line | Function | Env var or literal | Pipeline stage | On eval path? | Has fallback? |
|---|---|---|---|---|---|
| `Prism.PythonService/extraction/engine.py:150` | `_generate_with_fallback` | `settings.llm_extraction_model` | `extraction` | Yes | Yes |
| `Prism.PythonService/extraction/engine.py:158` | `_generate_with_fallback` | `settings.llm_extraction_fallback_model` | `extraction` | Yes | No |
| `Prism.PythonService/extraction/grounding.py:422` | `_audit_span_with_llm` | `settings.llm_audit_primary_model` | `span-grounding` | No | Yes |
| `Prism.PythonService/extraction/grounding.py:423` | `_audit_span_with_llm` | `settings.llm_audit_fallback_model` | `span-grounding` | No | No |
| `Prism.PythonService/agent_service.py:43` | `(module scope)` | `os.getenv("LLM_AGENT_MODEL")` | `chat` | No | No |
| `Prism.PythonService/agent_service.py:48` | `(module scope)` | `"gemini-flash-latest"` (commented) | `router` | No | No |
| `Prism.PythonService/agent_service.py:49` | `(module scope)` | `os.getenv("LLM_FAST_MODEL")` | `router` | No | No |
| `Prism.PythonService/paper_chat/agent.py:78` | `(module scope)` | `settings.llm_agent_model` | `chat` | No | No |
| `Prism.PythonService/paper_chat/agent.py:83` | `(module scope)` | `settings.llm_fast_model` | `router` | No | No |
| `Prism.PythonService/ai_service.py:21` | `analyize_text` | `os.getenv("LLM_SUMMARY_MODEL")` | `summary` | No | No |
| `Prism.PythonService/ai_service.py:46` | `transcribe_audio` | `os.getenv("LLM_SUMMARY_MODEL")` | `summary` | No | No |
| `Prism.PythonService/eval/matcher.py:29` | `(module scope)` | `"gemini-3.1-flash-lite"` (DEFAULT_MODEL) | `eval-matcher` | Yes | N/A |
| `Prism.PythonService/eval/matcher.py:125` | `match_claims` | `os.getenv("LLM_AUDIT_MODEL")` | `eval-matcher` | Yes | Yes |
| `Prism.PythonService/eval/matcher.py:150` | `match_claims` | `os.getenv("LLM_EXTRACTION_MODEL")` | `eval-matcher` | Yes | No |
| `Prism.PythonService/eval/dump_fixture.py:198` | `main` | `os.getenv("LLM_EXTRACTION_MODEL")` | `other` | No | No |
| `Prism.PythonService/eval/dump_fixture.py:199` | `main` | `os.getenv("LLM_AUDIT_MODEL")` | `other` | No | No |
| `Prism.AppHost/AppHost.cs:139-146` | `(builder)` | Literal strings (`"gemini-3.6-flash"`, `"gemini-3.1-flash-lite"`, `"groq/openai/gpt-oss-20b"`, `"gemini/gemini-3.1-flash-lite"`) | `other` | No | N/A |
| `Prism.AppHost/AppHost.cs:193-200` | `(builder)` | Literal strings (same as above) | `other` | No | N/A |

*(Note: There are also numerous hardcoded model string literals used exclusively in unit/integration tests within `Prism.PythonService/eval/tests/` and test fixtures in `docs/evals/fixtures/`)*

## Specific Questions

**1. The eval matcher.** How does `eval/`'s LLM-as-judge resolve its model? Env var, `PrismSettings` field, or hardcoded literal? If it shares a var with a production call path, name that var explicitly.
The eval matcher resolves its primary model via a raw env var read: `os.getenv("LLM_AUDIT_MODEL", DEFAULT_MODEL)` (`eval/matcher.py:125`). It resolves its fallback model via another raw env var read: `os.getenv("LLM_EXTRACTION_MODEL")` (`eval/matcher.py:150`). It also defines a hardcoded literal `DEFAULT_MODEL = "gemini-3.1-flash-lite"` (`eval/matcher.py:29`) if the primary var is missing.
It shares BOTH variables with production paths. `LLM_AUDIT_MODEL` is injected into the production `AppHost.cs` container definitions (though currently dead config in the app itself), and `LLM_EXTRACTION_MODEL` is the production model for the extraction pipeline.

**2. Which of the three extraction calls (extractor / auditor / structurer) use which var? Confirm whether auditor and structurer genuinely share one.**
All three extraction calls (extractor, auditor, and structurer) use the **exact same variable**: `settings.llm_extraction_model`. They all delegate to `_generate_with_fallback`, which hardcodes `model_name = settings.llm_extraction_model` (`extraction/engine.py:150`). Therefore, yes, the auditor and structurer genuinely share one variable, despite earlier documentation or variable naming suggesting `LLM_AUDIT_MODEL` was used.

**3. Does `LLM_EXTRACTION_FALLBACK_MODEL` cover all three extraction calls, or only some?**
It covers **all three**. Every Gemini call in `extract_claims` goes through `_generate_with_fallback`, which implements the fallback to `settings.llm_extraction_fallback_model` (`extraction/engine.py:158`).

**4. List every hardcoded model string literal still in the codebase after PR 1.**
- `Prism.AppHost/AppHost.cs:139-146, 193-200`: `"gemini-3.6-flash"`, `"gemini-3.1-flash-lite"`, `"groq/openai/gpt-oss-20b"`, `"gemini/gemini-3.1-flash-lite"`
- `Prism.PythonService/agent_service.py:48`: `# model="gemini-flash-latest"` (in a comment)
- `Prism.PythonService/eval/matcher.py:29`: `DEFAULT_MODEL = "gemini-3.1-flash-lite"`
- Test files and fixtures (`eval/tests/test_dump_fixture.py`, `test_data_source.py`, `test_matrix_runner_fixture_mode.py`, `test_check_fixture_freshness.py`, `docs/evals/fixtures/...`): `"gemini-2.5-flash"`, `"gemini-2.5-flash-lite"`, `"gemini-3.6-flash"`, `"gemini-3.1-flash-lite"`

**5. Are there vars declared in `PrismSettings` or `AppHost.cs` that no code actually reads? (dead config)**
Yes. `llm_audit_model` is defined in `PrismSettings` (`config.py:52`) but no Python code references `settings.llm_audit_model`. `AppHost.cs` blindly injects `LLM_AUDIT_MODEL` into both the Python API and Python Worker containers (`AppHost.cs:140`, `194`), but the production application ignores it. (Only the eval scripts read `LLM_AUDIT_MODEL` via raw `os.getenv`).

**6. Are there model reads NOT backed by a `PrismSettings` field — raw `os.getenv` with a silent `None`, or a default?**
Yes. Several files bypass `PrismSettings` entirely:
- `Prism.PythonService/agent_service.py` uses raw `os.getenv("LLM_AGENT_MODEL")` and `os.getenv("LLM_FAST_MODEL")` (silent None)
- `Prism.PythonService/ai_service.py` uses raw `os.getenv("LLM_SUMMARY_MODEL")` (silent None)
- `Prism.PythonService/eval/matcher.py` uses raw `os.getenv("LLM_AUDIT_MODEL", DEFAULT_MODEL)` (with default) and `os.getenv("LLM_EXTRACTION_MODEL")` (silent None)
- `Prism.PythonService/eval/dump_fixture.py` uses raw `os.getenv("LLM_EXTRACTION_MODEL", "")` and `os.getenv("LLM_AUDIT_MODEL", DEFAULT_MODEL)`

**7. Does `eval/dump_fixture.py` record the model name(s) in the fixture header? Which ones? Would a fixture generated under two different auditor models be distinguishable after the fact?**
Yes, it records two values in the header:
- `model_name` (read from `os.getenv("LLM_EXTRACTION_MODEL")`)
- `matcher_model` (read from `os.getenv("LLM_AUDIT_MODEL", DEFAULT_MODEL)`)
No, a fixture generated under two different auditor models would **not** be distinguishable after the fact. First, `dump_fixture.py` reads the primary env vars at startup rather than tracking which models were actually used at runtime (e.g., if a fallback was triggered, it goes unrecorded). Second, since the extraction pipeline's auditor strictly uses `LLM_EXTRACTION_MODEL`, changing `LLM_AUDIT_MODEL` would only change the `matcher_model` string recorded in the fixture header without affecting the actual extraction auditor at all.

**8. `Prism.ApiService/` — does any C# code choose a model name?**
No. A search confirms there are no model names hardcoded or resolved in `Prism.ApiService`. Model names are entirely localized to Python code and the `AppHost.cs` infra orchestrator.

## Proposal

The new naming scheme eliminates sharing and makes the pipeline stage explicit.

**Migration Table**

| Old Name | Proposed New Name | Files Touched | Requires Live update? |
|---|---|---|---|
| `LLM_EXTRACTION_MODEL` | `PRISM_LLM_EXTRACTION_PRIMARY` | `config.py`, `engine.py`, `AppHost.cs`, `eval/matcher.py`, `eval/dump_fixture.py`, `main.py`, `.env.template` | **Yes** |
| `LLM_EXTRACTION_FALLBACK_MODEL` | `PRISM_LLM_EXTRACTION_FALLBACK` | `config.py`, `engine.py`, `AppHost.cs`, `.env.template` | **Yes** |
| (Currently uses Extraction Primary) | `PRISM_LLM_CLAIM_AUDIT_PRIMARY` | `config.py`, `engine.py`, `AppHost.cs`, `.env.template` | **Yes** |
| (Currently uses Extraction Fallback) | `PRISM_LLM_CLAIM_AUDIT_FALLBACK`| `config.py`, `engine.py`, `AppHost.cs`, `.env.template` | **Yes** |
| `LLM_AUDIT_PRIMARY_MODEL` | `PRISM_LLM_SPAN_GROUNDING_PRIMARY` | `config.py`, `grounding.py`, `AppHost.cs`, `.env.template` | **Yes** |
| `LLM_AUDIT_FALLBACK_MODEL`| `PRISM_LLM_SPAN_GROUNDING_FALLBACK`| `config.py`, `grounding.py`, `AppHost.cs`, `.env.template` | **Yes** |
| `LLM_AGENT_MODEL` | `PRISM_LLM_CHAT_PRIMARY` | `config.py`, `agent.py`, `agent_service.py`, `AppHost.cs`, `.env.template` | **Yes** |
| `LLM_SUMMARY_MODEL` | `PRISM_LLM_SUMMARY_PRIMARY` | `config.py`, `ai_service.py`, `AppHost.cs`, `.env.template` | **Yes** |
| `LLM_FAST_MODEL` | `PRISM_LLM_ROUTER_PRIMARY` | `config.py`, `agent.py`, `agent_service.py`, `AppHost.cs`, `.env.template` | **Yes** |
| `LLM_AUDIT_MODEL` | `PRISM_LLM_EVAL_MATCHER_PRIMARY` | `eval/matcher.py`, `eval/dump_fixture.py`, `.env.template` (remove from `AppHost.cs` & `config.py` completely) | No |
| (Currently uses Extraction model) | `PRISM_LLM_EVAL_MATCHER_FALLBACK` | `eval/matcher.py`, `.env.template` | No |

**CRITICAL DEPLOYMENT NOTE:** All renames marked "Yes" for Live update require a live `az containerapp update --set-env-vars` before the next deploy. `PrismSettings` requires these variables to be present with no defaults; if the container image deploys before the new environment variables are configured in the live infrastructure, the Python services will crash on boot with a `pydantic ValidationError`.

## Proposed `.env` Block

```env
# ==============================================================================
# LLM Model Configuration
# ==============================================================================

# ------------------------------------------------------------------------------
# EXTRACTION STAGE
# Drives the initial paper-to-claims extraction steps (Prompt 1 & 2)
# ------------------------------------------------------------------------------
PRISM_LLM_EXTRACTION_PRIMARY=gemini-3.6-flash
# [FLAG] Warning: This fallback is in the exact same tier as the primary model.
PRISM_LLM_EXTRACTION_FALLBACK=gemini-3.6-flash

# ------------------------------------------------------------------------------
# CLAIM AUDIT STAGE
# Drives the claim-level auditor and structurer (Prompt 3 & 4)
# ------------------------------------------------------------------------------
PRISM_LLM_CLAIM_AUDIT_PRIMARY=gemini-3.6-flash
# [FLAG] Warning: This fallback is in the exact same tier as the primary model.
PRISM_LLM_CLAIM_AUDIT_FALLBACK=gemini-3.6-flash

# ------------------------------------------------------------------------------
# SPAN GROUNDING STAGE
# Drives the secondary judge for validating exact quote spans
# ------------------------------------------------------------------------------
PRISM_LLM_SPAN_GROUNDING_PRIMARY=groq/openai/gpt-oss-20b
PRISM_LLM_SPAN_GROUNDING_FALLBACK=gemini/gemini-3.1-flash-lite

# ------------------------------------------------------------------------------
# CHAT STAGE
# Drives the chat responses for user queries
# ------------------------------------------------------------------------------
PRISM_LLM_CHAT_PRIMARY=gemini-3.6-flash

# ------------------------------------------------------------------------------
# SUMMARY STAGE
# Drives text summarization and audio transcription
# ------------------------------------------------------------------------------
PRISM_LLM_SUMMARY_PRIMARY=gemini-3.1-flash-lite

# ------------------------------------------------------------------------------
# ROUTER STAGE
# Drives intent routing for chat queries
# ------------------------------------------------------------------------------
PRISM_LLM_ROUTER_PRIMARY=gemini-3.1-flash-lite

# ------------------------------------------------------------------------------
# EVAL MATCHER STAGE (Eval-gated)
# Drives the LLM-as-judge in the evaluation pipeline. Never used in production.
# ------------------------------------------------------------------------------
PRISM_LLM_EVAL_MATCHER_PRIMARY=gemini-3.6-flash
# [FLAG] Warning: This fallback is in the exact same tier as the primary model.
PRISM_LLM_EVAL_MATCHER_FALLBACK=gemini-3.6-flash
```
