import itertools
import random

import networkx as nx
import pytest

from graph_core import (Graph, chromatic_bounds, clique_lower_bound, color_graph, dsatur,
                        exact_chromatic_number, greedy_clique, is_valid_coloring, welsh_powell)

ALGOS = [dsatur, welsh_powell]


def G(nxg):
    return Graph.from_networkx(nxg)


@pytest.mark.parametrize("algo", ALGOS)
def test_random_graphs_always_valid_and_within_delta_plus_one(algo):
    for seed in range(25):
        g = G(nx.gnp_random_graph(40, random.Random(seed).choice([0.05, 0.2, 0.5]), seed=seed))
        r = algo(g)
        assert r.valid and is_valid_coloring(g, r.colors)
        max_deg = max((g.degree(v) for v in g), default=0)
        assert r.num_colors <= max_deg + 1                     # cota de Brooks/voraz


@pytest.mark.parametrize("algo", ALGOS)
def test_known_graphs(algo):
    assert algo(Graph()).num_colors == 0
    assert algo(Graph(vertices=[1, 2, 3])).num_colors == 1
    assert algo(G(nx.complete_graph(7))).num_colors == 7
    assert algo(G(nx.cycle_graph(7))).num_colors <= 3


def test_dsatur_is_exact_on_bipartite_cycles_and_wheels():
    assert dsatur(G(nx.complete_bipartite_graph(5, 6))).num_colors == 2
    assert dsatur(G(nx.grid_2d_graph(8, 8))).num_colors == 2
    assert dsatur(G(nx.cycle_graph(8))).num_colors == 2
    assert dsatur(G(nx.cycle_graph(9))).num_colors == 3
    assert dsatur(G(nx.wheel_graph(9))).num_colors == 3          # rueda con hub + ciclo par
    assert dsatur(G(nx.wheel_graph(8))).num_colors == 4          # rueda con ciclo impar


def test_dsatur_is_deterministic():
    g = G(nx.gnp_random_graph(60, 0.2, seed=3))
    assert dsatur(g).colors == dsatur(g).colors


def _brute_force_chi(g: Graph) -> int:
    vs = g.vertices
    for k in range(1, len(vs) + 1):
        for assign in itertools.product(range(k), repeat=len(vs)):
            col = dict(zip(vs, assign))
            if all(col[u] != col[v] for u, v in g.edges):
                return k
    return 0


def test_exact_chromatic_number_matches_brute_force():
    for seed in range(12):
        g = G(nx.gnp_random_graph(7, 0.5, seed=seed))
        assert exact_chromatic_number(g) == _brute_force_chi(g)


def test_known_chromatic_numbers():
    assert exact_chromatic_number(G(nx.petersen_graph())) == 3
    assert exact_chromatic_number(G(nx.complete_graph(6))) == 6
    assert exact_chromatic_number(G(nx.mycielski_graph(4))) == 4        # Grotzsch: omega=2, chi=4
    assert exact_chromatic_number(Graph()) == 0


def test_bounds_are_ordered_and_clique_is_a_clique():
    for seed in range(10):
        g = G(nx.gnp_random_graph(30, 0.3, seed=seed))
        b = chromatic_bounds(g, try_exact=False)
        assert b["lower"] <= b["upper"]
        cl = greedy_clique(g)
        assert all(g.has_edge(u, v) for u, v in itertools.combinations(cl, 2))
        assert clique_lower_bound(g) == len(cl)
        assert len(cl) <= dsatur(g).num_colors


def test_exact_gives_up_on_big_graphs():
    assert exact_chromatic_number(G(nx.gnp_random_graph(200, 0.1, seed=1)), max_vertices=60) is None


def test_batches_partition_vertices():
    g = G(nx.gnp_random_graph(25, 0.3, seed=9))
    r = color_graph(g, "welsh_powell")
    flat = [v for batch in r.batch_list() for v in batch]
    assert sorted(flat) == sorted(g.vertices)
    with pytest.raises(ValueError):
        color_graph(g, "nope")


def test_invalid_coloring_detected():
    g = Graph(edges=[("a", "b")])
    assert not is_valid_coloring(g, {"a": 0, "b": 0})
    assert not is_valid_coloring(g, {"a": 0})
