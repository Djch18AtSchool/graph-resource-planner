"""
Dibujo del plan con matplotlib (CLI).

* Color del nodo = lote de ejecucion (color del grafo de conflictos).
* layout="spring"  : layout de fuerzas de networkx.
* layout="batches" : una columna por lote; como cada lote es un conjunto independiente, TODAS las
                     aristas van entre columnas distintas (se ve que la coloracion es valida).
"""
from __future__ import annotations

from typing import Dict, Tuple

import networkx as nx
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Patch

from graph_core import ALGORITHM_NAMES, Plan

PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2", "#72B7B2", "#EECA3B", "#9D755D",
           "#FF9DA6", "#79706E", "#439894", "#D67195"]
LAYOUTS = ("spring", "batches")
LABELS_MAX_NODES = 60
Position = Tuple[float, float]


def batch_color(color: int) -> str:
    return PALETTE[color % len(PALETTE)]


def batch_positions(p: Plan) -> Dict[str, Position]:
    pos: Dict[str, Position] = {}
    for col, batch in enumerate(p.batches):
        n = len(batch.tasks)
        for row, task in enumerate(batch.tasks):
            pos[task] = (float(col), 0.5 if n == 1 else 1 - row / (n - 1))
    return pos


def spring_positions(p: Plan, seed: int = 7) -> Dict[str, Position]:
    g = p.graph
    return nx.spring_layout(g.to_networkx(), seed=seed, k=1.6 / max(1, len(g)) ** 0.5)


def draw_plan(p: Plan, layout: str = "spring", figsize: Tuple[float, float] = (11, 7)):
    if layout not in LAYOUTS:
        raise ValueError(f"Layout desconocido: {layout!r}. Opciones: {LAYOUTS}")
    g, colors = p.graph, p.coloring.colors
    pos = batch_positions(p) if layout == "batches" else spring_positions(p)
    n = g.num_vertices

    fig, ax = plt.subplots(figsize=figsize)
    segments = [[pos[u], pos[v]] for u, v in g.edges]
    ax.add_collection(LineCollection(segments, colors="#8a929d", linewidths=1.0, alpha=0.7, zorder=1))
    size = 650 if n <= 25 else 260 if n <= 60 else 40 if n <= 300 else 8
    vs = g.vertices
    ax.scatter([pos[v][0] for v in vs], [pos[v][1] for v in vs], s=size, c=[batch_color(colors[v]) for v in vs],
               edgecolors="#222", linewidths=0.8, zorder=3)
    if n <= LABELS_MAX_NODES:
        for v in vs:
            label = v if len(v) <= 22 else v[:21] + "…"
            ax.annotate(label, pos[v], fontsize=7.5, ha="center", va="bottom", zorder=4,
                        xytext=(0, 13 if size > 300 else 9 if size > 100 else 4), textcoords="offset points")

    handles = [Patch(facecolor=batch_color(b.index - 1), edgecolor="#222", label=f"Lote {b.index}")
               for b in p.batches[:12]]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, frameon=False)
    b = p.bounds
    chi = f"χ(G) = {b['exact']}" if b["exact"] is not None else f"{b['lower']} ≤ χ(G) ≤ {b['upper']}"
    ax.set_title(f"{p.problem.title or 'Asignación de recursos'}\n"
                 f"{ALGORITHM_NAMES[p.coloring.algorithm]}: {p.coloring.num_colors} lotes · {chi}", fontsize=11)
    ax.autoscale()
    ax.margins(0.08)
    ax.axis("off")
    fig.tight_layout()
    return fig
