import random

import networkx as nx
import pytest

from graph_core import Graph, GraphError


def test_basic_operations_keep_both_representations_in_sync():
    g = Graph(edges=[("a", "b"), ("b", "c"), ("c", "a"), ("c", "d")])
    assert (g.num_vertices, g.num_edges) == (4, 4)
    assert g.is_consistent()
    g.remove_vertex("a")
    assert g.is_consistent()
    assert sorted(g.vertices) == ["b", "c", "d"] and g.num_edges == 2
    g.remove_edge("b", "c")
    assert g.is_consistent() and not g.has_edge("b", "c") and not g.has_edge("b", "c", backend="matrix")


def test_backends_agree_on_queries():
    g = Graph(edges=[(1, 2), (1, 3), (2, 3), (3, 4)])
    for v in g.vertices:
        assert g.degree(v) == g.degree(v, "matrix")
        assert sorted(g.neighbors(v)) == sorted(g.neighbors(v, "matrix"))
    assert g.degrees() == g.degrees("matrix")


def test_rejects_self_loops_and_unknown_vertices():
    g = Graph(vertices=["x"])
    with pytest.raises(GraphError):
        g.add_edge("x", "x")
    with pytest.raises(GraphError):
        g.degree("nope")
    with pytest.raises(GraphError):
        g.remove_vertex("nope")


def test_add_edge_is_idempotent():
    g = Graph()
    g.add_edge("a", "b")
    g.add_edge("b", "a")
    assert g.num_edges == 1 and g.is_consistent()


def test_fuzz_against_networkx():
    """Operaciones aleatorias: Graph (lista+matriz) debe coincidir siempre con networkx."""
    rng = random.Random(42)
    g, ref = Graph(), nx.Graph()
    for step in range(1500):
        op = rng.choice(["av", "ae", "ae", "ae", "re", "rv"])
        if op == "av":
            v = rng.randrange(40)
            g.add_vertex(v)
            ref.add_node(v)
        elif op == "ae":
            u, v = rng.randrange(40), rng.randrange(40)
            if u != v:
                g.add_edge(u, v)
                ref.add_edge(u, v)
        elif op == "re" and ref.number_of_edges():
            u, v = rng.choice(list(ref.edges))
            g.remove_edge(u, v)
            ref.remove_edge(u, v)
        elif op == "rv" and ref.number_of_nodes():
            v = rng.choice(list(ref.nodes))
            g.remove_vertex(v)
            ref.remove_node(v)
        if step % 50 == 0:
            assert g.is_consistent()
    assert g.is_consistent()
    assert set(g.vertices) == set(ref.nodes)
    assert {frozenset(e) for e in g.edges} == {frozenset(e) for e in ref.edges}
    assert g.num_edges == ref.number_of_edges()
    assert g.degrees() == dict(ref.degree)


def test_json_and_networkx_roundtrip():
    g = Graph()
    g.add_vertex("a", label="Servicio A")
    g.add_edge("a", "b", kind="conflict")
    h = Graph.from_json(g.to_json())
    assert h.vertices == g.vertices and h.edges == g.edges
    assert h.vertex_attrs("a")["label"] == "Servicio A"
    assert h.edge_attrs("a", "b")["kind"] == "conflict"
    n = g.to_networkx()
    assert n.nodes["a"]["label"] == "Servicio A" and n.edges["a", "b"]["kind"] == "conflict"
    assert Graph.from_networkx(n).edges == g.edges


def test_components_copy_subgraph():
    g = Graph(edges=[(1, 2), (3, 4)])
    g.add_vertex(5)
    assert sorted(map(sorted, g.connected_components())) == [[1, 2], [3, 4], [5]]
    c = g.copy()
    c.remove_vertex(1)
    assert g.num_vertices == 5
    assert g.subgraph([1, 2, 5]).num_edges == 1
