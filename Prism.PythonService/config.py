"""Typed, validated environment configuration for the Python service.

Imported once at module load - pydantic-settings raises a ValidationError
immediately if any required variable is missing, so the process fails fast
at container startup instead of crashing deep inside a request handler
(os.environ["X"] -> KeyError) or silently limping along with model=None
(os.getenv("X") with no default).

Field names match env vars case-insensitively by default (PRISM_DB_HOST ->
prism_db_host); the two Aspire-style connection strings use an explicit
validation_alias because their names ("ConnectionStrings__messaging") don't
map onto a Python identifier.
"""
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AUDITOR_THINKING_LEVELS = {"low", "medium", "high"}
# Separate from AUDITOR_THINKING_LEVELS: the installed google-genai SDK's
# ThinkingLevel enum also has MINIMAL (see docs/decisions.md, "Experiment 3
# amendment 1 - 2026-10-15"), which AUDITOR_THINKING_LEVELS does not accept.
# Kept as its own set since MINIMAL's support by gemini-3.6-flash is
# unverified - accepting it here is a config-validation choice, not a claim
# that the API honors it.
PASS2_THINKING_LEVELS = {"minimal", "low", "medium", "high"}


class PrismSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres (memory_db.py - LangGraph checkpointer pool). Locally the RunAsContainer
    # Postgres uses password auth, so both are set. The deployed Azure Postgres Flexible
    # Server is Entra-only (passwordAuth: Disabled) - no password exists to inject, so
    # both are optional here and memory_db.py falls back to a Managed Identity token
    # (DefaultAzureCredential) as the password when prism_db_password is unset.
    prism_db_host: str
    prism_db_port: int = 5432
    prism_db_databasename: str
    prism_db_username: str | None = None
    prism_db_password: str | None = None

    # RabbitMQ / Blob Storage - Aspire injects these as connection strings (main.py).
    # "messaging" is the RabbitMQ resource. "blobs" is the blob *service*-level resource
    # (AddBlobs, not AddBlobContainer) - the container-scoped "uploads" resource's
    # connection string carries a ";ContainerName=..." suffix meant only for Aspire's own
    # .NET client integrations to parse; the raw Python SDK chokes on it (confirmed via a
    # live F5 run - "Connection string is either blank or malformed."). Python targets the
    # "prism-uploads" container by literal string at the call site instead - see main.py.
    messaging_connection_string: str = Field(validation_alias="ConnectionStrings__messaging")
    storage_connection_string: str = Field(validation_alias="ConnectionStrings__blobs")

    # LLM (Gemini)
    ai_api_key: str
    llm_chat_model: str
    llm_router_model: str
    llm_summary_model: str
    llm_extraction_model: str

    # Groq span-grounding (extraction/grounding.py)
    groq_api_key: str
    llm_grounding_model: str
    llm_grounding_fallback_model: str
    # Stage-1 RapidFuzz text normalisation (extraction/grounding.py normalize_for_match).
    grounding_normalize: bool = True

    # Extraction (Prompt 1 metadata + Prompt 2 extractor, extraction/engine.py)
    llm_extraction_fallback_model: str

    # Claim audit (Prompt 3 auditor + Prompt 4 structurer, extraction/engine.py) -
    # separate from the extraction pair above so the two workloads don't share a knob.
    llm_claim_audit_model: str
    llm_claim_audit_fallback_model: str

    # Experiment 1 - auditor thinking level override for the live service. Unset
    # means no thinking_config is sent (today's behavior, API default medium on
    # 3.6-flash). Auditor call only - every other Gemini call is untouched. The
    # eval replay script (eval/replay_audit.py) does not read this setting; it
    # passes thinking_level explicitly per call instead.
    auditor_thinking_level: str | None = None

    @field_validator("auditor_thinking_level")
    @classmethod
    def _validate_auditor_thinking_level(cls, value: str | None) -> str | None:
        if value is not None and value not in AUDITOR_THINKING_LEVELS:
            raise ValueError(
                f"auditor_thinking_level must be one of {sorted(AUDITOR_THINKING_LEVELS)} or unset, got {value!r}"
            )
        return value

    # Experiment 2 - extractor few-shot "note" field fix. Off (default) keeps today's
    # behavior: any claims few-shot example with a top-level "note" field renders as a
    # negative ("no claims") example even when it has real claims. On, a "note" field
    # alone no longer suppresses claims - only example_type == "negative_do_not_extract"
    # or a genuinely empty output does. Extractor rendering only; see
    # extraction/prompt_loader.py::_is_negative_example and
    # extraction/prompt_version.py::get_prompt_version.
    extractor_fewshot_fix: bool = False

    # Experiment 2 (redesigned) - extractor few-shot claim-shape examples. Off
    # (default) renders only the base 11 claims examples. On, appends 8 more
    # examples (prompts/extract_claims_fewshot_shapes.json, teaching the E1/E2/
    # E3/E5 claim shapes the base 11 do not cover) after the base 11, and
    # appends a system-prompt addendum (prompts/extract_claims_system_shapes.md).
    # Extractor rendering only; see extraction/prompt_loader.py::
    # build_gemini_messages_for_extractor and extraction/prompt_version.py::
    # get_prompt_version. Independent of extractor_fewshot_fix - both default
    # off; both flags on together is Experiment 2 (redesigned)'s treatment arm,
    # extractor_fewshot_fix alone (this flag off) is its control arm.
    extractor_fewshot_shapes: bool = False

    # Experiment 3 - pass-2 windowed "copy-only" extractor calls, merged into
    # the pass-1 claim list before the (unchanged) audit/structure calls. Off
    # (default) is byte-identical to today: extract_claims runs pass 1 only,
    # and get_prompt_version()'s output is unaffected. See
    # extraction/windowing.py, extraction/pass2.py, extraction/merge.py,
    # extraction/engine.py::extract_claims, and extraction/prompt_version.py::
    # get_prompt_version.
    extractor_second_pass: bool = False

    # Experiment 3 amendment 1 - pass-2 thinking_level override, applied to
    # the primary model only (the fallback call, if one ever fires, sends no
    # thinking_config - see extraction/engine.py::_call_gemini_structured).
    # Unset (default) means no thinking_config is sent for pass-2 calls -
    # byte-identical to today (API default, medium on 3.6-flash). Mirrors
    # auditor_thinking_level's convention; see docs/decisions.md, "Experiment
    # 3 amendment 1 - 2026-10-15".
    pass2_thinking_level: str | None = None

    @field_validator("pass2_thinking_level")
    @classmethod
    def _validate_pass2_thinking_level(cls, value: str | None) -> str | None:
        if value is not None and value not in PASS2_THINKING_LEVELS:
            raise ValueError(
                f"pass2_thinking_level must be one of {sorted(PASS2_THINKING_LEVELS)} or unset, got {value!r}"
            )
        return value

    # FastAPI server port (api.py __main__ entrypoint)
    port: int = 8000

    # Mock mode
    prism_mock_extraction: bool = False
    prism_mock_stage_delay_sec: int = 0

    # Nuclear system-reset endpoint guard - unset disables the endpoint (403)
    system_admin_token: str | None = None


settings = PrismSettings()
