"""
Lenguaje natural -> GraphSpec (JSON validado).

Flujo:
    texto --(prompt + esquema)--> LLM --> dict --(Pydantic)--> GraphSpec --(sanitized)--> limpio

Si la validacion falla (JSON mal formado, aristas a nodos inexistentes, ids duplicados...) el error
se devuelve al modelo y se reintenta hasta ``max_retries`` veces: asi el LLM se autocorrige y el
resto del sistema solo ve datos validos.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from pydantic import ValidationError

from .llm_client import LLMClient, LLMError, LLMOutputError
from .prompts import RETRY_SUFFIX, SYSTEM_PARSER, USER_PARSER_TEMPLATE
from .schemas import GraphSpec

MAX_INPUT_CHARS = 6000


@dataclass
class ParseResult:
    spec: GraphSpec
    warnings: List[str] = field(default_factory=list)
    attempts: int = 1
    raw: Optional[Dict[str, Any]] = None
    provider: str = ""


class RequirementParser:
    def __init__(self, client: LLMClient, max_retries: int = 2) -> None:
        self.client = client
        self.max_retries = max_retries
        self._schema = GraphSpec.llm_schema()

    async def parse(self, text: str) -> ParseResult:
        text = (text or "").strip()
        if not text:
            raise ValueError("El requerimiento esta vacio")
        if len(text) > MAX_INPUT_CHARS:
            raise ValueError(f"El requerimiento excede {MAX_INPUT_CHARS} caracteres")

        base_user = USER_PARSER_TEMPLATE.format(text=text)
        user = base_user
        last_error = ""
        for attempt in range(1, self.max_retries + 2):
            try:
                raw = await self.client.complete_structured(SYSTEM_PARSER, user, self._schema)
                spec = GraphSpec.model_validate(raw)
            except LLMOutputError as exc:                 # JSON mal formado: reintentar
                last_error = str(exc)
                user = base_user + RETRY_SUFFIX.format(error=last_error)
                continue
            except ValidationError as exc:               # JSON valido que no cumple el contrato
                last_error = _short_error(exc)
                user = base_user + RETRY_SUFFIX.format(error=last_error)
                continue
            spec, warnings = spec.sanitized()
            return ParseResult(spec=spec, warnings=warnings, attempts=attempt, raw=raw,
                               provider=self.client.name)
        raise LLMError(f"El LLM no produjo un JSON valido tras {self.max_retries + 1} intentos: {last_error}")


def _short_error(exc: ValidationError, limit: int = 800) -> str:
    msgs = [f"- {'.'.join(str(p) for p in e['loc']) or 'raiz'}: {e['msg']}" for e in exc.errors()]
    return "\n".join(msgs)[:limit]
