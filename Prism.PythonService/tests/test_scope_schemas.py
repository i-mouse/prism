"""The scope schemas: field order, no additionalProperties:false, and google-genai's
own schema conversion (the transform generate_content applies to response_schema)."""
import json
import typing

from google import genai

from extraction import scope_schemas
from extraction.scope_schemas import ScopeCheckItem, ScopeCheckResponse, ScopeItem, ScopeListResponse


def test_field_order_and_literals():
    assert list(ScopeItem.model_fields) == ["text", "kind"]
    assert list(ScopeListResponse.model_fields) == ["items"]
    assert list(ScopeCheckItem.model_fields) == ["item", "reported", "status", "contradicting_quote"]
    assert list(ScopeCheckResponse.model_fields) == ["items"]
    assert typing.get_args(ScopeItem.model_fields["kind"].annotation) == (
        "count", "quantifier", "named_set", "plural", "pair",
    )
    assert typing.get_args(ScopeCheckItem.model_fields["status"].annotation) == (
        "matches", "contradicted", "not_reported",
    )


def test_no_schema_forbids_extra_properties():
    for model in (ScopeListResponse, ScopeCheckResponse):
        schema_text = json.dumps(model.model_json_schema())
        assert '"additionalProperties": false' not in schema_text
        assert "additionalProperties" not in schema_text


def test_no_extra_forbid_config_on_any_scope_model():
    for model in (ScopeItem, ScopeListResponse, ScopeCheckItem, ScopeCheckResponse):
        assert model.model_config.get("extra") != "forbid"
    assert not hasattr(scope_schemas, "ConfigDict")


def _genai_schema(model):
    """google-genai's own conversion of a pydantic response_schema, with a real
    (offline: constructing a Client sends nothing) Gemini-API client so its
    Gemini-API-only checks run. No request is made."""
    from google.genai import _transformers

    client = genai.Client(api_key="offline-test-key")
    return _transformers.t_schema(client._api_client, model)


def test_google_genai_converts_the_list_schema():
    schema = _genai_schema(ScopeListResponse)
    item_schema = schema.properties["items"].items
    assert set(item_schema.properties) == {"text", "kind"}
    assert item_schema.properties["kind"].enum == ["count", "quantifier", "named_set", "plural", "pair"]


def test_google_genai_converts_the_check_schema_including_the_nullable_quote():
    schema = _genai_schema(ScopeCheckResponse)
    item_schema = schema.properties["items"].items
    assert list(item_schema.properties) == ["item", "reported", "status", "contradicting_quote"]
    assert item_schema.properties["contradicting_quote"].nullable is True
    assert item_schema.properties["status"].enum == ["matches", "contradicted", "not_reported"]
    assert item_schema.properties["reported"].items.type.value == "STRING"
