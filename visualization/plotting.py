"""
Dibujo del resultado del analisis (matplotlib).

* Color del nodo   = lote de ejecucion (color del grafo de conflictos). Gris = sin restricciones.
* Linea continua   = dependencia; linea roja discontinua = conflicto de recursos.
* Rombo hueco      = nodo virtual (cruce que hubo que resolver para que el grafo sea plano).
* layout="planar"  = posiciones del planar embedding (garantiza 0 cruces en el dibujo).
* layout="spring"  = layout de fuerzas de networkx sobre la arquitectura original (puede cruzar
                     aristas); se incluye para MOSTRAR el valor de la planaridad en la demo.
"""
from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

import networkx as nx
from matplotlib import pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from graph_core import count_crossings

PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2", "#72B7B2", "#EECA3B", "#9D755D",
           "#FF9DA6", "#79706E", "#439894", "#D67195"]
FREE_COLOR = "#D0D3D8"


def _normalize(pos: Dict[Any, Tuple[float, float]]) -> Dict[Any, Tuple[float, float]]:
    xs = [p[0] for p in pos.values()] or [0]
    ys = [p[1] for p in pos.values()] or [0]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    dx, dy = (x1 - x0) or 1.0, (y1 - y0) or 1.0
    return {v: ((x - x0) / dx, (y - y0) / dy) for v, (x, y) in pos.items()}


def draw_analysis(analysis, layout: str = "planar", show_labels: Optional[bool] = None,
                  figsize: Tuple[float, float] = (11, 7.5)):
    """Devuelve ``(figura, cruces)``; ``cruces`` es el numero de pares de aristas que se cruzan en el dibujo."""
    if layout == "spring":
        G = analysis.architecture_graph
        nxg = G.to_networkx()
        pos = _normalize(nx.spring_layout(nxg, seed=7, k=1.6 / max(1, len(G)) ** 0.5))
        edges = [(u, v, G.edge_attrs(u, v)) for u, v in G.edges]
        nodes = G.vertices
    else:
        G = analysis.drawing_graph
        pos = _normalize(analysis.positions)
        edges = [(u, v, G.edge_attrs(u, v)) for u, v in G.edges]
        nodes = G.vertices

    crossings = count_crossings(pos, [(u, v) for u, v, _ in edges]) if len(edges) < 4000 else -1
    n_real = analysis.architecture_graph.num_vertices
    if show_labels is None:
        show_labels = n_real <= 60

    fig, ax = plt.subplots(figsize=figsize)
    dep, con = [], []
    for u, v, attrs in edges:
        seg = [pos[u], pos[v]]
        (con if "conflict" in attrs.get("kinds", []) else dep).append(seg)
    ax.add_collection(LineCollection(dep, colors="#7A7F87", linewidths=1.2, zorder=1))
    ax.add_collection(LineCollection(con, colors="#D62728", linewidths=1.6, linestyles="--", zorder=2))

    constrained = set(analysis.constrained_vertices())
    colors = analysis.coloring.colors
    size = 700 if n_real <= 25 else 300 if n_real <= 60 else 40 if n_real <= 300 else 8
    real = [v for v in nodes if v in analysis.architecture_graph]
    virtual = [v for v in nodes if v not in analysis.architecture_graph]
    fc = [PALETTE[colors[v] % len(PALETTE)] if v in constrained else FREE_COLOR for v in real]
    ax.scatter([pos[v][0] for v in real], [pos[v][1] for v in real], s=size, c=fc,
               edgecolors="#222", linewidths=0.8, zorder=3)
    if virtual:
        ax.scatter([pos[v][0] for v in virtual], [pos[v][1] for v in virtual], s=size * 0.25, marker="D",
                   facecolors="white", edgecolors="#222", linewidths=1.2, zorder=4)
    if show_labels:
        for v in real:
            label = str(analysis.label(v))
            ax.annotate(label if len(label) <= 22 else label[:21] + "…", pos[v], fontsize=7.5,
                        ha="center", va="bottom", xytext=(0, 9 if size > 100 else 4),
                        textcoords="offset points", zorder=5)

    handles = [Patch(facecolor=PALETTE[c % len(PALETTE)], edgecolor="#222", label=f"Lote {c + 1}")
               for c in sorted(analysis.coloring.batches)
               if any(v in constrained for v in analysis.coloring.batches[c])]
    handles += [Patch(facecolor=FREE_COLOR, edgecolor="#222", label="Sin restricciones"),
                Line2D([0], [0], color="#7A7F87", lw=1.5, label="Dependencia"),
                Line2D([0], [0], color="#D62728", lw=1.8, ls="--", label="Conflicto")]
    if virtual:
        handles.append(Line2D([0], [0], marker="D", color="w", markerfacecolor="white", markeredgecolor="#222",
                              label="Nodo virtual (cruce)"))
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.01, 1), fontsize=8, frameon=False)

    chi = analysis.coloring.num_colors
    title = analysis.spec.title or "Grafo de recursos"
    kind = "layout plano" if layout != "spring" else "layout de fuerzas"
    sub = f"{kind} · cruces: {crossings if crossings >= 0 else 'n/d'} · χ(G) ≤ {chi}"
    ax.set_title(f"{title}\n{sub}", fontsize=11)
    ax.set_xlim(-0.08, 1.08)
    ax.set_ylim(-0.1, 1.12)
    ax.axis("off")
    fig.tight_layout()
    return fig, crossings
