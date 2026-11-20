"""
Capa de acceso al LLM. Interfaz minima ASINCRONA (para que el mismo codigo corra en la terminal
y en el navegador, donde las llamadas de red son promesas de JavaScript) con implementaciones
intercambiables:

    AnthropicClient  Claude con el SDK oficial (``anthropic.AsyncAnthropic``).
                     Structured output = ``output_config.format`` (JSON Schema estricto): la API
                     garantiza que la respuesta es un JSON que cumple el esquema.
    OllamaClient     Modelo local (API REST de Ollama). Structured output = parametro ``format``.
    OfflineClient    Sin red ni API key: devuelve especificaciones de ejemplo (demos y pruebas).
    BrowserClient    (ai_agent/browser_client.py) el mismo protocolo, transportado por JavaScript.

El FORMATO de las peticiones y respuestas (``anthropic_params``, ``anthropic_text``,
``ollama_payload``, ``ollama_text``) esta aqui una sola vez y lo comparten la terminal y la web.

Configuracion por variables de entorno (ver .env.example):
    LLM_PROVIDER       anthropic | ollama | offline   (por defecto: anthropic si hay API key, si no offline)
    ANTHROPIC_API_KEY  clave de la API (NUNCA subirla al repositorio)
    ANTHROPIC_MODEL    por defecto claude-opus-5-5
    ANTHROPIC_EFFORT   low | medium | high (por defecto medium)
    OLLAMA_HOST        por defecto http://localhost:11434
    OLLAMA_MODEL       por defecto llama3.1
"""
from __future__ import annotations

import copy
import json
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from .offline_examples import pick_example

DEFAULT_ANTHROPIC_MODEL = "claude-opus-5-5"
DEFAULT_EFFORT = "medium"
DEFAULT_OLLAMA_MODEL = "llama3.1"
DEFAULT_OLLAMA_HOST = "http://localhost:11434"
STRUCTURED_MAX_TOKENS = 16000
TEXT_MAX_TOKENS = 4000
# Si un clasificador de seguridad rechaza la peticion, la API la reintenta con otro modelo.
FALLBACK_BETA = "server-side-fallback-2026-07-01"
EFFORTS = ("low", "medium", "high")
PROVIDERS = ("anthropic", "ollama", "offline")


class LLMError(RuntimeError):
    """Fallo al invocar el LLM o al interpretar su respuesta (mensaje apto para el usuario)."""


class LLMOutputError(LLMError):
    """El LLM respondio, pero con un contenido mal formado: vale la pena reintentar."""


class LLMClient(ABC):
    name: str = "base"
    is_offline: bool = False

    @abstractmethod
    async def complete_structured(self, system: str, user: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Devuelve un objeto JSON (dict) que sigue ``schema``."""

    @abstractmethod
    async def complete_text(self, system: str, user: str) -> str:
        """Devuelve texto libre (reporte)."""


# =============================================================================== Claude
def anthropic_params(system: str, user: str, model: str, effort: str,
                     schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Cuerpo de ``beta.messages.create`` (identico en Python y en el SDK de JavaScript)."""
    output_config: Dict[str, Any] = {"effort": effort}
    if schema is not None:
        output_config["format"] = {"type": "json_schema", "schema": schema}
    return {
        "model": model,
        "max_tokens": STRUCTURED_MAX_TOKENS if schema is not None else TEXT_MAX_TOKENS,
        "system": system,
        "messages": [{"role": "user", "content": user}],
        "output_config": output_config,
        "betas": [FALLBACK_BETA],
        "fallbacks": "default",
    }


def anthropic_text(response: Dict[str, Any]) -> str:
    """Extrae el texto de una respuesta de Messages (dict) validando ``stop_reason``."""
    stop = response.get("stop_reason")
    if stop == "refusal":
        details = response.get("stop_details") or {}
        raise LLMError(f"Claude rechazo la solicitud (categoria: {details.get('category') or 'n/d'})")
    if stop == "max_tokens":
        raise LLMError("La respuesta de Claude se corto por max_tokens; simplifique el requerimiento")
    text = "".join(b.get("text", "") for b in response.get("content", []) if b.get("type") == "text").strip()
    if not text:
        raise LLMError("Claude no devolvio texto")
    return text


def parse_json_object(text: str, source: str) -> Dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMOutputError(f"{source} devolvio JSON invalido: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMOutputError(f"{source} devolvio un JSON que no es un objeto")
    return data


def resolve_effort(effort: Optional[str]) -> str:
    value = (effort or os.getenv("ANTHROPIC_EFFORT") or DEFAULT_EFFORT).lower()
    if value not in EFFORTS:
        raise LLMError(f"Esfuerzo invalido: {value!r} (opciones: {', '.join(EFFORTS)})")
    return value


class AnthropicClient(LLMClient):
    name = "anthropic"

    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None,
                 effort: Optional[str] = None, timeout: float = 120.0) -> None:
        import anthropic

        key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise LLMError("Falta ANTHROPIC_API_KEY (defina la variable de entorno o use --provider offline)")
        self._anthropic = anthropic
        self.client = anthropic.AsyncAnthropic(api_key=key, timeout=timeout, max_retries=2)
        self.model = model or os.getenv("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
        self.effort = resolve_effort(effort)

    async def _create(self, params: Dict[str, Any]) -> Dict[str, Any]:
        a = self._anthropic
        try:
            msg = await self.client.beta.messages.create(**params)
        except a.AuthenticationError as exc:
            raise LLMError("API key de Anthropic invalida") from exc
        except a.RateLimitError as exc:
            raise LLMError("Limite de uso de la API alcanzado; intente en unos segundos") from exc
        except a.BadRequestError as exc:
            raise LLMError(f"Solicitud rechazada por la API: {exc.message}") from exc
        except a.APIStatusError as exc:
            raise LLMError(f"Error de la API de Anthropic ({exc.status_code}): {exc.message}") from exc
        except a.APIConnectionError as exc:
            raise LLMError("No se pudo conectar con la API de Anthropic (revise la red)") from exc
        return msg.model_dump()

    async def complete_structured(self, system, user, schema):
        resp = await self._create(anthropic_params(system, user, self.model, self.effort, schema))
        return parse_json_object(anthropic_text(resp), "Claude")

    async def complete_text(self, system, user):
        return anthropic_text(await self._create(anthropic_params(system, user, self.model, self.effort)))


# =============================================================================== Ollama
def ollama_payload(system: str, user: str, model: str, schema: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model, "stream": False, "options": {"temperature": 0},
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }
    if schema is not None:
        payload["format"] = schema
    return payload


def ollama_text(response: Dict[str, Any]) -> str:
    try:
        return str(response["message"]["content"]).strip()
    except (KeyError, TypeError) as exc:
        raise LLMError("Respuesta de Ollama sin 'message.content'") from exc


class OllamaClient(LLMClient):
    name = "ollama"

    def __init__(self, model: Optional[str] = None, host: Optional[str] = None, timeout: float = 300.0) -> None:
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
        self.host = (host or os.getenv("OLLAMA_HOST", DEFAULT_OLLAMA_HOST)).rstrip("/")
        self.timeout = timeout

    async def _chat(self, payload: Dict[str, Any]) -> str:
        import httpx

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as http:
                r = await http.post(f"{self.host}/api/chat", json=payload)
                r.raise_for_status()
                return ollama_text(r.json())
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMError(f"Error al consultar Ollama en {self.host}: {exc}") from exc

    async def complete_structured(self, system, user, schema):
        return parse_json_object(await self._chat(ollama_payload(system, user, self.model, schema)), "Ollama")

    async def complete_text(self, system, user):
        return await self._chat(ollama_payload(system, user, self.model))


# ============================================================================== Offline
class OfflineClient(LLMClient):
    """Sin LLM: elige un ejemplo segun palabras clave. El reporte lo genera la plantilla determinista."""
    name = "offline"
    is_offline = True

    async def complete_structured(self, system, user, schema):
        return copy.deepcopy(pick_example(user))

    async def complete_text(self, system, user):
        raise LLMError("El cliente offline no genera texto; use la plantilla (reporter.template_report)")


# ============================================================================== fabrica
def get_client(provider: Optional[str] = None, **kwargs: Any) -> LLMClient:
    """Crea el cliente segun ``provider`` o la variable LLM_PROVIDER (ver docstring del modulo)."""
    provider = (provider or os.getenv("LLM_PROVIDER") or
                ("anthropic" if os.getenv("ANTHROPIC_API_KEY") else "offline")).lower()
    if provider == "anthropic":
        return AnthropicClient(**kwargs)
    if provider == "ollama":
        return OllamaClient(**kwargs)
    if provider == "offline":
        return OfflineClient()
    raise LLMError(f"Proveedor desconocido: {provider!r} ({' | '.join(PROVIDERS)})")
