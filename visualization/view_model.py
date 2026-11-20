"""
Modelo de vista: convierte un ``AnalysisResult`` en un JSON listo para la interfaz web.

La web no recalcula nada: recibe posiciones, lotes, cruces y metricas ya calculados por
graph_core en Python. Se generan DOS dibujos para la demostracion:

* ``planar``: grafo planarizado (reales + nodos virtuales) con el dibujo de Tutte refinado (0 cruces).
* ``spring``: la arquitectura original con un layout de fuerzas (networkx), que en general SI cruza
  aristas; sirve para mostrar el valor del dibujo plano.

Las coordenadas se escalan a un lienzo de ``CANVAS`` unidades con el eje y hacia abajo (pantalla).
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import networkx as nx

from graph_core import Graph, count_crossings

Position = Tuple[float, float]
CANVAS = 1000.0
MATRIX_MAX_VERTICES = 40
SPRING_SEED = 7


def _scale(pos: Dict[Any, Position]) -> Dict[Any, Position]:
    """Normaliza a [0, CANVAS] conservando la proporcion e invierte y (pantalla)."""
    if not pos:
        return {}
    xs = [p[0] for p in pos.values()]
    ys = [p[1] for p in pos.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
    x0, y1 = min(xs), max(ys)
    return {v: ((x - x0) / span * CANVAS, (y1 - y) / span * CANVAS) for v, (x, y) in pos.items()}


def _witness_pairs(edges: Sequence[Tuple[Any, Any]]) -> Set[frozenset]:
    return {frozenset(e) for e in edges}


def _nodes(analysis, graph: Graph, pos: Dict[Any, Position], branch: Set[Any]) -> List[Dict[str, Any]]:
    arch = analysis.architecture_graph
    constrained = set(analysis.constrained_vertices())
    colors = analysis.coloring.colors
    out = []
    for v in graph.vertices:
        x, y = pos[v]
        real = v in arch
        attrs = arch.vertex_attrs(v) if real else {}
        out.append({
            "id": str(v), "label": analysis.label(v) if real else "", "type": attrs.get("type", "virtual"),
            "description": attrs.get("description", ""), "virtual": not real,
            "batch": colors[v] + 1 if real and v in constrained else None,
            "degree": arch.degree(v) if real else graph.degree(v),
            "kuratowski": v in branch, "x": round(x, 2), "y": round(y, 2),
        })
    return out


def _edges(graph: Graph, witness: Set[frozenset]) -> List[Dict[str, Any]]:
    out = []
    for i, (u, v) in enumerate(graph.edges):
        attrs = graph.edge_attrs(u, v)
        original = attrs.get("original_edge", [u, v])
        out.append({
            "id": f"e{i}", "source": str(u), "target": str(v),
            "kinds": list(attrs.get("kinds", [])), "reason": attrs.get("reason", ""),
            "original": [str(original[0]), str(original[1])],
            "kuratowski": frozenset(original) in witness,
        })
    return out


def _drawing(analysis, graph: Graph, raw_pos: Dict[Any, Position]) -> Dict[str, Any]:
    p = analysis.planarity
    witness = _witness_pairs(p.witness_edges)
    pos = _scale(raw_pos)
    return {
        "nodes": _nodes(analysis, graph, pos, set(p.witness_branch_vertices)),
        "edges": _edges(graph, witness),
        "crossings": count_crossings(raw_pos, graph.edges),
    }


def spring_positions(graph: Graph) -> Dict[Any, Position]:
    if graph.num_vertices == 0:
        return {}
    k = 1.6 / max(1, graph.num_vertices) ** 0.5
    raw = nx.spring_layout(graph.to_networkx(), seed=SPRING_SEED, k=k)
    return {v: (float(x), float(y)) for v, (x, y) in raw.items()}


def adjacency_view(graph: Graph, labeler) -> Optional[Dict[str, Any]]:
    if graph.num_vertices > MATRIX_MAX_VERTICES:
        return None
    return {"labels": [labeler(v) for v in graph.vertices], "rows": graph.adjacency_matrix(),
            "degrees": [graph.degree(v) for v in graph.vertices]}


def build_view(analysis, report_text: Optional[str] = None, report_source: str = "",
               warnings: Sequence[str] = (), provider: str = "", attempts: int = 1) -> Dict[str, Any]:
    """JSON completo que consume la interfaz web (ver visualization/web/app.js)."""
    arch = analysis.architecture_graph
    return {
        "facts": analysis.facts(),
        "spec": analysis.spec.model_dump(),
        "planar": _drawing(analysis, analysis.drawing_graph, analysis.positions),
        "spring": _drawing(analysis, arch, spring_positions(arch)),
        "conflict_matrix": adjacency_view(analysis.conflict_graph, analysis.label),
        "timings_ms": {k: round(v * 1000, 3) for k, v in analysis.timings.items()},
        "report": report_text or "",
        "report_source": report_source,
        "warnings": list(warnings),
        "provider": provider,
        "attempts": attempts,
    }
