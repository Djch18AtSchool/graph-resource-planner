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


@dataclass
class ColoringResult:
    algorithm: str
    colors: Dict[Vertex, int]            # vertice -> color (0, 1, 2, ...)
    num_colors: int
    valid: bool = True
    batches: Dict[int, List[Vertex]] = field(default_factory=dict)  # color -> vertices

    def batch_list(self) -> List[List[Vertex]]:
        return [self.batches[c] for c in sorted(self.batches)]


def _build_result(graph: Graph, algorithm: str, colors: Dict[Vertex, int]) -> ColoringResult:
    batches: Dict[int, List[Vertex]] = {}
    for v in graph.vertices:                         # orden estable
        batches.setdefault(colors[v], []).append(v)
    return ColoringResult(algorithm=algorithm, colors=colors,
                          num_colors=len(batches), valid=is_valid_coloring(graph, colors),
                          batches=batches)


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
        for u in graph.neighbors(v):
            if u not in colors and c not in nbr_colors[u]:
                nbr_colors[u].add(c)
                heapq.heappush(heap, (-len(nbr_colors[u]), -deg[u], idx[u]))
    return _build_result(graph, "dsatur", colors)


# ----------------------------------------------------------------------- Welsh-Powell
def welsh_powell(graph: Graph) -> ColoringResult:
    """
    Welsh-Powell: ordena vertices por grado decreciente y construye un color a la
    vez: asigna el color actual a cada vertice sin colorear que no sea vecino de
    otro ya asignado en esa ronda. O(k*V + E) <= O(V^2).
    """
    order = sorted(graph.vertices, key=lambda v: -graph.degree(v))   # sort estable
    colors: Dict[Vertex, int] = {}
    remaining = len(order)
    c = 0
    while remaining:
        blocked = set()
        for v in order:
            if v in colors or v in blocked:
                continue
            colors[v] = c
            remaining -= 1
            blocked.update(graph.neighbors(v))
        c += 1
    return _build_result(graph, "welsh_powell", colors)


ALGORITHMS = {"dsatur": dsatur, "welsh_powell": welsh_powell}


def color_graph(graph: Graph, algorithm: str = "dsatur") -> ColoringResult:
    try:
        return ALGORITHMS[algorithm](graph)
    except KeyError:
        raise ValueError(f"Algoritmo desconocido: {algorithm!r}. Opciones: {sorted(ALGORITHMS)}")


# ------------------------------------------------------------------------------ cotas
def greedy_clique(graph: Graph, starts: int = 25) -> List[Vertex]:
    """
    Clique hallada vorazmente (se intenta desde los ``starts`` vertices de mayor grado).
    Sus miembros son tareas que se bloquean mutuamente: fuerzan al menos |clique| lotes.
    """
    if graph.num_vertices == 0:
        return []
    order = sorted(graph.vertices, key=lambda v: -graph.degree(v))
    best: List[Vertex] = [order[0]]
    for s in order[:starts]:
        clique = [s]
        cand = set(graph.neighbors(s))
        while cand:
            # el candidato con mas vecinos dentro de cand maximiza el crecimiento
            v = max(cand, key=lambda x: len(cand.intersection(graph.neighbors(x))))
            clique.append(v)
            cand &= set(graph.neighbors(v))
        if len(clique) > len(best):
            best = clique
    return best


def clique_lower_bound(graph: Graph, starts: int = 25) -> int:
    """Cota inferior de chi(G): omega(G) <= chi(G), con omega estimado por una clique voraz."""
    return len(greedy_clique(graph, starts))


class _SearchLimit(Exception):
    pass


def _exact_component(sub: Graph, node_limit: int) -> Optional[int]:
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
    state = {"best": upper, "nodes": 0}

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
        state["nodes"] += 1
        if state["nodes"] > node_limit:
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
    chi(G) exacto por branch & bound (DSatur + cotas). Solo componentes conexas de
    hasta ``max_vertices`` vertices y ``node_limit`` nodos de busqueda; si se excede
    devuelve None (el valor exacto es NP-dificil en general).
    """
    if graph.num_vertices == 0:
        return 0
    chi = 1
    for comp in graph.connected_components():
        if len(comp) > max_vertices:
            return None
        res = _exact_component(graph.subgraph(comp), node_limit)
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
