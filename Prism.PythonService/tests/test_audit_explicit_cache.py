"""Unit tests for the audit_explicit_cache setting (docs/decisions.md, "Explicit audit
caching moves into the app (audit_explicit_cache, default on) - 2026-11-23").

The underlying context_cache=True/False behavior of extract_claims is already covered by
tests/test_context_cache.py (named in docs/PRISM_REPORT.md's Phase 2 report); this file only
covers the new setting itself and its wiring into the one production caller (main.py).

No network, no LLM calls - no fake client is even needed for these two tests.
"""
import pathlib

from config import PrismSettings

MAIN_PY = pathlib.Path(__file__).resolve().parent.parent / "main.py"


def test_audit_explicit_cache_defaults_to_true():
    assert PrismSettings.model_fields["audit_explicit_cache"].default is True


def test_main_py_passes_the_setting_to_extract_claims():
    """main.py is the sole production caller of extract_claims (confirmed by a repo-wide grep
    for "extract_claims(" - every other hit is a test or the definition itself). main() is one
    large monolithic async function wrapping live RabbitMQ/blob/PDF-extraction calls, so it
    cannot be invoked as a unit without mocking that whole pipeline, and refactoring it to be
    unit-testable is out of scope here. This checks the wiring the same way
    test_context_cache_module_is_the_only_sdk_cache_caller (tests/test_context_cache.py) checks
    its own invariant: by reading the source text directly. Since the call site is a direct
    passthrough with no branching, this one assertion covers both settings.audit_explicit_cache
    being False (-> context_cache=False) and True (-> context_cache=True)."""
    source = MAIN_PY.read_text(encoding="utf-8")
    assert "context_cache=settings.audit_explicit_cache" in source
