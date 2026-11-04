"""Which backend the google-genai client talks to: AI Studio (API key) or Vertex AI (ADC).

The product always runs on AI Studio. Only the eval scripts (eval/replay_audit.py,
eval/probe_cache_schema.py) switch to Vertex, through eval/backend_options.py, by calling
set_backend() before the first request. Nothing here reads GOOGLE_GENAI_USE_VERTEXAI,
GOOGLE_CLOUD_PROJECT or GOOGLE_CLOUD_LOCATION: the AI Studio path passes vertexai=False
explicitly, so those variables can never switch it, and the Vertex path takes its project
and location from the caller.

extraction/engine.py::_build_client is the only place a genai.Client is built; every call
kind (auditor, structurer, scope lister/checker, cache create/use/delete) gets its client
from there.
"""
from dataclasses import dataclass

from google import genai

BACKEND_AISTUDIO = "aistudio"
BACKEND_VERTEX = "vertex"
DEFAULT_VERTEX_LOCATION = "global"


class BackendConfigError(ValueError):
    """The backend settings cannot build a client (raised before any request)."""


@dataclass(frozen=True)
class Backend:
    name: str = BACKEND_AISTUDIO
    project: str | None = None
    location: str | None = None


AISTUDIO = Backend()

# Indirection so tests can stand in for the SDK constructor (tests/conftest.py makes
# the default one refuse to build anything).
_client_factory = genai.Client
_active: Backend = AISTUDIO


def validate_backend(backend: Backend) -> None:
    if backend.name == BACKEND_AISTUDIO:
        if backend.project:
            raise BackendConfigError("--vertex-project is only valid with --backend vertex")
        return
    if backend.name != BACKEND_VERTEX:
        raise BackendConfigError(f"unknown backend {backend.name!r}")
    if not backend.project:
        raise BackendConfigError("--backend vertex requires --vertex-project (no default project)")
    if not backend.location:
        raise BackendConfigError("--backend vertex requires a location (--vertex-location)")


def set_backend(backend: Backend) -> Backend:
    """Makes `backend` the active one and returns the previous one (for restoring)."""
    global _active
    validate_backend(backend)
    previous, _active = _active, backend
    return previous


def get_backend() -> Backend:
    return _active


def build_genai_client(api_key: str):
    """The client for the active backend. AI Studio: the API key, vertexai=False.
    Vertex: vertexai=True with the active project and location; credentials come from
    Application Default Credentials and no API key is passed."""
    backend = _active
    validate_backend(backend)
    if backend.name == BACKEND_VERTEX:
        return _client_factory(vertexai=True, project=backend.project, location=backend.location)
    return _client_factory(api_key=api_key, vertexai=False)
