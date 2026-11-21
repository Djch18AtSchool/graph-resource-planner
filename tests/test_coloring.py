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


# ------------------------------------------------------------------ pasos (vista paso a paso)
@pytest.mark.parametrize("algo", ALGOS)
def test_steps_color_every_vertex_once_and_match_the_result(algo):
    g = G(nx.gnp_random_graph(30, 0.25, seed=4))
    r = algo(g)
    assert sorted(s.vertex for s in r.steps) == sorted(g.vertices)
    assert all(r.colors[s.vertex] == s.color for s in r.steps)


def test_dsatur_steps_record_saturation_at_selection_time():
    g = G(nx.gnp_random_graph(30, 0.25, seed=4))
    r = dsatur(g)
    first = r.steps[0]
    assert first.saturation == 0 and g.degree(first.vertex) == max(g.degree(v) for v in g)
    seen = {}
    for s in r.steps:
        assert s.saturation == len({seen[u] for u in g.neighbors(s.vertex) if u in seen})
        seen[s.vertex] = s.color


def test_welsh_powell_steps_go_round_by_round():
    r = welsh_powell(G(nx.gnp_random_graph(30, 0.25, seed=4)))
    colors = [s.color for s in r.steps]
    assert colors == sorted(colors) and all(s.saturation is None for s in r.steps)


def test_exact_search_budget_is_shared_across_components():
    import time
    from graph_core.generators import random_edges
    g = Graph()
    for k in range(12):                                       # 12 componentes dificiles de 60 vertices
        for u, v in random_edges(60, int(0.6 * 60 * 59 / 2), seed=2):
            g.add_edge((k, u), (k, v))
    t0 = time.perf_counter()
    exact_chromatic_number(g, node_limit=20_000)
    assert time.perf_counter() - t0 < 5


def test_greedy_clique_finds_the_whole_complete_graph_quickly():
    assert len(greedy_clique(G(nx.complete_graph(400)))) == 400
