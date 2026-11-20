"""
Orquestador del motor: GraphSpec -> coloracion + planaridad -> metricas -> (LLM) reporte.

    texto --[ai_agent.parser]--> GraphSpec
                                   |-- conflict_graph()      --[graph_core.coloring]--> lotes, chi(G)
                                   `-- architecture_graph()  --[graph_core.planarity]--> embedding / planarizacion
    metricas ("facts") --[ai_agent.reporter]--> reporte tecnico

Es la unica capa que conoce a ai_agent y graph_core; la CLI y la web solo llaman a este modulo.
``analyze_spec`` es sincrono (calculo puro); ``run_pipeline`` es asincrono porque espera al LLM.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ai_agent import GraphSpec, LLMClient, ParseResult, Report, ReportGenerator, RequirementParser
from graph_core import (ColoringResult, Graph, PlanarityResult, PlanarizationResult, check_planarity,
                        chromatic_bounds, color_graph, greedy_clique, planar_drawing, planarize,
                        welsh_powell)

Position = Tuple[float, float]


@dataclass
class AnalysisResult:
    spec: GraphSpec
    conflict_graph: Graph
    architecture_graph: Graph
    coloring: ColoringResult
    coloring_wp: ColoringResult
    bounds: Dict[str, Optional[int]]
    clique: List[str]
    planarity: PlanarityResult
    planarization: PlanarizationResult
    drawing_positions: Dict[Any, Position] = field(default_factory=dict)
    timings: Dict[str, float] = field(default_factory=dict)

    # --------------------------------------------------------------------------- vistas
    @property
    def positions(self) -> Dict[Any, Position]:
        """Dibujo plano legible (Tutte + refinamiento) del grafo planarizado; 0 cruces."""
        return self.drawing_positions or self.planarization.positions

    @property
    def drawing_graph(self) -> Graph:
        """Grafo que se dibuja: la arquitectura, con nodos virtuales si fue necesario planarizar."""
        return self.planarization.graph

    def label(self, v: Any) -> str:
        return self.architecture_graph.vertex_attrs(v).get("label", v) if v in self.architecture_graph else str(v)

    def constrained_vertices(self) -> List[str]:
        """Componentes involucrados en algun conflicto: son los unicos que hay que planificar."""
        return [v for v in self.conflict_graph.vertices if self.conflict_graph.degree(v) > 0]

    def unconstrained_vertices(self) -> List[str]:
        return [v for v in self.conflict_graph.vertices if self.conflict_graph.degree(v) == 0]

    def schedule_vertices(self) -> List[List[str]]:
        """Lotes (color = slot) solo con componentes en conflicto. Sin conflictos -> un unico lote con todo."""
        constrained = set(self.constrained_vertices())
        if not constrained:
            return [self.conflict_graph.vertices] if self.conflict_graph.num_vertices else []
        return [[v for v in batch if v in constrained] for batch in self.coloring.batch_list()]

    def schedule(self) -> List[Dict[str, Any]]:
        return [{"slot": i + 1, "tasks": [self.label(v) for v in batch]}
                for i, batch in enumerate(self.schedule_vertices())]

    def facts(self) -> Dict[str, Any]:
        """Metricas compactas que se entregan al LLM (y a las plantillas)."""
        arch, p = self.architecture_graph, self.planarity
        kinds = [e.kind for e in self.spec.edges]
        top = sorted(arch.vertices, key=lambda v: -arch.degree(v))[:3]
        return {
            "title": self.spec.title,
            "nodes": arch.num_vertices,
            "dependency_edges": kinds.count("dependency"),
            "conflict_edges": kinds.count("conflict"),
            "chromatic": {
                "algorithm": self.coloring.algorithm, "colors_used": self.coloring.num_colors,
                "welsh_powell_colors": self.coloring_wp.num_colors,
                "lower": self.bounds["lower"], "upper": self.bounds["upper"], "exact": self.bounds["exact"],
            },
            "schedule": self.schedule(),
            "max_parallel_tasks": max((len(b) for b in self.schedule_vertices()), default=0),
            "unconstrained": [self.label(v) for v in self.unconstrained_vertices()]
            if self.constrained_vertices() else [],
            "forcing_clique": [self.label(v) for v in self.clique],
            "planarity": {
                "is_planar": p.is_planar, "witness": p.witness_kind,
                "witness_vertices": [self.label(v) for v in p.witness_branch_vertices],
                "euler_bound_exceeded": p.euler_bound_exceeded,
                "crossings": self.planarization.num_crossings,
                "virtual_nodes": len(self.planarization.virtual_nodes),
                "unrouted_edges": len(self.planarization.unrouted_edges),
            },
            "most_connected": [{"label": self.label(v), "degree": arch.degree(v)} for v in top],
        }


def analyze_spec(spec: GraphSpec, algorithm: str = "dsatur", planarize_time_limit: Optional[float] = 30.0) -> AnalysisResult:
    """Ejecuta todos los algoritmos deterministas sobre una especificacion ya validada."""
    timings: Dict[str, float] = {}

    def timed(name, fn, *a, **kw):
        t = time.perf_counter()
        out = fn(*a, **kw)
        timings[name] = time.perf_counter() - t
        return out

    conflict, arch = spec.conflict_graph(), spec.architecture_graph()
    coloring = timed("coloring", color_graph, conflict, algorithm)
    coloring_wp = timed("coloring_welsh_powell", welsh_powell, conflict)
    bounds = timed("chromatic_bounds", chromatic_bounds, conflict)
    clique = greedy_clique(conflict)
    planarity = timed("planarity", check_planarity, arch)
    planarization = timed("planarization", planarize, arch, time_limit=planarize_time_limit)
    drawing = timed("drawing", planar_drawing, planarization.graph, fallback=planarization.positions)
    return AnalysisResult(spec, conflict, arch, coloring, coloring_wp, bounds, clique,
                          planarity, planarization, drawing, timings)


async def run_pipeline(text: str, client: LLMClient, algorithm: str = "dsatur",
                       with_report: bool = True) -> Tuple[ParseResult, AnalysisResult, Optional[Report]]:
    """Requerimiento en lenguaje natural -> (parseo, analisis, reporte)."""
    parsed = await RequirementParser(client).parse(text)
    analysis = analyze_spec(parsed.spec, algorithm)
    report = await ReportGenerator(client).generate(analysis.facts()) if with_report else None
    return parsed, analysis, report
