"""
Coloracion de vertices para asignacion de recursos.

Interpretacion en el sistema:
    vertice = tarea / microservicio
    arista  = conflicto de recurso compartido (no pueden ejecutarse a la vez)
    color   = lote ("slot") de ejecucion paralela libre de colisiones

Algoritmos (heuristicas; calcular chi(G) exacto es NP-dificil):

    DSatur         O((V + E) log V)  con heap perezoso (esta implementacion)
    Welsh-Powell   O(k*V + E) <= O(V^2), k = colores usados

Cotas:
    inferior: tamano de una clique  (omega(G) <= chi(G))
    superior: colores que usa la heuristica (y Delta(G)+1 en el peor caso)
    exacto  : branch & bound sobre DSatur, solo para componentes pequenas
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .graph import Graph, Vertex


@dataclass(frozen=True)
class ColoringStep:
    """Una decision del algoritmo: ``vertex`` recibe ``color``.

    ``saturation`` = colores distintos entre sus vecinos ya coloreados en ese momento (solo DSatur;
    en Welsh-Powell es None porque el criterio es el grado y la ronda).
    """
    vertex: Vertex
    color: int
    saturation: Optional[int] = None


@dataclass
class ColoringResult:
    algorithm: str
    colors: Dict[Vertex, int]            # vertice -> color (0, 1, 2, ...)
    num_colors: int
    valid: bool = True
    batches: Dict[int, List[Vertex]] = field(default_factory=dict)  # color -> vertices
    steps: List[ColoringStep] = field(default_factory=list)         # orden en que se coloreo

    def batch_list(self) -> List[List[Vertex]]:
        return [self.batches[c] for c in sorted(self.batches)]


def _build_result(graph: Graph, algorithm: str, colors: Dict[Vertex, int],
                  steps: List[ColoringStep]) -> ColoringResult:
    batches: Dict[int, List[Vertex]] = {}
    for v in graph.vertices:                         # orden estable
        batches.setdefault(colors[v], []).append(v)
    return ColoringResult(algorithm=algorithm, colors=colors,
                          num_colors=len(batches), valid=is_valid_coloring(graph, colors),
                          batches=batches, steps=steps)


def is_valid_coloring(graph: Graph, colors: Dict[Vertex, int]) -> bool:
    """Ninguna arista une dos vertices del mismo color y todo vertice tiene color. O(V + E)."""
    if any(v not in colors for v in graph.vertices):
        return False
    return all(colors[u] != colors[v] for u, v in graph.edges)


# --------------------------------------------------------------------------- DSatur
def dsatur(graph: Graph) -> ColoringResult:
    """
    DSatur (Brelaz, 1979): se colorea siempre el vertice con mayor *saturacion*
    (numero de colores distintos entre sus vecinos ya coloreados); empates por
    mayor grado y luego por orden de insercion (determinista).

    Implementacion con heap perezoso: cada vez que la saturacion de un vecino
    cambia se empuja una entrada nueva; las entradas obsoletas se descartan al
    extraerlas. Cada arista provoca a lo sumo un push -> O((V + E) log V).
    DSatur es exacto en grafos bipartitos, ciclos y ruedas.
    """
    labels = graph.vertices
    idx = {v: i for i, v in enumerate(labels)}
    deg = {v: graph.degree(v) for v in labels}
    nbr_colors: Dict[Vertex, set] = {v: set() for v in labels}
    colors: Dict[Vertex, int] = {}
    steps: List[ColoringStep] = []

    heap = [(0, -deg[v], idx[v]) for v in labels]
    heapq.heapify(heap)
    while heap:
        neg_sat, _, i = heapq.heappop(heap)
        v = labels[i]
        if v in colors or -neg_sat != len(nbr_colors[v]):
            continue                                  # entrada obsoleta
        used = nbr_colors[v]
        c = 0
        while c in used:                              # menor color disponible (mex)
            c += 1
        colors[v] = c
        steps.append(ColoringStep(v, c, len(used)))
        for u in graph.neighbors(v):
            if u not in colors and c not in nbr_colors[u]:
                nbr_colors[u].add(c)
                heapq.heappush(heap, (-len(nbr_colors[u]), -deg[u], idx[u]))
    return _build_result(graph, "dsatur", colors, steps)


# ----------------------------------------------------------------------- Welsh-Powell
def welsh_powell(graph: Graph) -> ColoringResult:
    """
    Welsh-Powell: ordena vertices por grado decreciente y construye un color a la
    vez: asigna el color actual a cada vertice sin colorear que no sea vecino de
    otro ya asignado en esa ronda. O(k*V + E) <= O(V^2).
    """
    order = sorted(graph.vertices, key=lambda v: -graph.degree(v))   # sort estable
    colors: Dict[Vertex, int] = {}
    steps: List[ColoringStep] = []
    remaining = len(order)
    c = 0
    while remaining:
        blocked = set()
        for v in order:
            if v in colors or v in blocked:
                continue
            colors[v] = c
            steps.append(ColoringStep(v, c))
            remaining -= 1
            blocked.update(graph.neighbors(v))
        c += 1
    return _build_result(graph, "welsh_powell", colors, steps)


ALGORITHMS = {"dsatur": dsatur, "welsh_powell": welsh_powell}
ALGORITHM_NAMES = {"dsatur": "DSatur", "welsh_powell": "Welsh-Powell"}


def color_graph(graph: Graph, algorithm: str = "dsatur") -> ColoringResult:
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Algoritmo desconocido: {algorithm!r}. Opciones: {sorted(ALGORITHMS)}")
    return ALGORITHMS[algorithm](graph)


# ------------------------------------------------------------------------------ cotas
CLIQUE_REFINE_SIZE = 48     # con mas candidatos, elegir por grado (O(k)) en vez de por interseccion (O(k^2))


def greedy_clique(graph: Graph, starts: int = 25) -> List[Vertex]:
    """
    Clique hallada vorazmente (se intenta desde los ``starts`` vertices de mayor grado).
    Sus miembros son tareas que se bloquean mutuamente: fuerzan al menos |clique| lotes.

    Con pocos candidatos se elige el que tiene mas vecinos dentro de ellos (mejor calidad); con
    muchos, el de mayor grado, para que una clique enorme cueste O(k^2) por inicio y no O(k^3).
    """
    if graph.num_vertices == 0:
        return []
    nbrs = {v: set(graph.neighbors(v)) for v in graph.vertices}
    order = sorted(graph.vertices, key=lambda v: -len(nbrs[v]))
    rank = {v: i for i, v in enumerate(order)}
    best: List[Vertex] = [order[0]]
    for s in order[:starts]:
        clique = [s]
        cand = set(nbrs[s])
        while cand:
            if len(cand) > CLIQUE_REFINE_SIZE:
                v = min(cand, key=rank.__getitem__)
            else:
                v = max(cand, key=lambda x: (len(cand & nbrs[x]), -rank[x]))
            clique.append(v)
            cand &= nbrs[v]
        if len(clique) > len(best):
            best = clique
    return best


def clique_lower_bound(graph: Graph, starts: int = 25) -> int:
    """Cota inferior de chi(G): omega(G) <= chi(G), con omega estimado por una clique voraz."""
    return len(greedy_clique(graph, starts))


class _SearchLimit(Exception):
    pass


def _exact_component(sub: Graph, budget: Dict[str, int]) -> Optional[int]:
    upper = dsatur(sub).num_colors
    lower = clique_lower_bound(sub)
    if lower >= upper:
        return upper

    labels = sub.vertices
    adj = {v: sub.neighbors(v) for v in labels}
    deg = {v: len(adj[v]) for v in labels}
    cnt: Dict[Vertex, Dict[int, int]] = {v: {} for v in labels}   # color -> #vecinos con ese color
    sat = {v: 0 for v in labels}
    colored: Dict[Vertex, int] = {}
    state = {"best": upper}

    def assign(v: Vertex, c: int) -> None:
        colored[v] = c
        for u in adj[v]:
            if u not in colored:
                n = cnt[u].get(c, 0)
                cnt[u][c] = n + 1
                if n == 0:
                    sat[u] += 1

    def undo(v: Vertex, c: int) -> None:
        del colored[v]
        for u in adj[v]:
            if u not in colored:
                cnt[u][c] -= 1
                if cnt[u][c] == 0:
                    sat[u] -= 1

    def search(used: int) -> None:
        budget["left"] -= 1
        if budget["left"] < 0:
            raise _SearchLimit
        if len(colored) == len(labels):
            state["best"] = used
            return
        v = max((x for x in labels if x not in colored), key=lambda x: (sat[x], deg[x]))
        for c in range(min(used + 1, state["best"] - 1)):
            if cnt[v].get(c, 0) > 0:
                continue
            new_used = max(used, c + 1)
            if new_used >= state["best"]:
                continue
            assign(v, c)
            search(new_used)
            undo(v, c)
            if state["best"] <= lower:
                return

    try:
        search(0)
    except _SearchLimit:
        return None
    return state["best"]


def exact_chromatic_number(graph: Graph, max_vertices: int = 60,
                           node_limit: int = 200_000) -> Optional[int]:
    """
    chi(G) exacto por branch & bound (DSatur + cotas). Solo si toda componente conexa tiene
    hasta ``max_vertices`` vertices; ``node_limit`` nodos de busqueda en TOTAL (compartidos por
    todas las componentes). Si se excede devuelve None (el valor exacto es NP-dificil en general).
    """
    if graph.num_vertices == 0:
        return 0
    comps = sorted(graph.connected_components(), key=len, reverse=True)
    if len(comps[0]) > max_vertices:
        return None
    budget = {"left": node_limit}
    chi = 1
    for comp in comps:
        if len(comp) <= chi:                       # chi(componente) <= |componente|: no puede subir
            break
        res = _exact_component(graph.subgraph(comp), budget)
        if res is None:
            return None
        chi = max(chi, res)
    return chi


def chromatic_bounds(graph: Graph, try_exact: bool = True) -> Dict[str, Optional[int]]:
    """Resumen de cotas: ``lower`` <= chi(G) <= ``upper`` (y ``exact`` si fue posible)."""
    upper = min(dsatur(graph).num_colors, welsh_powell(graph).num_colors)
    lower = clique_lower_bound(graph)
    exact = exact_chromatic_number(graph) if try_exact else None
    if exact is not None:
        lower = upper = exact
    return {"lower": lower, "upper": upper, "exact": exact}
