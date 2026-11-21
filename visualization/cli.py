"""
Interfaz de linea de comandos.

    python main.py demo [microservicios|examenes|ml|corona]   ejemplo incluido
    python main.py file mis_tareas.txt                         problema propio (formato de texto)
    python main.py random --n 1000 --p 0.005                   grafo aleatorio G(n, p)
    python main.py web                                         construye y sirve la app web
    python main.py stress                                      pruebas de estres (10 / 100 / 1000 nodos)

Opciones comunes: --algorithm dsatur|welsh_powell  --layout spring|batches  --out DIR  --show
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from graph_core import ALGORITHM_NAMES, ALGORITHMS, Plan, Problem, ProblemError, parse_problem, plan
from graph_core.generators import random_problem

from .examples import load_examples
from .plotting import LAYOUTS
from .view_model import build_view

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------------------ salida
def _num(x: float) -> str:
    return f"{x:g}"


def format_summary(p: Plan) -> str:
    b, g = p.bounds, p.graph
    chi = f"{b['exact']} (exacto)" if b["exact"] is not None else f"entre {b['lower']} y {b['upper']}"
    alg, alt = ALGORITHM_NAMES[p.coloring.algorithm], ALGORITHM_NAMES[p.alternative.algorithm]
    lines = [
        f"=== {p.problem.title or 'Asignación de recursos'} ===",
        f"Tareas: {g.num_vertices} | conflictos: {g.num_edges} | grado máximo Δ = {p.max_degree}",
        f"{alg}: {p.coloring.num_colors} lotes | {alt}: {p.alternative.num_colors} lotes | χ(G) {chi}",
        "",
        "Plan (cada lote corre en paralelo; los lotes van uno tras otro):",
    ]
    for batch in p.batches:
        lines.append(f"  Lote {batch.index} [t={_num(batch.start)}, dura {_num(batch.duration)}]: "
                     + ", ".join(batch.tasks))
    lines += [
        "",
        f"Ejecutores necesarios: {p.workers} | tiempo total: {_num(p.makespan)} "
        f"(secuencial: {_num(p.sequential_time)}, {p.speedup:.2f}x más rápido)",
    ]
    if len(p.clique) > 1:
        lines.append(f"Cota inferior: {', '.join(p.clique)} se bloquean entre sí -> al menos {len(p.clique)} lotes")
    lines.append("Tiempos: " + ", ".join(f"{k}={v * 1000:.2f}ms" for k, v in p.timings.items()))
    return "\n".join(lines)


def save_outputs(out: Path, p: Plan, layout: str) -> List[Path]:
    import matplotlib
    matplotlib.use("Agg")
    from .plotting import draw_plan

    out.mkdir(parents=True, exist_ok=True)
    problem_path, plan_path, png_path = out / "problema.txt", out / "plan.json", out / "grafo.png"
    problem_path.write_text(p.problem.to_text(), encoding="utf-8")
    plan_path.write_text(json.dumps(build_view(p), indent=2, ensure_ascii=False), encoding="utf-8")
    draw_plan(p, layout).savefig(png_path, dpi=150)
    return [problem_path, plan_path, png_path]


# ---------------------------------------------------------------------------- comandos
def _run(args, problem: Problem) -> int:
    p = plan(problem, args.algorithm)
    print(format_summary(p))
    if args.out:
        for path in save_outputs(Path(args.out), p, args.layout):
            print(f"  guardado: {path}")
    if args.show:
        import matplotlib.pyplot as plt
        from .plotting import draw_plan
        draw_plan(p, args.layout)
        plt.show()
    return 0


def cmd_demo(args) -> int:
    return _run(args, parse_problem(load_examples()[args.name]["text"]))


def cmd_file(args) -> int:
    try:
        problem = parse_problem(Path(args.path).read_text(encoding="utf-8"))
    except (OSError, ProblemError) as exc:
        print(f"Error al leer {args.path}: {exc}", file=sys.stderr)
        return 1
    return _run(args, problem)


def cmd_random(args) -> int:
    try:
        problem = random_problem(args.n, args.p, args.seed)
        return _run(args, problem)
    except (ValueError, ProblemError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def cmd_web(args) -> int:
    """Construye la app web (React + motor Python empaquetado) con pnpm y la sirve en localhost."""
    import shutil
    import subprocess
    from scripts.build_web import serve
    if not shutil.which("pnpm"):
        print("Error: hace falta pnpm (https://pnpm.io) para construir la interfaz web.", file=sys.stderr)
        return 1
    web = ROOT / "web"
    subprocess.run(["pnpm", "install", "--frozen-lockfile"], cwd=web, check=True)
    subprocess.run(["pnpm", "run", "build"], cwd=web, check=True)
    serve(web / "dist", args.port)
    return 0


def cmd_stress(args) -> int:
    from benchmarks.stress import main as stress_main
    return stress_main(args.rest)


# --------------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--algorithm", choices=sorted(ALGORITHMS), default="dsatur")
    common.add_argument("--layout", choices=LAYOUTS, default="spring")
    common.add_argument("--out", help="Carpeta donde guardar problema.txt, plan.json y grafo.png")
    common.add_argument("--show", action="store_true", help="Mostrar el grafo en una ventana")

    ap = argparse.ArgumentParser(prog="main.py", description="Asignación de recursos por coloración de grafos")
    sub = ap.add_subparsers(dest="command", required=True)

    s = sub.add_parser("demo", parents=[common], help="Ejemplo incluido")
    s.add_argument("name", nargs="?", default="microservicios", choices=list(load_examples()))
    s.set_defaults(func=cmd_demo)

    s = sub.add_parser("file", parents=[common], help="Problema en formato de texto (ver examples/)")
    s.add_argument("path")
    s.set_defaults(func=cmd_file)

    s = sub.add_parser("random", parents=[common], help="Grafo de conflictos aleatorio G(n, p)")
    s.add_argument("--n", type=int, default=100)
    s.add_argument("--p", type=float, default=0.05)
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(func=cmd_random)

    s = sub.add_parser("web", help="Construye la app web (Pyodide) y la sirve en http://localhost:PORT")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_web)

    s = sub.add_parser("stress", help="Pruebas de estrés (argumentos extra se pasan a benchmarks.stress)")
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_stress)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "stress":                 # sus opciones las interpreta benchmarks.stress
        return cmd_stress(argparse.Namespace(rest=argv[1:]))
    args = build_parser().parse_args(argv)
    return args.func(args)
