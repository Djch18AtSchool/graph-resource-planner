"""Dibujo plano de Tutte + refinamiento: siempre 0 cruces y vertices bien separados."""
import math
import random

import networkx as nx
import pytest

from graph_core import Graph, count_crossings, planar_drawing, planarize, tutte_positions
from graph_core.drawing import refine_planar


def apollonian(n, seed):
    rng = random.Random(seed)
    g = nx.Graph([(0, 1), (1, 2), (0, 2)])
    faces = [(0, 1, 2), (0, 1, 2)]
    for v in range(3, n):
        a, b, c = faces.pop(rng.randrange(len(faces)))
        g.add_edges_from([(v, a), (v, b), (v, c)])
        faces += [(a, b, v), (b, c, v), (a, c, v)]
    return g


PLANAR = {
    "arbol": nx.random_labeled_tree(25, seed=2), "ciclo": nx.cycle_graph(9), "rueda": nx.wheel_graph(10),
    "grilla": nx.grid_2d_graph(5, 5), "triangulacion": apollonian(40, 1), "estrella": nx.star_graph(8),
    "desconectado": nx.disjoint_union_all([nx.cycle_graph(5), nx.path_graph(2), nx.empty_graph(1), nx.complete_graph(4)]),
}


@pytest.mark.parametrize("name", sorted(PLANAR))
def test_planar_drawing_has_no_crossings_and_distinct_points(name):
    g = Graph.from_networkx(PLANAR[name])
    pos = planar_drawing(g)
    assert set(pos) == set(g.vertices)
    assert count_crossings(pos, g.edges) == 0
    points = list(pos.values())
    assert len({(round(x, 9), round(y, 9)) for x, y in points}) == len(points)     # sin vertices encimados


def test_tutte_places_inner_vertex_at_barycenter():
    # rueda: el centro es el unico vertice interno -> queda en el baricentro de la cara externa
    ok, emb = nx.check_planarity(nx.wheel_graph(7))
    pos = tutte_positions(emb)
    cx, cy = pos[0]
    rim = [pos[v] for v in range(1, 7)]
    assert math.isclose(cx, sum(p[0] for p in rim) / 6, abs_tol=1e-9)
    assert math.isclose(cy, sum(p[1] for p in rim) / 6, abs_tol=1e-9)


@pytest.mark.parametrize("graph", [nx.complete_graph(6), nx.complete_bipartite_graph(3, 4), nx.petersen_graph()])
def test_drawing_of_planarized_nonplanar_graph_has_no_crossings(graph):
    res = planarize(Graph.from_networkx(graph))
    pos = planar_drawing(res.graph, fallback=res.positions)
    assert count_crossings(pos, res.graph.edges) == 0


def test_refinement_never_creates_crossings_and_keeps_input_intact():
    g = Graph.from_networkx(apollonian(30, 5))
    _, emb = nx.check_planarity(g.to_networkx())
    start = tutte_positions(emb)
    snapshot = dict(start)
    refined = refine_planar(start, g.edges, iterations=40)
    assert start == snapshot                                                   # no muta la entrada
    assert count_crossings(refined, g.edges) == 0


def test_drawing_rejects_nonplanar_without_planarization():
    with pytest.raises(ValueError, match="no es plano"):
        planar_drawing(Graph.from_networkx(nx.complete_graph(5)))


def test_fallback_is_used_when_verification_fails(monkeypatch):
    import graph_core.drawing as drawing
    g = Graph.from_networkx(nx.cycle_graph(6))
    fallback = {v: (float(v), 0.0) for v in g.vertices}
    monkeypatch.setattr("graph_core.planarity.count_crossings", lambda pos, edges: 1)
    assert drawing.planar_drawing(g, fallback=fallback) == fallback
    assert planar_drawing(Graph()) == {}
