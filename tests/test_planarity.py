import random

import networkx as nx
import pytest

from graph_core import Graph, check_planarity, count_crossings, kuratowski_witness, planarize


def G(nxg):
    return Graph.from_networkx(nxg)


def random_planar_triangulation(n, seed):
    """Apolonica: inserta cada vertice nuevo dentro de una cara triangular al azar."""
    rng = random.Random(seed)
    g = nx.Graph([(0, 1), (1, 2), (0, 2)])
    faces = [(0, 1, 2), (0, 1, 2)]
    for v in range(3, n):
        a, b, c = faces.pop(rng.randrange(len(faces)))
        g.add_edges_from([(v, a), (v, b), (v, c)])
        faces += [(a, b, v), (b, c, v), (a, c, v)]
    return g


@pytest.mark.parametrize("name,graph", [
    ("arbol", nx.random_labeled_tree(30, seed=1)), ("K4", nx.complete_graph(4)),
    ("grilla", nx.grid_2d_graph(6, 6)), ("rueda", nx.wheel_graph(12)),
    ("triangulacion", random_planar_triangulation(60, 3)), ("vacio", nx.empty_graph(5)),
    ("desconectado", nx.disjoint_union(nx.grid_2d_graph(3, 3), nx.complete_graph(4))),
])
def test_planar_graphs_get_crossing_free_positions(name, graph):
    g = G(graph)
    r = check_planarity(g)
    assert r.is_planar and r.witness_kind is None
    assert set(r.positions) == set(g.vertices)
    assert count_crossings(r.positions, g.edges) == 0


@pytest.mark.parametrize("graph,kind", [
    (nx.complete_graph(5), "K5"), (nx.complete_bipartite_graph(3, 3), "K3,3"),
    (nx.petersen_graph(), "K3,3"),
])
def test_nonplanar_graphs_give_minimal_kuratowski_certificate(graph, kind):
    g = G(graph)
    r = check_planarity(g)
    assert not r.is_planar and r.positions is None
    assert r.witness_kind == kind
    assert len(r.witness_branch_vertices) == (5 if kind == "K5" else 6)
    w = r.witness_edges
    assert not nx.check_planarity(nx.Graph(w))[0]                              # es no plano
    assert all(nx.check_planarity(nx.Graph([e for e in w if e != x]))[0] for x in w)   # y minimal


def test_agrees_with_networkx_on_random_graphs():
    for seed in range(40):
        n, m = 12, random.Random(seed).randint(8, 40)
        graph = nx.gnm_random_graph(n, m, seed=seed)
        assert check_planarity(G(graph), with_positions=False).is_planar == nx.check_planarity(graph)[0]


def test_euler_bound_flag_and_dense_witness():
    r = check_planarity(G(nx.complete_graph(12)))
    assert r.euler_bound_exceeded and r.witness_kind in {"K5", "K3,3"}
    with pytest.raises(ValueError):
        kuratowski_witness(G(nx.grid_2d_graph(3, 3)))


def _assert_valid_planarization(original: Graph, res):
    out = res.graph
    assert check_planarity(out, with_positions=False).is_planar
    assert count_crossings(res.positions, out.edges) == 0
    assert res.num_crossings == len(res.virtual_nodes)
    assert all(out.vertex_attrs(x).get("virtual") for x in res.virtual_nodes)
    assert all(out.degree(x) == 4 for x in res.virtual_nodes)        # un cruce = grado 4
    assert {frozenset(e) for e in res.edge_paths} == {frozenset(e) for e in original.edges}
    for (u, v), path in res.edge_paths.items():
        assert {path[0], path[-1]} == {u, v}
        assert all(x in res.virtual_nodes for x in path[1:-1])
        assert all(out.has_edge(a, b) for a, b in zip(path, path[1:]))
    real = [x for x in out.vertices if x not in res.virtual_nodes]
    assert sorted(map(str, real)) == sorted(map(str, original.vertices))


def test_planarize_planar_graph_is_identity():
    g = G(nx.grid_2d_graph(4, 4))
    res = planarize(g)
    assert res.was_planar and res.num_crossings == 0
    assert {frozenset(e) for e in res.graph.edges} == {frozenset(e) for e in g.edges}


@pytest.mark.parametrize("graph,min_cross", [
    (nx.complete_graph(5), 1), (nx.complete_bipartite_graph(3, 3), 1), (nx.petersen_graph(), 2),
    (nx.complete_graph(6), 3), (nx.complete_graph(7), 9), (nx.gnm_random_graph(15, 40, seed=7), 1),
])
def test_planarize_nonplanar_graphs(graph, min_cross):
    g = G(graph)
    res = planarize(g)
    assert not res.was_planar and res.num_crossings >= min_cross       # cr(K5)=1, cr(K6)=3, cr(Petersen)=2
    _assert_valid_planarization(g, res)


def test_planarize_planar_plus_extra_edges_scales():
    base = random_planar_triangulation(120, 5)
    rng = random.Random(1)
    for _ in range(6):
        u, v = rng.sample(list(base.nodes), 2)
        base.add_edge(u, v)
    g = G(base)
    res = planarize(g)
    assert res.num_crossings <= 90          # heuristica; el orden por triangulos evita bloquear la estructura
    _assert_valid_planarization(g, res)


def test_planarize_time_limit_reports_unrouted_edges():
    g = G(nx.gnm_random_graph(40, 200, seed=3))
    res = planarize(g, time_limit=0.0)
    assert res.unrouted_edges                                          # nada se alcanzo a enrutar
    assert check_planarity(res.graph, with_positions=False).is_planar


def test_reinsertion_never_worsens_and_results_are_deterministic():
    g = G(nx.gnm_random_graph(14, 38, seed=11))
    a, b = planarize(g, improve_passes=0), planarize(g, improve_passes=3)
    assert b.num_crossings <= a.num_crossings
    _assert_valid_planarization(g, b)
    again = planarize(g, improve_passes=3)
    assert again.num_crossings == b.num_crossings and again.edge_paths == b.edge_paths


@pytest.mark.parametrize("n,seed", [(10, 38), (15, 15), (20, 15), (20, 19), (20, 23)])
def test_planarize_regression_reroute_cannot_create_multiedges(n, seed):
    """Antes, ~10% de los grafos aleatorios fallaban con ValueError en el rip-up & reroute."""
    from benchmarks.generators import random_edges
    g = Graph(vertices=range(n), edges=random_edges(n, int(2.5 * n), seed))
    res = planarize(g)
    assert check_planarity(res.graph, with_positions=False).is_planar
    assert count_crossings(res.positions, res.graph.edges) == 0
    assert {frozenset(k) for k in res.edge_paths} == {frozenset(e) for e in g.edges}
