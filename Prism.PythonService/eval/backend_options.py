"""Eval-only backend options shared by eval/replay_audit.py and eval/probe_cache_schema.py:
--backend {aistudio,vertex}, --vertex-project, --vertex-location; the LiteLLM router that
sends the grounding calls' Gemini routes to Vertex; the pre-request checks; and the
run_config block recorded in a run's summary.

Default (--backend aistudio) changes nothing: no router is installed, no field is added to
any output, and the genai client is built with vertexai=False (extraction/llm_backend.py).
No product entry point imports this module.

Under --backend vertex EVERY Gemini call goes to Vertex: genai clients come from
llm_backend (vertexai=True), and the LiteLLM grounding call's Gemini routes are rewritten
to vertex_ai/<model> with vertex_project / vertex_location and no api_key. A non-Google
provider route (groq/..., openai/...) passes through unchanged: it is not a Gemini call.
A Gemini route that cannot be rewritten raises BackendRoutingError before the request.
"""
import contextlib
import importlib.metadata
import re

import litellm

from eval import pricing
from extraction import llm_backend
from extraction.llm_backend import (
    BACKEND_AISTUDIO,
    BACKEND_VERTEX,
    DEFAULT_VERTEX_LOCATION,
    Backend,
    BackendConfigError,
)

# Thinking levels a model rejects with HTTP 400 (checked before any request).
UNSUPPORTED_THINKING_LEVELS: dict[str, frozenset[str]] = {
    "gemini-3.8-flash": frozenset({"minimal"}),
}


class BackendRoutingError(BaseException):
    """A Gemini route that cannot be sent to the active backend.

    A BaseException on purpose, like eval.replay_audit.CapExceeded: grounding's span audit
    catches Exception and turns it into a SKIPPED span, which would hide the failure.
    """


def add_backend_args(parser) -> None:
    parser.add_argument(
        "--backend", choices=[BACKEND_AISTUDIO, BACKEND_VERTEX], default=BACKEND_AISTUDIO,
        help="where every Gemini call goes (default aistudio: the API key). vertex uses Application Default "
             "Credentials and needs --vertex-project",
    )
    parser.add_argument(
        "--vertex-project", default=None,
        help="Google Cloud project id; required with --backend vertex (no default), rejected with aistudio",
    )
    parser.add_argument(
        "--vertex-location", default=DEFAULT_VERTEX_LOCATION,
        help=f"Vertex location (default {DEFAULT_VERTEX_LOCATION})",
    )


def backend_from_args(args) -> Backend:
    """The Backend the args ask for. Missing attributes mean the default (AI Studio), so
    an args namespace built before these options existed still works. Raises
    BackendConfigError for a bad combination."""
    name = getattr(args, "backend", BACKEND_AISTUDIO)
    project = getattr(args, "vertex_project", None)
    if name == BACKEND_VERTEX:
        backend = Backend(BACKEND_VERTEX, project, getattr(args, "vertex_location", DEFAULT_VERTEX_LOCATION))
    else:
        backend = Backend(name, project)
    llm_backend.validate_backend(backend)
    return backend


@contextlib.contextmanager
def active_backend(backend: Backend):
    """Makes `backend` the one every client is built for, and restores the previous one."""
    previous = llm_backend.set_backend(backend)
    try:
        yield backend
    finally:
        llm_backend.set_backend(previous)


def _is_gemini_route(model: object) -> bool:
    if not isinstance(model, str):
        return False
    return model.startswith(("gemini/", "vertex_ai/", "vertex_ai_beta/")) or model.lower().startswith("gemini")


def _vertex_model(model: str) -> str:
    if model.startswith("vertex_ai/"):
        name = model[len("vertex_ai/"):]
    elif model.startswith("vertex_ai_beta/"):
        name = model[len("vertex_ai_beta/"):]
    elif model.startswith("gemini/"):
        name = model[len("gemini/"):]
    else:
        name = model
    if not name or "/" in name:
        raise BackendRoutingError(f"cannot route Gemini model {model!r} to Vertex: no model name to rewrite")
    return f"vertex_ai/{name}"


def _route_one(backend: Backend, entry: dict) -> dict:
    """One completion kwargs / fallback entry. A Gemini route is rewritten to Vertex; any
    other provider's entry is returned as it is."""
    model = entry.get("model")
    if not isinstance(model, str):
        raise BackendRoutingError(f"cannot route a LiteLLM call without a model string (got {model!r})")
    if not _is_gemini_route(model):
        return entry
    routed = {k: v for k, v in entry.items() if k != "api_key"}
    routed["model"] = _vertex_model(model)
    routed["vertex_project"] = backend.project
    routed["vertex_location"] = backend.location
    return routed


def route_completion_kwargs(backend: Backend, kwargs: dict) -> dict:
    """LiteLLM acompletion kwargs for `backend`. AI Studio: returned untouched. Vertex: the
    model and every fallbacks entry are routed with _route_one."""
    if backend.name != BACKEND_VERTEX:
        return kwargs
    routed = _route_one(backend, kwargs)
    fallbacks = routed.get("fallbacks")
    if fallbacks is not None:
        if not isinstance(fallbacks, (list, tuple)):
            raise BackendRoutingError(f"cannot route LiteLLM fallbacks of type {type(fallbacks).__name__}")
        routed["fallbacks"] = [
            _route_one(backend, entry) if isinstance(entry, dict) else _unroutable_fallback(entry)
            for entry in fallbacks
        ]
    return routed


def _unroutable_fallback(entry: object):
    raise BackendRoutingError(f"cannot route LiteLLM fallbacks entry {entry!r}: expected a dict with a model")


@contextlib.contextmanager
def routed_litellm(backend: Backend):
    """For the duration of the block, litellm.acompletion routes Gemini models to Vertex.
    A no-op under AI Studio (nothing is installed, so the request is unchanged)."""
    if backend.name != BACKEND_VERTEX:
        yield
        return
    original = litellm.acompletion

    async def routed(*args, **kwargs):
        if args:
            raise BackendRoutingError("cannot route a positional LiteLLM acompletion call to Vertex")
        return await original(**route_completion_kwargs(backend, kwargs))

    litellm.acompletion = routed
    try:
        yield
    finally:
        litellm.acompletion = original


def check_grounding_routes(backend: Backend, primary: str, fallback: str) -> None:
    """Runs the router on the configured grounding models, so a Gemini route that cannot be
    sent to Vertex fails before any request. A groq/ primary is accepted."""
    route_completion_kwargs(backend, {"model": primary, "fallbacks": [{"model": fallback, "api_key": "x"}]})


def validate_thinking(model: str, level: str | None) -> None:
    """ValueError for a thinking level the model rejects (gemini-3.8-flash: "minimal" is HTTP 400)."""
    if level is None:
        return
    rejected = UNSUPPORTED_THINKING_LEVELS.get(pricing.normalise_model_name(model), frozenset())
    if level.lower() in rejected:
        raise ValueError(
            f"thinking level {level!r} is rejected by {model} (HTTP 400); use one of "
            f"{sorted({'low', 'medium', 'high'})}. No request was made"
        )


def is_google_model(model: str) -> bool:
    return pricing.normalise_model_name(model).startswith("gemini")


def require_priced(models: dict[str, str]) -> None:
    """Every Google model the run can call must have a price (UnpricedModelError names the
    role and the model). Non-Google providers (groq/...) are exempt: their usage keeps the
    existing 'unpriced' handling."""
    for role, model in models.items():
        if not is_google_model(model):
            continue
        try:
            pricing.rates_for_model(model)
        except pricing.UnpricedModelError as exc:
            raise pricing.UnpricedModelError(f"{role}: {exc}") from exc


def library_versions() -> dict[str, str | None]:
    out: dict[str, str | None] = {}
    for key, dist in (("google_genai_version", "google-genai"), ("litellm_version", "litellm")):
        try:
            out[key] = importlib.metadata.version(dist)
        except importlib.metadata.PackageNotFoundError:
            out[key] = None
    return out


def run_config(
    backend: Backend, auditor_model: str, other_models: dict[str, str], thinking_level: str | None,
) -> dict:
    """The block recorded in a summary / printed by the probe (R7)."""
    return {
        "backend": backend.name,
        "project": backend.project,
        "location": backend.location,
        "auditor_model": auditor_model,
        "other_models": dict(other_models),
        "thinking_level": thinking_level,
        **library_versions(),
    }


def output_slug(auditor_model: str | None, backend: Backend, default_model: str) -> str:
    """Folder-name part for a run with a non-default option, so it never lands in the
    baseline exp1_{level}_{n} folders."""
    model = pricing.normalise_model_name(auditor_model or default_model)
    slug = re.sub(r"[^a-z0-9.]+", "-", model).strip("-")
    return f"{slug}-vertex" if backend.name == BACKEND_VERTEX else slug


__all__ = [
    "BackendConfigError", "BackendRoutingError", "UNSUPPORTED_THINKING_LEVELS", "active_backend", "add_backend_args",
    "backend_from_args", "check_grounding_routes", "is_google_model", "library_versions", "output_slug",
    "require_priced", "route_completion_kwargs", "routed_litellm", "run_config", "validate_thinking",
]
