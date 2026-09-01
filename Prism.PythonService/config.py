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
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PrismSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres (memory_db.py - LangGraph checkpointer pool)
    prism_db_host: str
    prism_db_port: int = 5432
    prism_db_databasename: str
    prism_db_username: str
    prism_db_password: str

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
    llm_agent_model: str
    llm_fast_model: str
    llm_summary_model: str
    llm_extraction_model: str
    llm_audit_model: str

    # Groq audit fallback (extraction/grounding.py)
    groq_api_key: str
    audit_model: str = "groq/openai/gpt-oss-20b"
    audit_fallback_model: str = "gemini/gemini-3.1-flash-lite-preview"

    # FastAPI server port (api.py __main__ entrypoint)
    port: int = 8000

    # Nuclear system-reset endpoint guard - unset disables the endpoint (403)
    system_admin_token: str | None = None


settings = PrismSettings()
