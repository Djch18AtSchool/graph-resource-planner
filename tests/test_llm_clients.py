"""Clientes LLM: formato de las peticiones (structured outputs), manejo de errores y puente web."""
import asyncio
import json
from types import SimpleNamespace

import anthropic
import httpx
import pytest

from ai_agent import AnthropicClient, BrowserClient, GraphSpec, LLMError, OllamaClient
from ai_agent.llm_client import (FALLBACK_BETA, anthropic_params, anthropic_text, ollama_payload, ollama_text,
                                 parse_json_object, resolve_effort)

run = asyncio.run
GOOD = {"title": "t", "nodes": [{"id": "a", "label": "A", "type": "service", "description": ""}],
        "edges": []}


def _message(text, stop="end_turn", blocks=None):
    content = blocks if blocks is not None else [{"type": "thinking", "thinking": ""}, {"type": "text", "text": text}]
    return {"content": content, "stop_reason": stop, "stop_details": None}


# ------------------------------------------------------------------- formato de Claude
def test_anthropic_params_use_structured_outputs_not_forced_tools():
    schema = GraphSpec.llm_schema()
    p = anthropic_params("sys", "usr", "claude-opus-5-5", "medium", schema)
    assert p["output_config"] == {"effort": "medium", "format": {"type": "json_schema", "schema": schema}}
    assert "tool_choice" not in p and "tools" not in p        # tool_choice forzado da 400 en modelos actuales
    assert p["betas"] == [FALLBACK_BETA] and p["fallbacks"] == "default"
    assert p["messages"] == [{"role": "user", "content": "usr"}] and p["system"] == "sys"
    text_params = anthropic_params("s", "u", "m", "low")
    assert "format" not in text_params["output_config"] and text_params["max_tokens"] < p["max_tokens"]


def test_anthropic_text_skips_thinking_blocks_and_checks_stop_reason():
    assert anthropic_text(_message('{"a": 1}')) == '{"a": 1}'
    with pytest.raises(LLMError, match="rechazo"):
        anthropic_text({"content": [], "stop_reason": "refusal", "stop_details": {"category": "cyber"}})
    with pytest.raises(LLMError, match="max_tokens"):
        anthropic_text(_message("{", stop="max_tokens"))
    with pytest.raises(LLMError, match="no devolvio texto"):
        anthropic_text(_message("", blocks=[]))


@pytest.mark.parametrize("text", ["no es json", "[1, 2]"])
def test_parse_json_object_rejects_non_objects(text):
    with pytest.raises(LLMError):
        parse_json_object(text, "X")


def test_resolve_effort(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_EFFORT", raising=False)
    assert resolve_effort(None) == "medium"
    monkeypatch.setenv("ANTHROPIC_EFFORT", "HIGH")
    assert resolve_effort(None) == "high"
    with pytest.raises(LLMError):
        resolve_effort("maximo")


# ------------------------------------------------------------------- cliente con el SDK
class FakeMessages:
    def __init__(self, result=None, error=None):
        self.result, self.error, self.kwargs = result, error, None

    async def create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(model_dump=lambda: self.result)


def _client_with(messages):
    client = AnthropicClient(api_key="sk-test", model="modelo-x", effort="low")
    client.client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return client


def test_anthropic_client_structured_and_text():
    fake = FakeMessages(_message(json.dumps(GOOD)))
    client = _client_with(fake)
    assert run(client.complete_structured("s", "u", {"type": "object"})) == GOOD
    assert fake.kwargs["model"] == "modelo-x" and fake.kwargs["output_config"]["effort"] == "low"
    fake.result = _message("## Resumen")
    assert run(client.complete_text("s", "u")) == "## Resumen"


def _status_error(cls, status):
    req = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    return cls("mensaje", response=httpx.Response(status, request=req), body=None)


@pytest.mark.parametrize("error,fragment", [
    (_status_error(anthropic.AuthenticationError, 401), "invalida"),
    (_status_error(anthropic.RateLimitError, 429), "Limite"),
    (_status_error(anthropic.BadRequestError, 400), "rechazada"),
    (_status_error(anthropic.InternalServerError, 500), "500"),
    (anthropic.APIConnectionError(request=httpx.Request("POST", "https://x")), "conectar"),
])
def test_anthropic_client_maps_sdk_errors_to_friendly_messages(error, fragment):
    with pytest.raises(LLMError, match=fragment):
        run(_client_with(FakeMessages(error=error)).complete_text("s", "u"))


def test_anthropic_client_requires_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(LLMError, match="ANTHROPIC_API_KEY"):
        AnthropicClient()


# ------------------------------------------------------------------------------ Ollama
def test_ollama_payload_and_text():
    p = ollama_payload("s", "u", "llama3.1", {"type": "object"})
    assert p["format"] == {"type": "object"} and p["stream"] is False and p["options"]["temperature"] == 0
    assert "format" not in ollama_payload("s", "u", "m")
    assert ollama_text({"message": {"content": " hola "}}) == "hola"
    with pytest.raises(LLMError):
        ollama_text({"error": "x"})


def test_ollama_client_posts_schema_as_format(monkeypatch):
    seen = {}

    def handler(request):
        seen.update(url=str(request.url), body=json.loads(request.content))
        return httpx.Response(200, json={"message": {"content": json.dumps(GOOD)}})

    real = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    out = run(OllamaClient(model="m", host="http://h:1/").complete_structured("s", "u", {"type": "object"}))
    assert out == GOOD and seen["url"] == "http://h:1/api/chat" and seen["body"]["format"] == {"type": "object"}


def test_ollama_client_wraps_http_errors(monkeypatch):
    real = httpx.AsyncClient
    transport = httpx.MockTransport(lambda request: httpx.Response(500, text="boom"))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: real(transport=transport, **kw))
    with pytest.raises(LLMError, match="Ollama"):
        run(OllamaClient(host="http://h:1").complete_text("s", "u"))


# ---------------------------------------------------------------- cliente del navegador
class FakeBridge:
    """Imita el puente JS: recibe (proveedor, payload JSON) y devuelve la respuesta en JSON."""

    def __init__(self, response=None, error=None):
        self.response, self.error, self.calls = response, error, []

    async def request(self, provider, payload_json):
        self.calls.append((provider, json.loads(payload_json)))
        if self.error:
            raise self.error
        return json.dumps(self.response)


def test_browser_client_builds_same_request_as_terminal():
    bridge = FakeBridge(_message(json.dumps(GOOD)))
    client = BrowserClient(bridge, "anthropic", model="claude-opus-5-5", effort="medium")
    assert run(client.complete_structured("s", "u", {"type": "object"})) == GOOD
    provider, payload = bridge.calls[0]
    assert provider == "anthropic"
    assert payload == anthropic_params("s", "u", "claude-opus-5-5", "medium", {"type": "object"})


def test_browser_client_ollama_and_errors():
    bridge = FakeBridge({"message": {"content": "reporte"}})
    client = BrowserClient(bridge, "ollama")
    assert client.model == "llama3.1" and run(client.complete_text("s", "u")) == "reporte"
    failing = BrowserClient(FakeBridge(error=RuntimeError("CORS")), "ollama")
    with pytest.raises(LLMError, match="CORS"):
        run(failing.complete_text("s", "u"))
    with pytest.raises(LLMError):
        BrowserClient(bridge, "offline")
