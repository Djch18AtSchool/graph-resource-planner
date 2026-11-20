"""Generadores de grafos para las pruebas de estres (reproducibles con ``seed``)."""
from __future__ import annotations

import math
import random
from typing import List, Tuple

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


def sparse_random(n: int, seed: int = 0) -> Edges:
    """Grado medio ~4 (tipico de un grafo de microservicios grande): casi seguro no plano."""
    return random_edges(n, 2 * n, seed)


def dense_random(n: int, seed: int = 0) -> Edges:
    """Densidad 0.30 (n <= 100) o 0.05 (n = 1000, ~25k aristas): estres de coloracion y de Euler."""
    p = 0.30 if n <= 100 else 0.05
    return random_edges(n, int(p * n * (n - 1) / 2), seed)


def planar_plus_extra(n: int, seed: int = 0) -> Edges:
    """Triangulacion + n/20 aristas extra: casi plano, escenario realista para planarizar."""
    base = apollonian(n, seed)
    have = set(base) | {(b, a) for a, b in base}
    rng, extra = random.Random(seed + 1), []
    while len(extra) < max(1, n // 20):
        u, v = rng.randrange(n), rng.randrange(n)
        if u != v and (u, v) not in have:
            have.add((u, v)); have.add((v, u)); extra.append((u, v))
    return base + extra


FAMILIES = {
    "planar (triangulacion)": apollonian,
    "grilla (bipartito)": grid,
    "casi plano (+n/20)": planar_plus_extra,
    "aleatorio disperso": sparse_random,
    "aleatorio denso": dense_random,
}
