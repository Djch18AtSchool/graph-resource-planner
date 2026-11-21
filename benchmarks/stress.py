"""
Pruebas de estres: grafos de 10, 100 y 1000 nodos.

    python main.py stress                      # o:  python -m benchmarks.stress
    python main.py stress --quick              # solo 10 y 100 nodos
    python main.py stress --sizes 10 100 1000 --out results

Produce en ``--out`` (por defecto ``results/``):
    stress_results.csv / .json    una fila por (familia, n): tiempos, colores y cotas de chi(G)
    stress_representations.csv    lista vs matriz: memoria y tiempo al crecer V (grafo disperso)
    stress_times.png, stress_colors.png, stress_ops.png, stress_memory.png    figuras para el informe
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import time
import tracemalloc
from pathlib import Path
from typing import Callable, Dict, List, Optional

from graph_core import Graph, clique_lower_bound, dsatur, exact_chromatic_number, welsh_powell
from graph_core.coloring import is_valid_coloring
from graph_core.generators import FAMILIES, random_edges


def timeit(fn: Callable, *a, repeat: int = 1, **kw):
    best, out = float("inf"), None
    for _ in range(repeat):
        t = time.perf_counter()
        out = fn(*a, **kw)
        best = min(best, time.perf_counter() - t)
    return best, out


def bench_operations(g: Graph, queries: int = 100_000, seed: int = 0) -> Dict[str, float]:
    """Lista vs matriz sobre una carga masiva de consultas (segundos)."""
    rng, vs = random.Random(seed), g.vertices
    pairs = [(rng.choice(vs), rng.choice(vs)) for _ in range(queries)]
    res: Dict[str, float] = {}
    for backend in ("list", "matrix"):
        res[f"has_edge_{backend}"], _ = timeit(lambda: [g.has_edge(u, v, backend) for u, v in pairs])
        res[f"neighbors_all_{backend}"], _ = timeit(lambda: [g.neighbors(v, backend) for v in vs])
        res[f"degrees_all_{backend}"], _ = timeit(g.degrees, backend)
    return res


def bench_one(family: str, n: int, seed: int = 1) -> Dict[str, object]:
    edges = FAMILIES[family](n, seed)
    row: Dict[str, object] = {"family": family, "n": n}

    tracemalloc.start()
    t_build, g = timeit(lambda: Graph(vertices=range(n), edges=edges))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    row.update(V=g.num_vertices, E=g.num_edges, density=round(g.density(), 5),
               max_degree=max(g.degrees().values(), default=0), build_s=t_build, build_peak_mb=peak / 1e6)
    row.update(bench_operations(g))

    for name, algo in (("dsatur", dsatur), ("welsh_powell", welsh_powell)):
        t, r = timeit(algo, g, repeat=3)
        assert r.valid and is_valid_coloring(g, r.colors)
        row[f"{name}_s"], row[f"{name}_colors"] = t, r.num_colors

    row["clique_lower"] = clique_lower_bound(g)
    t, exact = timeit(exact_chromatic_number, g)
    best = min(row["dsatur_colors"], row["welsh_powell_colors"])
    if exact is None and row["clique_lower"] == best:      # la clique demuestra que la heuristica es optima
        exact = best
    row.update(exact_s=t, exact_chi="" if exact is None else exact)
    return row


def bench_representations(sizes=(100, 500, 1000, 2000, 3000), seed: int = 2) -> List[Dict[str, float]]:
    """Memoria y tiempo de construir SOLO la lista o SOLO la matriz para un grafo disperso (E = 3V)."""
    out = []
    for V in sizes:
        edges = random_edges(V, 3 * V, seed)
        row = {"V": V, "E": len(edges)}

        tracemalloc.start()
        t = time.perf_counter()
        adj = {v: {} for v in range(V)}
        for u, v in edges:
            adj[u][v] = None
            adj[v][u] = None
        row["list_s"] = time.perf_counter() - t
        row["list_mb"] = tracemalloc.get_traced_memory()[1] / 1e6
        tracemalloc.stop()
        del adj

        tracemalloc.start()
        t = time.perf_counter()
        mat = [[0] * V for _ in range(V)]
        for u, v in edges:
            mat[u][v] = mat[v][u] = 1
        row["matrix_s"] = time.perf_counter() - t
        row["matrix_mb"] = tracemalloc.get_traced_memory()[1] / 1e6
        tracemalloc.stop()
        del mat
        out.append(row)
    return out


def _write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def _plots(out: Path, rows, rep_rows) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    sizes = sorted({r["n"] for r in rows})
    fams = list(dict.fromkeys(r["family"] for r in rows))

    # 1) tiempos de coloracion
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    for ax, key, title in ((axes[0], "dsatur_s", "DSatur"), (axes[1], "welsh_powell_s", "Welsh-Powell")):
        for fam in fams:
            ys = [next(r[key] for r in rows if r["family"] == fam and r["n"] == n) * 1000 for n in sizes]
            ax.plot(sizes, ys, marker="o", label=fam)
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlabel("n (vertices)"); ax.set_ylabel("ms"); ax.set_title(title); ax.grid(alpha=.3)
    axes[0].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(out / "stress_times.png", dpi=150); plt.close(fig)

    # 2) colores usados por cada algoritmo frente a la cota inferior (n mas grande)
    n = max(sizes)
    big = [next(r for r in rows if r["family"] == fam and r["n"] == n) for fam in fams]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    xs = range(len(fams))
    ax.bar([x - 0.27 for x in xs], [r["clique_lower"] for r in big], 0.27, label="cota inferior (clique)")
    ax.bar(list(xs), [r["dsatur_colors"] for r in big], 0.27, label="DSatur")
    ax.bar([x + 0.27 for x in xs], [r["welsh_powell_colors"] for r in big], 0.27, label="Welsh-Powell")
    ax.set_xticks(list(xs)); ax.set_xticklabels(fams, fontsize=8, rotation=12)
    ax.set_ylabel("colores (lotes)"); ax.set_title(f"Lotes usados, n = {n}"); ax.legend(); ax.grid(alpha=.3, axis="y")
    fig.tight_layout(); fig.savefig(out / "stress_colors.png", dpi=150); plt.close(fig)

    # 3) lista vs matriz en operaciones (grafo disperso mas grande)
    fam = "aleatorio disperso"
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ops = [("has_edge", "has_edge ×100k"), ("neighbors_all", "neighbors (todos)"), ("degrees_all", "grados (todos)")]
    n = max(sizes)
    r = next(r for r in rows if r["family"] == fam and r["n"] == n)
    xs = range(len(ops))
    ax.bar([x - 0.2 for x in xs], [r[f"{k}_list"] * 1000 for k, _ in ops], 0.4, label="lista de adyacencia")
    ax.bar([x + 0.2 for x in xs], [r[f"{k}_matrix"] * 1000 for k, _ in ops], 0.4, label="matriz de adyacencia")
    ax.set_xticks(list(xs)); ax.set_xticklabels([lbl for _, lbl in ops]); ax.set_yscale("log")
    ax.set_ylabel("ms"); ax.set_title(f"Lista vs matriz, V={n}, E={r['E']}"); ax.legend(); ax.grid(alpha=.3, axis="y")
    fig.tight_layout(); fig.savefig(out / "stress_ops.png", dpi=150); plt.close(fig)

    # 4) memoria lista vs matriz
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot([r["V"] for r in rep_rows], [r["list_mb"] for r in rep_rows], marker="o", label="lista O(V+E)")
    ax.plot([r["V"] for r in rep_rows], [r["matrix_mb"] for r in rep_rows], marker="s", label="matriz O(V²)")
    ax.set_xlabel("V (con E = 3V)"); ax.set_ylabel("pico de memoria (MB)")
    ax.set_title("Espacio: lista vs matriz"); ax.legend(); ax.grid(alpha=.3)
    fig.tight_layout(); fig.savefig(out / "stress_memory.png", dpi=150); plt.close(fig)


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="stress", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 100, 1000])
    ap.add_argument("--quick", action="store_true", help="solo 10 y 100 nodos")
    ap.add_argument("--out", default="results")
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args(argv)
    sizes = [10, 100] if args.quick else args.sizes
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    print(f"{'familia':24s}{'n':>6s}{'E':>8s}{'Δ':>5s}{'DSatur ms':>11s}{'cols':>5s}{'W-P ms':>9s}{'cols':>5s}"
          f"{'clique':>8s}{'χ(G)':>8s}")
    for n in sizes:
        for fam in FAMILIES:
            r = bench_one(fam, n)
            rows.append(r)
            print(f"{fam:24s}{n:6d}{r['E']:8d}{r['max_degree']:5d}{r['dsatur_s'] * 1000:11.2f}{r['dsatur_colors']:5d}"
                  f"{r['welsh_powell_s'] * 1000:9.2f}{r['welsh_powell_colors']:5d}{r['clique_lower']:8d}"
                  f"{str(r['exact_chi'] or '-'):>8s}", flush=True)
    rep_rows = bench_representations()
    _write_csv(out / "stress_results.csv", rows)
    _write_csv(out / "stress_representations.csv", rep_rows)
    (out / "stress_results.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    if not args.no_plots:
        _plots(out, rows, rep_rows)
    print(f"\nResultados en {out.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
