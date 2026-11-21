"""Del problema de tareas al plan: grafo de conflictos, lotes, tiempos y cotas de chi(G)."""
import itertools

import pytest

from graph_core import is_valid_coloring
from graph_core.generators import random_problem, resource_problem
from graph_core.problem import parse_problem
from graph_core.scheduling import conflict_graph, plan

EXAM = """
titulo: Examenes
Calculo [2]: ana, beto
Fisica [1]: ana, carla
Discreta [3]: beto, carla
Ingles [1]: dani
Quimica [2]: dani, ana
"""


def test_tasks_sharing_a_resource_conflict_and_edges_record_the_shared_resources():
    g = conflict_graph(parse_problem(EXAM))
    assert g.num_vertices == 5
    assert g.has_edge("Calculo", "Fisica") and g.edge_attrs("Calculo", "Fisica")["resources"] == ["ana"]
    assert g.has_edge("Ingles", "Quimica")
    assert not g.has_edge("Ingles", "Calculo")
    assert g.vertex_attrs("Discreta")["duration"] == 3.0


def test_explicit_conflict_without_shared_resource_is_marked_explicit():
    g = conflict_graph(parse_problem("A: r\nB: s\nA -- B"))
    assert g.edge_attrs("A", "B") == {"resources": [], "explicit": True}


def test_explicit_conflict_on_already_conflicting_pair_keeps_resources():
    g = conflict_graph(parse_problem("A: r\nB: r\nA -- B"))
    assert g.edge_attrs("A", "B") == {"resources": ["r"], "explicit": True}


def test_plan_batches_are_independent_sets_and_cover_every_task():
    p = plan(parse_problem(EXAM))
    assert is_valid_coloring(p.graph, p.coloring.colors)
    names = [t for b in p.batches for t in b.tasks]
    assert sorted(names) == sorted(t.name for t in p.problem.tasks)
    for b in p.batches:
        assert all(not p.graph.has_edge(u, v) for u, v in itertools.combinations(b.tasks, 2))


def test_batch_times_makespan_and_workers():
    p = plan(parse_problem("A [2]: r\nB [5]: r\nC [1]: s"))
    # A y B comparten r -> 2 lotes; C cabe en cualquiera
    assert len(p.batches) == 2
    assert p.batches[0].start == 0 and p.batches[1].start == p.batches[0].duration
    assert p.makespan == sum(b.duration for b in p.batches)
    assert p.sequential_time == 8
    assert p.workers == max(len(b.tasks) for b in p.batches)
    assert p.speedup == pytest.approx(p.sequential_time / p.makespan)


def test_bounds_use_exact_chi_on_small_graphs_and_resource_clique():
    p = plan(parse_problem(EXAM))
    assert p.bounds["exact"] == 3 and p.bounds["lower"] == p.bounds["upper"] == 3
    # "ana" la usan 3 tareas -> forman un K3, al menos 3 lotes
    assert p.max_resource_usage == 3


def test_resource_clique_raises_the_lower_bound_when_exact_is_skipped():
    text = "\n".join(f"T{i}: gpu" for i in range(8))
    p = plan(parse_problem(text), try_exact=False)
    assert p.bounds["lower"] == 8 and p.bounds["exact"] == 8         # clique = heuristica -> optimo probado
    assert sorted(p.clique) == sorted(f"T{i}" for i in range(8))


def test_exact_stays_unknown_when_bounds_do_not_meet():
    # Grotzsch (Mycielski 4): clique 2, chi 4 -> sin branch & bound la cota no basta
    import networkx as nx
    from graph_core import Graph
    g = Graph.from_networkx(nx.mycielski_graph(4))
    text = "\n".join(f"V{v}" for v in g.vertices) + "\n" + "\n".join(f"V{u} -- V{v}" for u, v in g.edges)
    p = plan(parse_problem(text), try_exact=False)
    assert p.bounds["exact"] is None and p.bounds["lower"] < p.bounds["upper"]


def test_alternative_algorithm_is_the_other_one():
    p = plan(parse_problem(EXAM), "welsh_powell")
    assert p.coloring.algorithm == "welsh_powell" and p.alternative.algorithm == "dsatur"
    assert p.bounds["upper"] == min(p.coloring.num_colors, p.alternative.num_colors)


def test_tasks_without_conflicts_still_get_a_batch():
    p = plan(parse_problem("A\nB\nC"))
    assert len(p.batches) == 1 and p.workers == 3 and p.bounds["exact"] == 1


def test_unknown_algorithm_raises():
    with pytest.raises(ValueError, match="Algoritmo desconocido"):
        plan(parse_problem("A"), "voraz")


def test_timings_are_recorded():
    assert {"conflict_graph", "coloring", "alternative", "bounds"} <= set(plan(parse_problem(EXAM)).timings)


@pytest.mark.parametrize("n", [10, 100, 1000])
def test_random_problems_scale_and_stay_valid(n):
    p = plan(random_problem(n, 4 / n if n > 10 else 0.3, seed=1))
    assert p.coloring.valid and p.alternative.valid
    assert p.graph.num_vertices == n


def test_random_problem_is_reproducible_and_validates_arguments():
    assert random_problem(30, 0.2, seed=5) == random_problem(30, 0.2, seed=5)
    with pytest.raises(ValueError):
        random_problem(0, 0.2)
    with pytest.raises(ValueError):
        random_problem(10, 1.5)


def test_resource_problem_builds_union_of_cliques():
    prob = resource_problem(50, resources=10, per_task=2, seed=3)
    g = conflict_graph(prob)
    for users in prob.resource_users().values():
        assert all(g.has_edge(u, v) for u, v in itertools.combinations(users, 2))


def test_too_many_conflicts_is_rejected_before_building_the_graph():
    from graph_core.problem import ProblemError
    from graph_core.scheduling import MAX_CONFLICTS
    n = int((2 * MAX_CONFLICTS) ** 0.5) + 2
    text = "\n".join(f"T{i}: unico" for i in range(n))
    with pytest.raises(ProblemError, match="conflictos"):
        plan(parse_problem(text))


# --------------------------------------------------------------- regresiones de la revision
def test_one_huge_resource_clique_is_fast():
    import time
    t0 = time.perf_counter()
    p = plan(parse_problem("\n".join(f"T{i}: R" for i in range(440))))
    assert time.perf_counter() - t0 < 3                     # antes: ~16 s en greedy_clique
    assert p.bounds["exact"] == 440 and p.bounds["method"] == "clique"


def test_conflict_limit_counts_distinct_pairs_not_shared_resources():
    # 300 tareas con los mismos 3 recursos: 44 850 conflictos reales (antes se contaban x3 y se rechazaba)
    p = plan(parse_problem("\n".join(f"T{i}: r1, r2, r3" for i in range(300))), try_exact=False)
    assert p.graph.num_edges == 300 * 299 // 2
    assert p.graph.edge_attrs("T0", "T1")["resources"] == ["r1", "r2", "r3"]


def test_exact_method_is_reported():
    assert plan(parse_problem(EXAM)).bounds["method"] in {"clique", "branch_and_bound"}


def test_random_problem_enforces_limits_for_the_cli():
    from graph_core.problem import MAX_TASKS
    with pytest.raises(ValueError):
        random_problem(MAX_TASKS + 1, 0.0)
    with pytest.raises(ValueError, match="conflictos"):
        random_problem(1200, 1.0)
