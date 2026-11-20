"""
Grafos planos y diagramacion de arquitectura (sin cruces de aristas).

Contenido
---------
check_planarity(graph)    Test de planaridad (networkx: Left-Right / Boyer-Myrvold, O(V)).
                          Si es plano -> posiciones (x, y) de un *planar embedding*
                          (dibujo con segmentos rectos, algoritmo de de Fraysseix-Pach-Pollack).
                          Si no       -> certificado de Kuratowski: subdivision de K5 o K3,3.
count_crossings(...)      Verificador independiente: cuenta cruces entre segmentos de un dibujo.
planarize(graph)          Reduccion de cruces para grafos NO planos:
                              1. se construye un subgrafo plano maximal (voraz),
                              2. cada arista restante se inserta recorriendo el GRAFO DUAL del
                                 embedding (camino de menos caras cruzadas),
                              3. cada cruce se reemplaza por un NODO VIRTUAL (de grado 4).
                          El resultado es un grafo plano con posiciones sin cruces.

Complejidades (V vertices, E aristas, c = aristas que requieren cruces):
    check_planarity   O(V + E)  (E <= 3V - 6 si es plano)
    planarize         O((c + log E) * (V + E))  con la busqueda galopante del subgrafo plano
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx

from .graph import Graph, Vertex

Position = Tuple[float, float]


# =============================================================================
# Utilidades geometricas
# =============================================================================
def _orient(a: Position, b: Position, c: Position) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _segments_cross(p1: Position, p2: Position, p3: Position, p4: Position) -> bool:
    """True si los segmentos p1p2 y p3p4 se intersecan en un punto interior comun
    (los segmentos que solo comparten un extremo NO se consideran cruzados)."""
    d1, d2 = _orient(p3, p4, p1), _orient(p3, p4, p2)
    d3, d4 = _orient(p1, p2, p3), _orient(p1, p2, p4)
    if ((d1 > 0 > d2) or (d1 < 0 < d2)) and ((d3 > 0 > d4) or (d3 < 0 < d4)):
        return True
    return False


def count_crossings(positions: Dict[Vertex, Position], edges: List[Tuple[Vertex, Vertex]]) -> int:
    """
    Numero de pares de aristas que se cruzan en el dibujo. Barrido por coordenada x:
    O(E log E + P) con P = pares con intervalos en x solapados (O(E^2) en el peor caso).
    Verificador independiente del algoritmo de embedding.
    """
    segs = []
    for u, v in edges:
        a, b = positions[u], positions[v]
        if a[0] > b[0]:
            a, b = b, a
        segs.append((a[0], b[0], u, v, a, b))
    segs.sort(key=lambda s: s[0])
    active: List = []
    crossings = 0
    for s in segs:
        x0 = s[0]
        active = [t for t in active if t[1] >= x0]
        for t in active:
            if len({s[2], s[3], t[2], t[3]}) < 4:       # comparten un extremo
                continue
            if _segments_cross(s[4], s[5], t[4], t[5]):
                crossings += 1
        active.append(s)
    return crossings


# =============================================================================
# Test de planaridad + embedding + testigo de Kuratowski
# =============================================================================
@dataclass
class PlanarityResult:
    is_planar: bool
    positions: Optional[Dict[Vertex, Position]] = None       # solo si es plano
    embedding: Optional[nx.PlanarEmbedding] = None           # solo si es plano
    witness_kind: Optional[str] = None                       # "K5" | "K3,3" (subdivision)
    witness_edges: List[Tuple[Vertex, Vertex]] = field(default_factory=list)
    witness_branch_vertices: List[Vertex] = field(default_factory=list)
    euler_bound_exceeded: bool = False                       # E > 3V - 6


def _positions_from_embedding(emb: nx.PlanarEmbedding) -> Dict[Vertex, Position]:
    n = emb.number_of_nodes()
    if n == 0:
        return {}
    if n == 1:
        return {next(iter(emb.nodes)): (0, 0)}
    if n == 2:
        a, b = list(emb.nodes)
        return {a: (0, 0), b: (1, 0)}
    pos = nx.combinatorial_embedding_to_pos(emb)
    return {v: (float(x), float(y)) for v, (x, y) in pos.items()}


def _classify_witness(edges: List[Tuple[Vertex, Vertex]]) -> Tuple[str, List[Vertex]]:
    """El testigo es una subdivision: los vertices de grado >= 3 son los 'branch vertices'."""
    sub = nx.Graph(edges)
    branch = [v for v, d in sub.degree() if d >= 3]
    return ("K5" if len(branch) == 5 else "K3,3"), branch


def _planar_edges(edges: List[Tuple[Vertex, Vertex]]) -> bool:
    return nx.check_planarity(nx.Graph(edges))[0]


def _quickxplain(background: List, has_delta: bool, cands: List) -> List:
    """QuickXplain (Junker, 2004): subconjunto minimal de ``cands`` que, unido a
    ``background`` (plano), vuelve no plano el grafo. O(k log(|cands|/k)) tests."""
    if has_delta and not _planar_edges(background):
        return []
    if len(cands) == 1:
        return list(cands)
    mid = len(cands) // 2
    c1, c2 = cands[:mid], cands[mid:]
    d2 = _quickxplain(background + c1, bool(c1), c2)
    d1 = _quickxplain(background + d2, bool(d2), c1)
    return d1 + d2


def kuratowski_witness(graph: Graph) -> Tuple[str, List[Tuple[Vertex, Vertex]], List[Vertex]]:
    """
    Certificado de no planaridad (Teorema de Kuratowski): subgrafo MINIMAL no plano, que
    es una subdivision de K5 o de K3,3. Devuelve (tipo, aristas, branch_vertices).

    Se restringe a las primeras 3V-5 aristas cuando E >= 3V-5 (todo grafo simple con
    esa cantidad de aristas ya es no plano), de modo que escala a grafos densos.
    """
    edges = list(graph.edges)
    n = graph.num_vertices
    if n >= 3 and len(edges) >= 3 * n - 5:
        edges = edges[:3 * n - 5]
    if _planar_edges(edges):
        raise ValueError("El grafo es plano: no hay certificado de Kuratowski")
    witness = _quickxplain([], False, edges)
    kind, branch = _classify_witness(witness)
    return kind, witness, branch


def check_planarity(graph: Graph, with_positions: bool = True, with_witness: bool = True) -> PlanarityResult:
    """Decide si ``graph`` es plano. Ver docstring del modulo."""
    n, m = graph.num_vertices, graph.num_edges
    euler = n >= 3 and m > 3 * n - 6
    ok, emb = nx.check_planarity(graph.to_networkx(), counterexample=False)
    if ok:
        pos = _positions_from_embedding(emb) if with_positions else None
        return PlanarityResult(True, positions=pos, embedding=emb)
    res = PlanarityResult(False, euler_bound_exceeded=euler)
    if with_witness:
        res.witness_kind, res.witness_edges, res.witness_branch_vertices = kuratowski_witness(graph)
    return res


# =============================================================================
# Planarizacion (reduccion de cruces con nodos virtuales)
# =============================================================================
class _RerouteConflict(Exception):
    """Un paso de rip-up & reroute no puede deshacerse sin crear una multiarista."""


@dataclass
class PlanarizationResult:
    graph: Graph                                   # grafo planarizado (reales + virtuales)
    positions: Dict[Vertex, Position]
    virtual_nodes: List[Vertex]
    num_crossings: int
    edge_paths: Dict[Tuple[Vertex, Vertex], List[Vertex]]   # arista original -> camino con virtuales
    was_planar: bool
    unrouted_edges: List[Tuple[Vertex, Vertex]] = field(default_factory=list)  # si se agoto el tiempo
    elapsed: float = 0.0


def _faces(emb: nx.PlanarEmbedding):
    """Caras del embedding: lista de listas de vertices y mapa semiarista -> id de cara. O(V + E)."""
    faces: List[List[Vertex]] = []
    face_of: Dict[Tuple[Vertex, Vertex], int] = {}
    seen = set()
    for a, b in list(emb.edges()):
        if (a, b) in seen:
            continue
        nodes = emb.traverse_face(a, b, mark_half_edges=seen)
        fid = len(faces)
        faces.append(nodes)
        for i, x in enumerate(nodes):
            face_of[(x, nodes[(i + 1) % len(nodes)])] = fid
    return faces, face_of


def _dual_route(emb: nx.PlanarEmbedding, u: Vertex, v: Vertex) -> List[Tuple[Vertex, Vertex]]:
    """
    Camino minimo en el grafo dual desde alguna cara incidente a u hasta alguna
    incidente a v. Devuelve la lista ordenada de aristas del primal que hay que
    CRUZAR (cada una se vuelve un cruce). BFS multi-fuente: O(V + E).
    """
    faces, face_of = _faces(emb)
    src = {face_of[(u, w)] for w in emb.successors(u)}
    dst = {face_of[(v, w)] for w in emb.successors(v)}
    if src & dst:
        return []                                   # comparten cara: sin cruces
    parent: Dict[int, Optional[Tuple[int, Tuple[Vertex, Vertex]]]] = {f: None for f in src}
    queue = list(src)
    head = 0
    while head < len(queue):
        f = queue[head]
        head += 1
        if f in dst:
            path = []
            while parent[f] is not None:
                f, edge = parent[f]
                path.append(edge)
            return path[::-1]
        nodes = faces[f]
        for i, a in enumerate(nodes):
            b = nodes[(i + 1) % len(nodes)]
            g = face_of[(b, a)]                      # cara al otro lado de la arista {a, b}
            if g not in parent:
                parent[g] = (f, (a, b))
                queue.append(g)
    raise RuntimeError("Sin ruta en el dual (el grafo deberia estar conectado en esa componente)")


def _insertion_order(graph: Graph) -> List[Tuple[Vertex, Vertex]]:
    """
    Orden de insercion de las aristas para el subgrafo plano voraz.

    Prioridad: aristas que cierran MAS TRIANGULOS primero (las que forman la estructura planar
    densa suelen estar en triangulos; las aristas "largas" que causan la no planaridad, en pocos),
    luego menor suma de grados. Primero va un bosque generador (siempre plano) elegido con esa misma
    prioridad (Kruskal), y despues el resto. O(E * d) por los conteos de triangulos.
    """
    index = {v: i for i, v in enumerate(graph.vertices)}
    nbr = {v: set(graph.neighbors(v)) for v in graph.vertices}
    prio = {}
    for u, v in graph.edges:
        tri = len(nbr[u] & nbr[v])
        prio[(u, v)] = (-tri, graph.degree(u) + graph.degree(v), index[u], index[v])
    ordered = sorted(prio, key=prio.get)

    parent = {v: v for v in graph.vertices}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    tree, rest = [], []
    for u, v in ordered:
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[ru] = rv
            tree.append((u, v))
        else:
            rest.append((u, v))
    return tree + rest


def planarize(graph: Graph, virtual_prefix: str = "__x", time_limit: Optional[float] = None,
              improve_passes: int = 3) -> PlanarizationResult:
    """
    Convierte ``graph`` en un grafo plano insertando nodos virtuales en los cruces.

    1. Subgrafo plano maximal voraz (orden por triangulos; busqueda galopante + biseccion:
       O(log E) tests de planaridad por tramo en lugar de uno por arista).
    2. Cada arista restante se inserta por el DUAL del embedding actual (camino con menos
       caras cruzadas); cada cruce se reemplaza por un nodo virtual de grado 4.
    3. Mejora ("rip-up & reroute", ``improve_passes`` pasadas): se quita una arista cruzada, se
       recalcula el embedding y se la reinserta por el dual; se conserva solo si baja los cruces.

    Si el grafo ya es plano devuelve el mismo grafo sin nodos virtuales. ``time_limit`` (segundos)
    acota el trabajo: lo que no alcance a insertarse queda en ``unrouted_edges`` (el dibujo es plano
    pero incompleto). El numero minimo de cruces (crossing number) es NP-dificil: esto es heuristica.
    """
    t0 = time.perf_counter()

    def out_of_time() -> bool:
        return time_limit is not None and time.perf_counter() - t0 > time_limit

    base = check_planarity(graph)
    if base.is_planar:
        edge_paths = {(u, v): [u, v] for u, v in graph.edges}
        return PlanarizationResult(graph.copy(), base.positions or {}, [], 0, edge_paths, True,
                                   elapsed=time.perf_counter() - t0)

    index = {v: i for i, v in enumerate(graph.vertices)}
    canon = lambda u, v: (u, v) if index[u] <= index[v] else (v, u)

    H = nx.Graph()
    H.add_nodes_from(graph.vertices)
    owner: Dict[frozenset, Tuple[Vertex, Vertex]] = {}     # segmento -> arista original
    paths: Dict[Tuple[Vertex, Vertex], List[Vertex]] = {}  # arista original -> camino
    virtual: Dict[Vertex, None] = {}                       # nodos virtuales (conjunto ordenado)
    counter = [0]
    unrouted: List[Tuple[Vertex, Vertex]] = []

    def add_direct(u, v):
        H.add_edge(u, v)
        owner[frozenset((u, v))] = (u, v)
        paths[(u, v)] = [u, v]

    def planar_with(chunk) -> Tuple[bool, Optional[nx.PlanarEmbedding]]:
        H.add_edges_from(chunk)
        ok, e = nx.check_planarity(H)
        H.remove_edges_from(chunk)
        return ok, e

    def insert_with_crossings(u, v, emb) -> int:
        """Inserta (u, v) cruzando las aristas del camino minimo del dual. Devuelve #cruces."""
        crossed = _dual_route(emb, u, v)
        prev, new_path = u, [u]
        for (a, b) in crossed:
            x = f"{virtual_prefix}{counter[0]}"
            counter[0] += 1
            virtual[x] = None
            orig = owner.pop(frozenset((a, b)))
            H.remove_edge(a, b)
            for s_, t_ in ((a, x), (x, b)):
                H.add_edge(s_, t_)
                owner[frozenset((s_, t_))] = orig
            p = paths[orig]                              # insertar x entre a y b en el camino
            for i in range(len(p) - 1):
                if {p[i], p[i + 1]} == {a, b}:
                    p.insert(i + 1, x)
                    break
            H.add_edge(prev, x)
            owner[frozenset((prev, x))] = (u, v)
            new_path.append(x)
            prev = x
        H.add_edge(prev, v)
        owner[frozenset((prev, v))] = (u, v)
        new_path.append(v)
        paths[(u, v)] = new_path
        return len(crossed)

    # ------------------------------------------------- fases 1 y 2: subgrafo plano + insercion por dual
    remaining = [canon(u, v) for u, v in _insertion_order(graph)]
    _, emb = nx.check_planarity(H)
    while remaining:
        if out_of_time():
            unrouted = remaining
            break
        ok, e_all = planar_with(remaining)
        if ok:                                           # todo lo que queda cabe sin cruces
            for u, v in remaining:
                add_direct(u, v)
            remaining = []
            break
        lo, hi, step, emb_lo = 0, len(remaining), 1, emb   # lo factible, hi infactible
        while lo + step < hi:                            # fase galopante
            ok, e = planar_with(remaining[:lo + step])
            if not ok:
                hi = lo + step
                break
            lo, emb_lo = lo + step, e
            step *= 2
        while hi - lo > 1:                               # biseccion en (lo, hi)
            mid = (lo + hi) // 2
            ok, e = planar_with(remaining[:mid])
            if ok:
                lo, emb_lo = mid, e
            else:
                hi = mid
        for u, v in remaining[:lo]:
            add_direct(u, v)
        u, v = remaining[lo]                             # primera arista que exige cruces
        remaining = remaining[lo + 1:]
        insert_with_crossings(u, v, emb_lo)
        ok, emb = nx.check_planarity(H)
        if not ok:
            raise RuntimeError("Error interno: la planarizacion no produjo un grafo plano")

    # ------------------------------------------------- fase 3: rip-up & reroute
    def remove_original(key) -> None:
        path = paths.pop(key)
        for a, b in zip(path, path[1:]):
            H.remove_edge(a, b)
            owner.pop(frozenset((a, b)))
        for x in path[1:-1]:                             # x queda con los 2 segmentos de la arista cruzada f
            nbrs = list(H.neighbors(x))
            if len(nbrs) != 2 or H.has_edge(*nbrs):
                # Deshacer el cruce recrearia una arista que ya existe (dos tramos paralelos entre los
                # mismos vertices): nx.Graph los fusionaria y se perderia un tramo. Se aborta este reroute.
                raise _RerouteConflict
            a, b = nbrs
            f = owner.pop(frozenset((a, x)))
            owner.pop(frozenset((x, b)))
            H.remove_node(x)
            H.add_edge(a, b)
            owner[frozenset((a, b))] = f
            paths[f].remove(x)
            del virtual[x]

    for _ in range(improve_passes if not unrouted else 0):
        improved = False
        for key in sorted((k for k, p in paths.items() if len(p) > 2), key=lambda k: -len(paths[k])):
            if out_of_time() or key not in paths or len(paths[key]) <= 2:
                continue
            snap = (H.copy(), dict(owner), {k: list(p) for k, p in paths.items()}, dict(virtual))
            old = len(paths[key]) - 2
            u, v = key
            try:
                remove_original(key)
            except _RerouteConflict:
                H, owner, paths, virtual = snap
                continue
            _, emb = nx.check_planarity(H)
            H.add_edge(u, v)
            ok, _ = nx.check_planarity(H)
            if ok:
                H.remove_edge(u, v)
                add_direct(u, v)
                new = 0
            else:
                H.remove_edge(u, v)
                new = insert_with_crossings(u, v, emb)
            if new < old:
                improved = True
            else:                                        # no mejora: restaurar estado previo
                H, owner, paths, virtual = snap
        if not improved:
            break

    ok, emb = nx.check_planarity(H)
    if not ok:
        raise RuntimeError("Error interno: la planarizacion no produjo un grafo plano")
    out = Graph()
    for v in graph.vertices:
        out.add_vertex(v, **graph.vertex_attrs(v))
    for x in virtual:
        out.add_vertex(x, virtual=True)
    for a, b in H.edges():
        orig = owner[frozenset((a, b))]
        attrs = dict(graph.edge_attrs(*orig))
        attrs["original_edge"] = list(orig)
        out.add_edge(a, b, **attrs)
    positions = _positions_from_embedding(emb)
    return PlanarizationResult(out, positions, list(virtual), len(virtual), paths, False,
                               unrouted_edges=unrouted, elapsed=time.perf_counter() - t0)
