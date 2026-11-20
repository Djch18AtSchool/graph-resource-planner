"""
Sintesis e interpretacion: de metricas deterministas a un reporte tecnico.

Principio de diseno: el LLM INTERPRETA, nunca CALCULA. Las cifras (chi(G), lotes, planaridad) las
producen los algoritmos de graph_core y se le pasan como JSON ("facts"). Ademas, al final de todo
reporte se anade un bloque "Datos verificados" generado por codigo, de modo que aunque el modelo
se equivoque al redactar, los numeros correctos siempre aparecen.

Si el LLM no esta disponible (modo offline o error de red) se usa ``template_report``.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .llm_client import LLMClient, LLMError
from .prompts import SYSTEM_REPORT


@dataclass
class Report:
    text: str
    source: str                      # "llm" | "template"
    warning: Optional[str] = None


def verified_block(facts: Dict[str, Any]) -> str:
    c, p = facts["chromatic"], facts["planarity"]
    chi = (f"chi(G) = {c['exact']} (exacto)" if c.get("exact") is not None
           else f"{c['lower']} <= chi(G) <= {c['upper']}")
    chi += f"; {ALGORITHM_NAMES.get(c['algorithm'], c['algorithm'])} usa {c['colors_used']} colores"
    plan = ("plano" if p["is_planar"] else
            f"NO plano (subdivision de {p['witness']}; {p['crossings']} cruce(s) -> {p['virtual_nodes']} nodo(s) virtual(es))")
    return ("### Datos verificados (calculados por el motor)\n"
            f"- Nodos: {facts['nodes']} | dependencias: {facts['dependency_edges']} | conflictos: {facts['conflict_edges']}\n"
            f"- {chi} (Welsh-Powell: {c['welsh_powell_colors']})\n"
            f"- Lotes secuenciales: {len(facts['schedule'])} | maximo de tareas en paralelo: {facts['max_parallel_tasks']}\n"
            f"- Diagrama de arquitectura: {plan}\n")


ALGORITHM_NAMES = {"dsatur": "DSatur", "welsh_powell": "Welsh-Powell"}


def _chromatic_sentence(c: Dict[str, Any]) -> str:
    """chi(G) es el MINIMO de lotes; la heuristica puede usar mas (p. ej. Welsh-Powell en grafos corona)."""
    if c.get("exact") is not None:
        return (f"El numero cromatico del grafo de conflictos es chi(G) = {c['exact']}: ningun plan "
                f"puede usar menos de {c['exact']} lote(s).")
    return (f"El numero cromatico del grafo de conflictos esta acotado: {c['lower']} <= chi(G) <= {c['upper']} "
            "(calcularlo exacto es NP-dificil).")


def template_report(facts: Dict[str, Any]) -> str:
    """Reporte determinista (sin LLM) con las mismas secciones que pide el prompt."""
    c, p = facts["chromatic"], facts["planarity"]
    k = len(facts["schedule"])
    lines = [f"## Resumen",
             f"El sistema \"{facts['title'] or 'sin titulo'}\" tiene {facts['nodes']} componentes, "
             f"{facts['dependency_edges']} dependencias y {facts['conflict_edges']} conflictos de recursos. "
             f"{_chromatic_sentence(c)} El plan propuesto usa {k} lote(s) secuencial(es).",
             "", "## Plan de ejecucion"]
    for slot in facts["schedule"]:
        lines.append(f"- **Lote {slot['slot']}** ({len(slot['tasks'])} en paralelo): " + ", ".join(slot["tasks"]))
    if facts.get("unconstrained"):
        lines.append(f"- Sin restricciones (pueden correr en cualquier lote): " + ", ".join(facts["unconstrained"]) + ".")
    lines += ["", "## Infraestructura minima recomendada",
              f"- {k} ventanas/lotes de ejecucion secuenciales.",
              f"- Capacidad para {facts['max_parallel_tasks']} tareas concurrentes (el lote mas grande).",
              ]
    if facts.get("forcing_clique") and len(facts["forcing_clique"]) > 1:
        lines.append("- Estas tareas se bloquean mutuamente y por eso fuerzan los lotes: "
                     + ", ".join(facts["forcing_clique"]) + ".")
    lines += ["", "## Arquitectura y planaridad"]
    if p["is_planar"]:
        lines.append("El diagrama es plano: se puede dibujar sin cruces de aristas.")
    else:
        lines.append(f"El diagrama NO es plano (contiene una subdivision de {p['witness']}). Se introdujeron "
                     f"{p['virtual_nodes']} nodo(s) virtual(es) en {p['crossings']} cruce(s); considere agrupar esas "
                     "conexiones en un bus/gateway para simplificar la arquitectura.")
    lines += ["", "## Riesgos y siguientes pasos"]
    if facts.get("most_connected"):
        top = facts["most_connected"][0]
        lines.append(f"- Punto de acoplamiento principal: {top['label']} (grado {top['degree']}).")
    lines.append("- Revisar los conflictos que mas aumentan el numero de lotes; compartir menos recursos reduce chi(G).")
    return "\n".join(lines)


class ReportGenerator:
    def __init__(self, client: LLMClient) -> None:
        self.client = client

    async def generate(self, facts: Dict[str, Any]) -> Report:
        verified = verified_block(facts)
        if self.client.is_offline:
            return Report(template_report(facts) + "\n\n" + verified, "template")
        user = "METRICAS (JSON):\n" + json.dumps(facts, ensure_ascii=False, indent=2)
        try:
            body = await self.client.complete_text(SYSTEM_REPORT, user)
        except LLMError as exc:
            return Report(template_report(facts) + "\n\n" + verified, "template",
                          warning=f"El LLM fallo ({exc}); se uso la plantilla determinista.")
        return Report(body + "\n\n" + verified, "llm")
