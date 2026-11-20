"""
Cliente LLM para la version web (Python corriendo en el navegador con Pyodide/WebAssembly).

Python construye la peticion EXACTAMENTE igual que en la terminal (``anthropic_params`` /
``ollama_payload``) y la entrega a un *puente* de JavaScript que solo hace el transporte:

    * anthropic -> SDK oficial ``@anthropic-ai/sdk`` (``client.beta.messages.create``)
    * ollama    -> ``fetch`` a ``{host}/api/chat``

El puente expone ``request(provider, payload_json) -> Promise<str>`` (respuesta JSON). En Pyodide
``await`` sobre una promesa de JS funciona de forma nativa, por eso la capa ai_agent es asincrona.
La API key la guarda el puente en el navegador del usuario; nunca pasa por Python ni por el repo.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional, Protocol

from .llm_client import (DEFAULT_ANTHROPIC_MODEL, DEFAULT_OLLAMA_MODEL, LLMClient, LLMError, anthropic_params,
                         anthropic_text, ollama_payload, ollama_text, parse_json_object, resolve_effort)

BROWSER_PROVIDERS = ("anthropic", "ollama")


class JsBridge(Protocol):
    async def request(self, provider: str, payload_json: str) -> str: ...


class BrowserClient(LLMClient):
    def __init__(self, bridge: JsBridge, provider: str, model: Optional[str] = None,
                 effort: Optional[str] = None) -> None:
        if provider not in BROWSER_PROVIDERS:
            raise LLMError(f"Proveedor no disponible en la web: {provider!r}")
        self.bridge = bridge
        self.name = provider
        self.effort = resolve_effort(effort)
        default = DEFAULT_ANTHROPIC_MODEL if provider == "anthropic" else DEFAULT_OLLAMA_MODEL
        self.model = model or default

    async def _send(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        try:
            raw = await self.bridge.request(self.name, json.dumps(payload))
        except Exception as exc:                     # JsException solo existe dentro de Pyodide
            raise LLMError(f"Error al llamar a {self.name} desde el navegador: {exc}") from exc
        return parse_json_object(str(raw), self.name)

    def _payload(self, system: str, user: str, schema: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if self.name == "anthropic":
            return anthropic_params(system, user, self.model, self.effort, schema)
        return ollama_payload(system, user, self.model, schema)

    def _text(self, response: Dict[str, Any]) -> str:
        return anthropic_text(response) if self.name == "anthropic" else ollama_text(response)

    async def complete_structured(self, system, user, schema):
        resp = await self._send(self._payload(system, user, schema))
        return parse_json_object(self._text(resp), self.name)

    async def complete_text(self, system, user):
        return self._text(await self._send(self._payload(system, user, None)))
