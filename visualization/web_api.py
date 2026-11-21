"""
API que el Web Worker invoca dentro de Pyodide. Entrada y salida son cadenas JSON.

    metadata()            -> {"examples": [...], "algorithms": [...], "limits": {...}}
    handle(request_json)  -> {"ok": true, "view": {...}} | {"ok": false, "error": "mensaje"}

Peticiones:
    {"mode": "text",   "text": "...",                 "algorithm": "dsatur"}
    {"mode": "random", "n": 100, "p": 0.05, "seed": 1, "algorithm": "welsh_powell"}
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from graph_core import ALGORITHMS, ProblemError, parse_problem, plan
from graph_core.generators import random_problem
from graph_core.problem import MAX_TASKS, MAX_TEXT_CHARS
from graph_core.scheduling import MAX_CONFLICTS

from .examples import load_examples
from .view_model import build_view

log = logging.getLogger(__name__)
GENERIC_ERROR = "Ocurrió un error inesperado al procesar el problema. Revise la entrada e intente de nuevo."


class RequestError(ValueError):
    """Peticion mal formada (mensaje apto para el usuario)."""


def metadata() -> str:
    examples = [{"key": k, **v} for k, v in load_examples().items()]
    limits = {"max_tasks": MAX_TASKS, "max_text_chars": MAX_TEXT_CHARS, "max_conflicts": MAX_CONFLICTS}
    return json.dumps({"examples": examples, "algorithms": list(ALGORITHMS), "limits": limits}, ensure_ascii=False)


def _algorithm(req: Dict[str, Any]) -> str:
    alg = req.get("algorithm", "dsatur")
    if not isinstance(alg, str) or alg not in ALGORITHMS:
        raise RequestError(f"Algoritmo desconocido. Opciones: {', '.join(ALGORITHMS)}")
    return alg


def _number(req: Dict[str, Any], key: str, kind: type, low: float, high: float) -> Any:
    value = req.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestError(f"«{key}» debe ser un número")
    if kind is int and value != int(value):
        raise RequestError(f"«{key}» debe ser un entero")
    if not low <= value <= high:
        raise RequestError(f"«{key}» debe estar entre {low:g} y {high:g}")
    return kind(value)


def _problem(req: Dict[str, Any]):
    mode = req.get("mode")
    if mode == "text":
        text = req.get("text")
        if not isinstance(text, str) or not text.strip():
            raise RequestError("Escriba al menos una tarea.")
        return parse_problem(text)
    if mode == "random":
        n = _number(req, "n", int, 1, MAX_TASKS)
        p = _number(req, "p", float, 0, 1)
        seed = _number(req, "seed", int, 0, 2**31 - 1) if "seed" in req else 0
        if p * n * (n - 1) / 2 > MAX_CONFLICTS:
            raise RequestError(f"Con n = {n} la probabilidad máxima es {2 * MAX_CONFLICTS / (n * (n - 1)):.4f} "
                               f"({MAX_CONFLICTS} conflictos)")
        return random_problem(n, p, seed)
    raise RequestError("Modo desconocido; use «text» o «random».")


def handle(request_json: str) -> str:
    try:
        req = json.loads(request_json)
        if not isinstance(req, dict):
            raise RequestError("La petición debe ser un objeto JSON.")
        view = build_view(plan(_problem(req), _algorithm(req)))
        return json.dumps({"ok": True, "view": view}, ensure_ascii=False)
    except (RequestError, ProblemError) as exc:
        return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
    except Exception:                                       # nunca mostrar trazas al usuario
        log.exception("Fallo inesperado en handle()")
        return json.dumps({"ok": False, "error": GENERIC_ERROR}, ensure_ascii=False)
