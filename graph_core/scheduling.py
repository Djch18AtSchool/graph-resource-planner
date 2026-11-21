"""
Del problema de tareas al plan de ejecucion (Modulo 2: coloracion para asignacion de recursos).

    vertice = tarea / microservicio
    arista  = conflicto: comparten un recurso exclusivo (o se declaro el conflicto)
    color   = lote de ejecucion paralela; los lotes corren uno tras otro

Si un recurso lo usan k tareas, esas k tareas forman una clique K_k del grafo de conflictos, asi que
hacen falta al menos k lotes: chi(G) >= max_r |usuarios(r)|.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Tuple, TypeVar

from .coloring import ALGORITHMS, ColoringResult, color_graph, exact_chromatic_number, greedy_clique
from .graph import Graph
from .problem import Problem, ProblemError

T = TypeVar("T")
MAX_CONFLICTS = 100_000
Pair = Tuple[str, str]


# ----------------------------------------------------------------------- grafo de conflictos
def _conflict_pairs(problem: Problem) -> Dict[Pair, Dict[str, object]]:
    """Par (a, b) en orden de declaracion -> {"resources": [...], "explicit": bool}."""
    order = {t.name: i for i, t in enumerate(problem.tasks)}
    pairs: Dict[Pair, Dict[str, object]] = {}

    def entry(a: str, b: str) -> Dict[str, object]:
        key = (a, b) if order[a] < order[b] else (b, a)
        if key not in pairs:
            if len(pairs) >= MAX_CONFLICTS:          # corta antes de gastar memoria en un grafo enorme
                raise ProblemError(f"El problema genera más de {MAX_CONFLICTS} conflictos; "
                                   "reduzca las tareas por recurso")
            pairs[key] = {"resources": [], "explicit": False}
        return pairs[key]

    for r, users in problem.resource_users().items():
        for i, a in enumerate(users):
            for b in users[i + 1:]:
                entry(a, b)["resources"].append(r)
    for a, b in problem.conflicts:
        entry(a, b)["explicit"] = True
    return pairs


def conflict_graph(problem: Problem) -> Graph:
    """Grafo de conflictos con lista y matriz de adyacencia. O(V + sum_r k_r^2) para k_r usuarios del recurso r."""
    g = Graph()
    for task in problem.tasks:
        g.add_vertex(task.name, duration=task.duration, resources=list(task.resources))
    for (a, b), attrs in _conflict_pairs(problem).items():
        g.add_edge(a, b, **attrs)
    return g


# ------------------------------------------------------------------------------------ plan
@dataclass(frozen=True)
class Batch:
    index: int                       # 1, 2, 3, ... (color + 1)
    tasks: Tuple[str, ...]
    start: float                     # instante en que empieza el lote
    duration: float                  # lo que tarda su tarea mas larga


@dataclass(frozen=True)
class Plan:
    problem: Problem
    graph: Graph
    coloring: ColoringResult         # algoritmo elegido
    alternative: ColoringResult      # el otro algoritmo, para comparar
    bounds: Dict[str, object]        # lower, upper, exact (o None) y method: "clique" | "branch_and_bound" | None
    clique: Tuple[str, ...]          # tareas que se bloquean mutuamente (justifican la cota inferior)
    batches: Tuple[Batch, ...]
    timings: Dict[str, float] = field(default_factory=dict)

    @property
    def makespan(self) -> float:
        return sum(b.duration for b in self.batches)

    @property
    def sequential_time(self) -> float:
        return sum(t.duration for t in self.problem.tasks)

    @property
    def speedup(self) -> float:
        return self.sequential_time / self.makespan if self.makespan else 1.0

    @property
    def workers(self) -> int:
        """Ejecutores necesarios para correr el lote mas grande en paralelo."""
        return max((len(b.tasks) for b in self.batches), default=0)

    @property
    def max_resource_usage(self) -> int:
        return max((len(u) for u in self.problem.resource_users().values()), default=0)

    @property
    def max_degree(self) -> int:
        return max(self.graph.degrees().values(), default=0)


def _batches(problem: Problem, coloring: ColoringResult) -> Tuple[Batch, ...]:
    duration = {t.name: t.duration for t in problem.tasks}
    out, start = [], 0.0
    for i, tasks in enumerate(coloring.batch_list(), start=1):
        length = max(duration[t] for t in tasks)
        out.append(Batch(i, tuple(tasks), start, length))
        start += length
    return tuple(out)


def _lower_bound(problem: Problem, graph: Graph) -> Tuple[int, Tuple[str, ...]]:
    """Mayor clique conocida: la voraz o la de un recurso muy compartido."""
    clique = greedy_clique(graph)
    busiest = max(problem.resource_users().values(), key=len, default=[])
    best = busiest if len(busiest) > len(clique) else clique
    return len(best), tuple(best)


def _timed(timings: Dict[str, float], name: str, fn: Callable[..., T], *args) -> T:
    t0 = time.perf_counter()
    out = fn(*args)
    timings[name] = time.perf_counter() - t0
    return out


def plan(problem: Problem, algorithm: str = "dsatur", try_exact: bool = True) -> Plan:
    """Colorea el grafo de conflictos y arma el plan por lotes, con cotas de chi(G)."""
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Algoritmo desconocido: {algorithm!r}. Opciones: {sorted(ALGORITHMS)}")
    other = next(a for a in ALGORITHMS if a != algorithm)
    timings: Dict[str, float] = {}
    graph = _timed(timings, "conflict_graph", conflict_graph, problem)
    coloring = _timed(timings, "coloring", color_graph, graph, algorithm)
    alternative = _timed(timings, "alternative", color_graph, graph, other)

    t0 = time.perf_counter()
    lower, clique = _lower_bound(problem, graph)
    upper = min(coloring.num_colors, alternative.num_colors)
    exact, method = None, None
    if lower == upper:                               # la clique ya demuestra que la heuristica es optima
        exact, method = upper, "clique"
    elif try_exact:
        exact = exact_chromatic_number(graph)
        method = "branch_and_bound" if exact is not None else None
    if exact is not None:
        lower = upper = exact
    timings["bounds"] = time.perf_counter() - t0

    bounds = {"lower": lower, "upper": upper, "exact": exact, "method": method}
    return Plan(problem, graph, coloring, alternative, bounds, clique, _batches(problem, coloring), timings)
