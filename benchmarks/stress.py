"""
Pruebas de estres: grafos de 10, 100 y 1000 nodos.

    python main.py stress                      # o:  python -m benchmarks.stress
    python main.py stress --quick              # solo 10 y 100 nodos
    python main.py stress --sizes 10 100 1000 --planarize-limit 30 --out results

Produce en ``--out`` (por defecto ``results/``):
    stress_results.csv / .json    una fila por (familia, n) con tiempos, memoria y calidad
    stress_representations.csv    lista vs matriz: memoria y tiempo al crecer V (grafo disperso)
    stress_times.png, stress_ops.png, stress_memory.png    figuras para el informe
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

from graph_core import Graph, check_planarity, dsatur, planarize, welsh_powell
from graph_core.coloring import is_valid_coloring

from .generators import FAMILIES


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


def bench_one(family: str, n: int, planarize_limit: float, seed: int = 1) -> Dict[str, object]:
    edges = FAMILIES[family](n, seed)
    row: Dict[str, object] = {"family": family, "n": n}

    tracemalloc.start()
    t_build, g = timeit(lambda: Graph(vertices=range(n), edges=edges))
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    row.update(V=g.num_vertices, E=g.num_edges, density=round(g.density(), 5),
               build_s=t_build, build_peak_mb=peak / 1e6)
    row.update(bench_operations(g))

    for name, algo in (("dsatur", dsatur), ("welsh_powell", welsh_powell)):
        t, r = timeit(algo, g, repeat=3)
        assert r.valid and is_valid_coloring(g, r.colors)
        row[f"{name}_s"], row[f"{name}_colors"] = t, r.num_colors

    t, pl = timeit(check_planarity, g)
    row.update(planarity_s=t, is_planar=pl.is_planar, witness=pl.witness_kind or "",
               euler_exceeded=pl.euler_bound_exceeded)

    t, res = timeit(planarize, g, time_limit=planarize_limit)
    row.update(planarize_s=t, crossings=res.num_crossings, unrouted=len(res.unrouted_edges),
               planarize_completed=not res.unrouted_edges)
    return row


def bench_representations(sizes=(100, 500, 1000, 2000, 3000), seed: int = 2) -> List[Dict[str, float]]:
    """Memoria y tiempo de construir SOLO la lista o SOLO la matriz para un grafo disperso (E = 3V)."""
    from .generators import random_edges
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

    # 1) tiempos de coloracion y planaridad
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.2))
    for ax, key, title in ((axes[0], "dsatur_s", "DSatur"), (axes[1], "welsh_powell_s", "Welsh-Powell"),
                           (axes[2], "planarity_s", "Test de planaridad")):
        for fam in fams:
            ys = [next(r[key] for r in rows if r["family"] == fam and r["n"] == n) * 1000 for n in sizes]
            ax.plot(sizes, ys, marker="o", label=fam)
        ax.set_xscale("log"); ax.set_yscale("log")
        ax.set_xlabel("n (vertices)"); ax.set_ylabel("ms"); ax.set_title(title); ax.grid(alpha=.3)
    axes[0].legend(fontsize=7)
    fig.tight_layout(); fig.savefig(out / "stress_times.png", dpi=150); plt.close(fig)

    # 2) lista vs matriz en operaciones (grafo disperso mas grande)
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

    # 3) memoria lista vs matriz
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
    ap.add_argument("--planarize-limit", type=float, default=30.0, help="segundos maximos por planarizacion")
    ap.add_argument("--out", default="results")
    ap.add_argument("--no-plots", action="store_true")
    args = ap.parse_args(argv)
    sizes = [10, 100] if args.quick else args.sizes
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    rows = []
    hdr = f"{'familia':24s}{'n':>6s}{'E':>8s}{'DSatur':>10s}{'cols':>5s}{'W-P':>10s}{'cols':>5s}{'planar?':>9s}{'plan.ms':>9s}{'cruces':>8s}{'planarizar':>12s}"
    print(hdr)
    for n in sizes:
        for fam in FAMILIES:
            r = bench_one(fam, n, args.planarize_limit)
            rows.append(r)
            note = "" if r["planarize_completed"] else f" (limite; {r['unrouted']} sin enrutar)"
            print(f"{fam:24s}{n:6d}{r['E']:8d}{r['dsatur_s'] * 1000:9.2f}m{r['dsatur_colors']:5d}"
                  f"{r['welsh_powell_s'] * 1000:9.2f}m{r['welsh_powell_colors']:5d}{str(r['is_planar']):>9s}"
                  f"{r['planarity_s'] * 1000:9.1f}{r['crossings']:8d}{r['planarize_s']:11.2f}s{note}", flush=True)
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
