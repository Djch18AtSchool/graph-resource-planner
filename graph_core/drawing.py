"""
Dibujo plano "legible" de un grafo plano: embedding baricentrico de Tutte.

El embedding de ``check_planarity`` usa el algoritmo de de Fraysseix-Pach-Pollack (rejilla
(2V-4) x (V-2)): es O(V) y garantiza 0 cruces, pero produce triangulos muy aplastados, poco
legibles en un diagrama de arquitectura. Para la visualizacion se usa el teorema de Tutte (1963):

    Si G es plano y 3-conexo, se fija su cara externa como un poligono convexo y cada vertice
    interno se coloca en el BARICENTRO de sus vecinos, el dibujo con segmentos rectos resultante
    es plano (sin cruces) y todas las caras son convexas.

Procedimiento (V vertices, E aristas):
    1. Se triangula el embedding combinatorio (salvo la cara mas grande, que sera la externa);
       esto agrega aristas auxiliares que lo vuelven conexo y 2-conexo.           O(V)
    2. La cara externa se fija sobre una circunferencia (poligono estrictamente convexo).
    3. Coordenadas internas: sistema lineal  L_int * x = b  (Laplaciano de los internos).
       Se resuelve con numpy.                                                       O(V^3) denso
    4. Refinamiento por fuerzas que PRESERVA la planaridad (grafos pequenos): Fruchterman-Reingold
       donde un movimiento solo se acepta si las aristas incidentes al vertice movido no cruzan
       ninguna otra arista. Invariante: el dibujo es plano antes y despues de cada paso.
       Costo por iteracion O(V^2 + V*d*E) = O(V^2 + E^2).
    5. Verificacion independiente con ``count_crossings`` sobre las aristas ORIGINALES; si por
       degeneraciones numericas apareciera algun cruce, se usa el dibujo de rejilla (siempre plano).

Las aristas auxiliares de la triangulacion solo sirven para el calculo: no se dibujan.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
from networkx.algorithms.planar_drawing import triangulate_embedding

from .graph import Graph, Vertex

Position = Tuple[float, float]

MIN_NODES_FOR_TUTTE = 4          # con 3 o menos vertices cualquier dibujo es plano
COMPONENT_GAP = 0.35             # separacion horizontal entre componentes (en unidades del radio)
REFINE_ITERATIONS = 300          # iteraciones maximas (grafos pequenos)
REFINE_WORK_BUDGET = 1_500_000   # tope de E^2 * iteraciones (~1 s en CPython): grafos densos iteran menos
REFINE_MIN_ITERATIONS = 30       # por debajo no vale la pena refinar (se deja el dibujo de Tutte)
COOLING = 0.985                  # factor de enfriamiento de la "temperatura" (paso maximo)
BACKTRACK_STEPS = 3              # si un paso crea un cruce se prueba con 1/2 y 1/4 del paso
NODE_EDGE_REACH = 0.8            # radio (en multiplos de la distancia ideal k) de la repulsion vertice-arista
MIN_DISTANCE = 1e-6


def _circle(nodes: List[Vertex], radius: float = 1.0) -> Dict[Vertex, Position]:
    k = len(nodes)
    return {v: (radius * math.cos(2 * math.pi * i / k + math.pi / 2),
                radius * math.sin(2 * math.pi * i / k + math.pi / 2))
            for i, v in enumerate(nodes)}


def _small_layout(nodes: List[Vertex]) -> Dict[Vertex, Position]:
    """Componentes con <= 3 vertices: punto, segmento o triangulo (siempre planos)."""
    if len(nodes) == 1:
        return {nodes[0]: (0.0, 0.0)}
    if len(nodes) == 2:
        return {nodes[0]: (-0.5, 0.0), nodes[1]: (0.5, 0.0)}
    return _circle(nodes, 0.6)


def tutte_positions(embedding: nx.PlanarEmbedding) -> Dict[Vertex, Position]:
    """Embedding baricentrico de Tutte de un embedding plano CONEXO con >= 4 vertices."""
    tri, outer = triangulate_embedding(embedding, fully_triangulate=False)
    pos = _circle(list(outer))
    inner = [v for v in tri.nodes if v not in pos]
    if not inner:
        return pos
    idx = {v: i for i, v in enumerate(inner)}
    n = len(inner)
    lap = np.zeros((n, n))
    rhs = np.zeros((n, 2))
    for v in inner:
        i = idx[v]
        nbrs = list(tri.neighbors(v))
        lap[i, i] = len(nbrs)
        for w in nbrs:
            if w in idx:
                lap[i, idx[w]] -= 1.0
            else:
                rhs[i] += pos[w]
    sol = np.linalg.solve(lap, rhs)
    for v in inner:
        x, y = sol[idx[v]]
        pos[v] = (float(x), float(y))
    return pos


def _segment_hits_any(a: Position, b: Position, u: Vertex, w: Vertex,
                      edges: List[Tuple[Vertex, Vertex]], pos: Dict[Vertex, Position]) -> bool:
    from .planarity import _segments_cross
    for x, y in edges:
        if x in (u, w) or y in (u, w):
            continue                                  # comparten extremo: no es cruce
        if _segments_cross(a, b, pos[x], pos[y]):
            return True
    return False


def _move_keeps_planarity(v: Vertex, target: Position, pos: Dict[Vertex, Position],
                          adj: Dict[Vertex, List[Vertex]], edges: List[Tuple[Vertex, Vertex]]) -> bool:
    """True si al mover v a ``target`` ninguna de sus aristas incidentes cruza otra arista."""
    old = pos[v]
    pos[v] = target
    try:
        return not any(_segment_hits_any(target, pos[w], v, w, edges, pos) for w in adj[v])
    finally:
        pos[v] = old


def _closest_point(p: Position, a: Position, b: Position) -> Position:
    """Punto del segmento ab mas cercano a p."""
    abx, aby = b[0] - a[0], b[1] - a[1]
    denom = abx * abx + aby * aby
    if denom < MIN_DISTANCE:
        return a
    t = max(0.0, min(1.0, ((p[0] - a[0]) * abx + (p[1] - a[1]) * aby) / denom))
    return a[0] + t * abx, a[1] + t * aby


def _node_edge_repulsion(nodes: List[Vertex], edges: List[Tuple[Vertex, Vertex]],
                         pos: Dict[Vertex, Position], disp: Dict[Vertex, List[float]], k: float) -> None:
    """Aleja cada vertice de las aristas no incidentes que tiene demasiado cerca: O(V * E)."""
    reach = NODE_EDGE_REACH * k
    for v in nodes:
        p = pos[v]
        for x, y in edges:
            if v in (x, y):
                continue
            c = _closest_point(p, pos[x], pos[y])
            dx, dy = p[0] - c[0], p[1] - c[1]
            d = max(MIN_DISTANCE, math.hypot(dx, dy))
            if d < reach:
                f = (reach - d) * (reach - d) / d
                disp[v][0] += dx / d * f
                disp[v][1] += dy / d * f


def refine_planar(pos: Dict[Vertex, Position], edges: List[Tuple[Vertex, Vertex]],
                  iterations: Optional[int] = None) -> Dict[Vertex, Position]:
    """
    Fruchterman-Reingold con restriccion de planaridad: parte de un dibujo plano y devuelve
    OTRO dibujo plano con los vertices mejor repartidos. No modifica ``pos`` (devuelve una copia).
    """
    if iterations is None:
        iterations = min(REFINE_ITERATIONS, REFINE_WORK_BUDGET // max(1, len(edges)) ** 2)
    nodes = list(pos)
    n = len(nodes)
    if n < MIN_NODES_FOR_TUTTE or iterations < REFINE_MIN_ITERATIONS:
        return dict(pos)
    cur = dict(pos)
    adj: Dict[Vertex, List[Vertex]] = {v: [] for v in nodes}
    for u, w in edges:
        adj[u].append(w)
        adj[w].append(u)
    xs = [p[0] for p in cur.values()]
    ys = [p[1] for p in cur.values()]
    area = max(MIN_DISTANCE, (max(xs) - min(xs)) * (max(ys) - min(ys)))
    k = math.sqrt(area / n)                          # distancia ideal entre vertices
    temp = k
    for _ in range(iterations):
        disp = {v: [0.0, 0.0] for v in nodes}
        for i in range(n):                           # repulsion entre todo par: O(V^2)
            a = nodes[i]
            for j in range(i + 1, n):
                b = nodes[j]
                dx, dy = cur[a][0] - cur[b][0], cur[a][1] - cur[b][1]
                d = max(MIN_DISTANCE, math.hypot(dx, dy))
                f = k * k / d
                disp[a][0] += dx / d * f
                disp[a][1] += dy / d * f
                disp[b][0] -= dx / d * f
                disp[b][1] -= dy / d * f
        for u, w in edges:                           # atraccion por las aristas: O(E)
            dx, dy = cur[u][0] - cur[w][0], cur[u][1] - cur[w][1]
            d = max(MIN_DISTANCE, math.hypot(dx, dy))
            f = d * d / k
            disp[u][0] -= dx / d * f
            disp[u][1] -= dy / d * f
            disp[w][0] += dx / d * f
            disp[w][1] += dy / d * f
        _node_edge_repulsion(nodes, edges, cur, disp, k)
        for v in nodes:                              # paso acotado por la "temperatura"
            dx, dy = disp[v]
            d = max(MIN_DISTANCE, math.hypot(dx, dy))
            step = min(d, temp)
            for _ in range(BACKTRACK_STEPS):         # backtracking: paso mas corto si cruzaria
                target = (cur[v][0] + dx / d * step, cur[v][1] + dy / d * step)
                if _move_keeps_planarity(v, target, cur, adj, edges):
                    cur[v] = target
                    break
                step /= 2
        temp *= COOLING
    return cur


def _component_positions(sub: nx.Graph, refine: bool) -> Dict[Vertex, Position]:
    nodes = list(sub.nodes)
    if len(nodes) < MIN_NODES_FOR_TUTTE:
        return _small_layout(nodes)
    ok, emb = nx.check_planarity(sub)
    if not ok:
        raise ValueError("El grafo no es plano: planarizelo antes de dibujarlo")
    pos = tutte_positions(emb)
    return refine_planar(pos, list(sub.edges)) if refine else pos


def _pack_horizontally(parts: List[Dict[Vertex, Position]]) -> Dict[Vertex, Position]:
    """Coloca las componentes una al lado de la otra (la mas grande primero)."""
    out: Dict[Vertex, Position] = {}
    cursor = 0.0
    for part in sorted(parts, key=len, reverse=True):
        xs = [p[0] for p in part.values()]
        ys = [p[1] for p in part.values()]
        x0, x1 = min(xs), max(xs)
        cy = (min(ys) + max(ys)) / 2
        shift = cursor - x0
        for v, (x, y) in part.items():
            out[v] = (x + shift, y - cy)
        cursor += (x1 - x0) + COMPONENT_GAP
    return out


def planar_drawing(graph: Graph, fallback: Optional[Dict[Vertex, Position]] = None,
                   refine: bool = True) -> Dict[Vertex, Position]:
    """
    Posiciones sin cruces y legibles para un grafo PLANO (cada componente con Tutte y, si
    ``refine``, el refinamiento por fuerzas que preserva la planaridad).

    ``fallback``: dibujo plano ya conocido (p. ej. el de rejilla de ``check_planarity``) que se
    devuelve si la verificacion independiente detectara algun cruce en el dibujo de Tutte.
    """
    from .planarity import count_crossings          # import diferido: evita el ciclo de modulos

    if graph.num_vertices == 0:
        return {}
    nxg = graph.to_networkx()
    parts = [_component_positions(nxg.subgraph(c).copy(), refine) for c in nx.connected_components(nxg)]
    pos = _pack_horizontally(parts)
    if fallback is not None and count_crossings(pos, graph.edges) > 0:
        return dict(fallback)
    return pos
