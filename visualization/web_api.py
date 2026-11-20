"""
Punto de entrada de la app web (lo invoca el Web Worker de Pyodide, ver visualization/web/worker.js).

Todas las funciones reciben y devuelven JSON (str) para que el cruce JavaScript <-> Python sea
trivial y no haya objetos proxy que liberar. Los errores esperables (entrada invalida, fallo del
LLM) se devuelven como ``{"ok": false, "error": "..."}`` con un mensaje apto para el usuario.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from ai_agent import (EXAMPLES, BrowserClient, GraphSpec, LLMClient, LLMError, OfflineClient, ReportGenerator,
                      RequirementParser)
from ai_agent.parser import MAX_INPUT_CHARS
from graph_core import ALGORITHMS
from pipeline import analyze_spec

from .view_model import build_view

MODES = ("text", "example", "json")
MAX_JSON_CHARS = 200_000
GENERIC_ERROR = "Error interno al analizar el grafo. Revise la entrada e intente de nuevo."

logger = logging.getLogger(__name__)


def metadata() -> str:
    """Datos estaticos para poblar la interfaz (ejemplos, algoritmos, limites)."""
    return json.dumps({
        "examples": [{"key": k, "title": v["title"]} for k, v in EXAMPLES.items()],
        "example_specs": EXAMPLES,
        "algorithms": sorted(ALGORITHMS),
        "max_input_chars": MAX_INPUT_CHARS,
    }, ensure_ascii=False)


def _make_client(req: Dict[str, Any], bridge: Any) -> LLMClient:
    provider = req.get("provider", "offline")
    if provider == "offline":
        return OfflineClient()
    if bridge is None:
        raise LLMError("No hay puente JavaScript para llamar al LLM")
    return BrowserClient(bridge, provider, model=req.get("model") or None, effort=req.get("effort") or None)


def _spec_from_request(req: Dict[str, Any]) -> GraphSpec:
    mode = req.get("mode")
    if mode == "example":
        key = req.get("example")
        if key not in EXAMPLES:
            raise ValueError(f"Ejemplo desconocido: {key!r}")
        return GraphSpec.model_validate(EXAMPLES[key])
    raw = str(req.get("spec_json") or "")
    if len(raw) > MAX_JSON_CHARS:
        raise ValueError(f"El JSON excede {MAX_JSON_CHARS} caracteres")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalido: {exc.msg} (linea {exc.lineno}, columna {exc.colno})") from exc
    return GraphSpec.model_validate(data)


async def _analyze(req: Dict[str, Any], bridge: Any) -> Dict[str, Any]:
    mode = req.get("mode")
    if mode not in MODES:
        raise ValueError(f"Modo desconocido: {mode!r}")
    algorithm = req.get("algorithm", "dsatur")
    if not isinstance(algorithm, str) or algorithm not in ALGORITHMS:
        raise ValueError(f"Algoritmo desconocido: {algorithm!r}")
    client = _make_client(req, bridge)

    if mode == "text":
        parsed = await RequirementParser(client).parse(str(req.get("text") or ""))
        spec, warnings, attempts = parsed.spec, list(parsed.warnings), parsed.attempts
    else:
        spec, warnings = _spec_from_request(req).sanitized()
        attempts = 0

    analysis = analyze_spec(spec, algorithm)
    warnings += _analysis_warnings(analysis.facts())
    report_text, source = None, ""
    if req.get("with_report", True):
        report = await ReportGenerator(client).generate(analysis.facts())
        report_text, source = report.text, report.source
        if report.warning:
            warnings.append(report.warning)
    return build_view(analysis, report_text, source, warnings, client.name, attempts)


def _analysis_warnings(facts: Dict[str, Any]) -> List[str]:
    unrouted = facts["planarity"]["unrouted_edges"]
    if not unrouted:
        return []
    return [f"La planarizacion alcanzo su limite de tiempo: {unrouted} arista(s) no se dibujaron."]


async def handle(request_json: str, bridge: Optional[Any] = None) -> str:
    """Analiza una solicitud de la web. ``bridge``: objeto JS con ``request(provider, payload)``."""
    try:
        req = json.loads(request_json)
        if not isinstance(req, dict):
            raise ValueError("La solicitud debe ser un objeto JSON")
        view = await _analyze(req, bridge)
    except (LLMError, ValueError) as exc:          # pydantic.ValidationError hereda de ValueError
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
    except Exception:                              # nunca mostrar un traceback al usuario
        logger.exception("Fallo inesperado en web_api.handle")
        return json.dumps({"ok": False, "error": GENERIC_ERROR}, ensure_ascii=False)
    return json.dumps({"ok": True, "view": view}, ensure_ascii=False, default=str)
