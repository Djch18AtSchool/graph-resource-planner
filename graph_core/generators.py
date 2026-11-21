"""
Generadores reproducibles (``seed``) para las pruebas de estres y la demo web.

* Familias de grafos (listas de aristas sobre 0..n-1) con chi(G) conocido o acotado.
* ``random_problem`` / ``resource_problem``: problemas de tareas listos para planificar.
"""
from __future__ import annotations

import math
import random
from typing import List, Tuple

from .problem import MAX_TASKS, Problem, Task
from .scheduling import MAX_CONFLICTS

Edges = List[Tuple[int, int]]


def apollonian(n: int, seed: int = 0) -> Edges:
    """Triangulacion plana aleatoria (maximal plana: E = 3n - 6) insertando vertices en caras."""
    rng = random.Random(seed)
    if n < 3:
        return [(0, 1)] if n == 2 else []
    edges = [(0, 1), (1, 2), (0, 2)]
    faces = [(0, 1, 2), (0, 1, 2)]
    for v in range(3, n):
        a, b, c = faces.pop(rng.randrange(len(faces)))
        edges += [(v, a), (v, b), (v, c)]
        faces += [(a, b, v), (b, c, v), (a, c, v)]
    return edges


def grid(n: int, seed: int = 0) -> Edges:
    """Grilla ~sqrt(n) x sqrt(n): plana y bipartita (chi = 2)."""
    side = max(2, int(math.sqrt(n)))
    idx = lambda r, c: r * side + c
    out = []
    for r in range(side):
        for c in range(side):
            if c + 1 < side:
                out.append((idx(r, c), idx(r, c + 1)))
            if r + 1 < side:
                out.append((idx(r, c), idx(r + 1, c)))
    return out


def random_edges(n: int, m: int, seed: int = 0) -> Edges:
    rng = random.Random(seed)
    m = min(m, n * (n - 1) // 2)
    seen = set()
    while len(seen) < m:
        u, v = rng.randrange(n), rng.randrange(n)
        if u != v:
            seen.add((min(u, v), max(u, v)))
    return sorted(seen)


def random_problem(n: int, p: float, seed: int = 0) -> Problem:
    """n tareas ``T1..Tn`` con conflictos explicitos de un grafo aleatorio G(n, p)."""
    if not 1 <= n <= MAX_TASKS:
        raise ValueError(f"n debe estar entre 1 y {MAX_TASKS}")
    if not 0 <= p <= 1:
        raise ValueError("p debe estar entre 0 y 1")
    m = round(p * n * (n - 1) / 2)
    if m > MAX_CONFLICTS:
        raise ValueError(f"G({n}, {p:g}) tendría {m} conflictos; el máximo es {MAX_CONFLICTS}")
    names = [f"T{i + 1}" for i in range(n)]
    conflicts = tuple((names[u], names[v]) for u, v in random_edges(n, m, seed))
    return Problem(f"Aleatorio G({n}, {p:g})", tuple(Task(x) for x in names), conflicts)


def resource_problem(n: int, resources: int, per_task: int = 2, seed: int = 0) -> Problem:
    """n tareas que usan ``per_task`` recursos elegidos entre ``resources``: union de cliques (escenario real)."""
    rng = random.Random(seed)
    pool = [f"R{j + 1}" for j in range(resources)]
    tasks = tuple(Task(f"T{i + 1}", float(rng.randint(1, 4)), tuple(sorted(rng.sample(pool, min(per_task, resources)))))
                  for i in range(n))
    return Problem(f"Recursos compartidos ({n} tareas, {resources} recursos)", tasks)


def resource_edges(n: int, seed: int = 0) -> Edges:
    """Grafo de conflictos de ``resource_problem`` con max(4, n/5) recursos: cada recurso aporta una clique."""
    prob = resource_problem(n, max(4, n // 5), 2, seed)
    index = {t.name: i for i, t in enumerate(prob.tasks)}
    edges = set()
    for users in prob.resource_users().values():
        ids = [index[u] for u in users]
        edges.update((min(a, b), max(a, b)) for i, a in enumerate(ids) for b in ids[i + 1:])
    return sorted(edges)


def sparse_random(n: int, seed: int = 0) -> Edges:
    """Grado medio ~4 (tipico de un sistema grande con pocos conflictos por tarea)."""
    return random_edges(n, 2 * n, seed)


def dense_random(n: int, seed: int = 0) -> Edges:
    """Densidad 0.30 (n <= 100) o 0.05 (n = 1000, ~25k aristas): estres de coloracion."""
    p = 0.30 if n <= 100 else 0.05
    return random_edges(n, int(p * n * (n - 1) / 2), seed)


FAMILIES = {
    "planar (triangulacion)": apollonian,
    "grilla (bipartito)": grid,
    "aleatorio disperso": sparse_random,
    "aleatorio denso": dense_random,
    "recursos compartidos": lambda n, seed=0: resource_edges(n, seed),
}
