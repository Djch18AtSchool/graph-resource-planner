"""
Plan -> diccionario JSON para la interfaz web (lo que el navegador dibuja y lista).

Toda la matematica ya esta resuelta en ``graph_core``; aqui solo se traduce a datos planos:
lotes 1-indexados, pasos del algoritmo, cotas de chi(G), recursos y la matriz de adyacencia.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from graph_core import Plan

MATRIX_MAX_VERTICES = 40          # mas alla, la matriz V x V no se lee en pantalla
DRAW_MAX_EDGES = 8000             # mas alla, Cytoscape se vuelve lento: se omite el dibujo


def _metrics(p: Plan) -> Dict[str, Any]:
    g = p.graph
    return {
        "tasks": g.num_vertices,
        "conflicts": g.num_edges,
        "density": round(g.density(), 4),
        "max_degree": p.max_degree,
        "colors": p.coloring.num_colors,
        "lower": p.bounds["lower"],
        "upper": p.bounds["upper"],
        "exact": p.bounds["exact"],
        "exact_method": p.bounds["method"],
        "greedy_bound": p.max_degree + 1,
        "workers": p.workers,
        "makespan": p.makespan,
        "sequential": p.sequential_time,
        "speedup": round(p.speedup, 2),
        "max_resource_usage": p.max_resource_usage,
    }


def _matrix(p: Plan) -> Optional[Dict[str, List]]:
    g = p.graph
    if g.num_vertices > MATRIX_MAX_VERTICES:
        return None
    return {"labels": g.vertices, "rows": g.adjacency_matrix(), "degrees": [g.degree(v) for v in g.vertices]}


def build_view(p: Plan) -> Dict[str, Any]:
    g, colors = p.graph, p.coloring.colors
    drawable = g.num_edges <= DRAW_MAX_EDGES
    resources = sorted(p.problem.resource_users().items(), key=lambda kv: (-len(kv[1]), kv[0]))
    return {
        "title": p.problem.title,
        "algorithm": p.coloring.algorithm,
        "alternative": {"algorithm": p.alternative.algorithm, "colors": p.alternative.num_colors},
        "metrics": _metrics(p),
        "tasks": [{"id": t.name, "duration": t.duration, "resources": list(t.resources),
                   "degree": g.degree(t.name), "batch": colors[t.name] + 1} for t in p.problem.tasks],
        "conflicts": [{"source": u, "target": v, **g.edge_attrs(u, v)} for u, v in g.edges] if drawable else [],
        "drawable": drawable,
        "batches": [{"index": b.index, "tasks": list(b.tasks), "start": b.start, "duration": b.duration}
                    for b in p.batches],
        "steps": [{"task": s.vertex, "batch": s.color + 1, "saturation": s.saturation} for s in p.coloring.steps],
        "clique": list(p.clique),
        "resources": [{"name": r, "tasks": users} for r, users in resources],
        "matrix": _matrix(p),
        "timings_ms": {k: v * 1000 for k, v in p.timings.items()},
    }
