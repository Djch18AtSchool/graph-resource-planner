"""
Interfaz de linea de comandos.

    python main.py demo [ecommerce|pipeline|ml]            analisis de un ejemplo (sin API key)
    python main.py analyze "Crea una arquitectura ..."     requerimiento en lenguaje natural
    python main.py file examples/ecommerce.json            analiza un GraphSpec JSON ya escrito
    python main.py interactive                             bucle interactivo (REPL)
    python main.py web                                     construye y sirve la app web en localhost
    python main.py stress                                  pruebas de estres (10 / 100 / 1000 nodos)

Opciones comunes: --provider anthropic|ollama|offline  --model ID  --algorithm dsatur|welsh_powell
                  --layout planar|spring  --out DIR  --no-report  --show
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import List, Optional

from ai_agent import EXAMPLES, GraphSpec, LLMError, ReportGenerator, get_client
from graph_core import ALGORITHMS
from pipeline import AnalysisResult, analyze_spec, run_pipeline

ROOT = Path(__file__).resolve().parent.parent


# ------------------------------------------------------------------------------ salida
def format_summary(a: AnalysisResult) -> str:
    f = a.facts()
    c, p = f["chromatic"], f["planarity"]
    chi = f"{c['exact']} (exacto)" if c["exact"] is not None else f"{c['lower']}..{c['upper']}"
    lines = [
        f"=== {f['title'] or 'Grafo de recursos'} ===",
        f"Componentes: {f['nodes']} | dependencias: {f['dependency_edges']} | conflictos: {f['conflict_edges']}",
        f"Coloracion ({c['algorithm']}): {c['colors_used']} lotes | Welsh-Powell: {c['welsh_powell_colors']} | chi(G) = {chi}",
        "",
        "Plan de ejecucion (cada lote corre en paralelo, los lotes van en secuencia):",
    ]
    for slot in f["schedule"]:
        lines.append(f"  Lote {slot['slot']}: " + ", ".join(slot["tasks"]))
    if f["unconstrained"]:
        lines.append("  Sin restricciones: " + ", ".join(f["unconstrained"]))
    lines.append("")
    if p["is_planar"]:
        lines.append("Planaridad: el diagrama es PLANO (0 cruces).")
    else:
        lines.append(f"Planaridad: NO plano (certificado: subdivision de {p['witness']}). "
                     f"Planarizado con {p['crossings']} cruce(s) = {p['virtual_nodes']} nodo(s) virtual(es).")
        if p["unrouted_edges"]:
            lines.append(f"  ATENCION: {p['unrouted_edges']} aristas sin enrutar (limite de tiempo).")
    t = a.timings
    lines.append("Tiempos: " + ", ".join(f"{k}={v * 1000:.1f}ms" for k, v in t.items()))
    return "\n".join(lines)


def save_outputs(out: Path, a: AnalysisResult, report_text: Optional[str], layout: str) -> List[Path]:
    import matplotlib
    matplotlib.use("Agg")
    from visualization.plotting import draw_analysis

    out.mkdir(parents=True, exist_ok=True)
    paths = []
    p = out / "spec.json"
    p.write_text(a.spec.model_dump_json(indent=2), encoding="utf-8")
    paths.append(p)
    p = out / "analysis.json"
    p.write_text(json.dumps({"facts": a.facts(), "timings_s": a.timings,
                             "drawing_graph": a.drawing_graph.to_dict()}, indent=2, ensure_ascii=False, default=str),
                 encoding="utf-8")
    paths.append(p)
    fig, _ = draw_analysis(a, layout=layout)
    p = out / "graph.png"
    fig.savefig(p, dpi=150)
    paths.append(p)
    if report_text:
        p = out / "report.md"
        p.write_text(report_text, encoding="utf-8")
        paths.append(p)
    return paths


def _show(a: AnalysisResult, layout: str) -> None:
    from visualization.plotting import draw_analysis
    import matplotlib.pyplot as plt
    draw_analysis(a, layout=layout)
    plt.show()


# ---------------------------------------------------------------------------- comandos
def _client(args):
    kwargs = {"model": args.model} if args.model else {}
    return get_client(args.provider, **kwargs)


def _finish(args, a: AnalysisResult, report_text: Optional[str]) -> None:
    print(format_summary(a))
    if report_text:
        print("\n" + report_text)
    if args.out:
        for p in save_outputs(Path(args.out), a, report_text, args.layout):
            print(f"  guardado: {p}")
    if args.show:
        _show(a, args.layout)


def cmd_analyze(args) -> int:
    try:
        client = _client(args)
        parsed, a, report = asyncio.run(
            run_pipeline(args.text, client, args.algorithm, with_report=not args.no_report))
    except (LLMError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"[proveedor: {parsed.provider} | intentos: {parsed.attempts}]")
    for w in parsed.warnings:
        print(f"  aviso: {w}")
    if report and report.warning:
        print(f"  aviso: {report.warning}")
    _finish(args, a, report.text if report else None)
    return 0


def _analyze_spec_with_report(args, spec: GraphSpec) -> int:
    a = analyze_spec(spec, args.algorithm)
    report_text = None
    if not args.no_report:
        try:
            client = _client(args)
        except LLMError as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1
        rep = asyncio.run(ReportGenerator(client).generate(a.facts()))
        if rep.warning:
            print(f"  aviso: {rep.warning}")
        report_text = rep.text
    _finish(args, a, report_text)
    return 0


def cmd_file(args) -> int:
    try:
        spec, _ = GraphSpec.model_validate_json(Path(args.path).read_text(encoding="utf-8")).sanitized()
    except (OSError, ValueError) as exc:
        print(f"Error al leer {args.path}: {exc}", file=sys.stderr)
        return 1
    return _analyze_spec_with_report(args, spec)


def cmd_demo(args) -> int:
    spec, _ = GraphSpec.model_validate(EXAMPLES[args.name]).sanitized()
    return _analyze_spec_with_report(args, spec)


def cmd_interactive(args) -> int:
    try:
        client = _client(args)
    except LLMError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    print(f"Motor de planificacion (proveedor: {client.name}). Describa un sistema; 'salir' para terminar.")
    print("Ejemplo: Crea una arquitectura de microservicios para un e-commerce con pagos, inventario y notificaciones.")
    while True:
        try:
            text = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if text.lower() in {"salir", "exit", "quit"}:
            return 0
        if not text:
            continue
        try:
            parsed, a, report = asyncio.run(
                run_pipeline(text, client, args.algorithm, with_report=not args.no_report))
        except (LLMError, ValueError) as exc:
            print(f"Error: {exc}")
            continue
        for w in parsed.warnings:
            print(f"  aviso: {w}")
        _finish(args, a, report.text if report else None)


def cmd_web(args) -> int:
    from scripts.build_web import build, serve
    site = build(ROOT / "dist")
    print(f"Sitio construido en {site}")
    serve(site, args.port)
    return 0


def cmd_stress(args) -> int:
    from benchmarks.stress import main as stress_main
    return stress_main(args.rest)


# --------------------------------------------------------------------------------- main
def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--provider", choices=["anthropic", "ollama", "offline"], default=None,
                        help="Proveedor LLM (por defecto: LLM_PROVIDER, o anthropic si hay API key, o offline)")
    common.add_argument("--model", default=None, help="Modelo del proveedor (p. ej. claude-opus-5-5, llama3.1)")
    common.add_argument("--algorithm", choices=sorted(ALGORITHMS), default="dsatur")
    common.add_argument("--layout", choices=["planar", "spring"], default="planar")
    common.add_argument("--out", help="Carpeta donde guardar spec.json, analysis.json, graph.png y report.md")
    common.add_argument("--no-report", action="store_true", help="Omitir el reporte del LLM")
    common.add_argument("--show", action="store_true", help="Mostrar el grafo en una ventana")

    ap = argparse.ArgumentParser(prog="main.py", description="Motor IA de planificacion basado en grafos")
    sub = ap.add_subparsers(dest="command", required=True)

    s = sub.add_parser("analyze", parents=[common], help="Requerimiento en lenguaje natural")
    s.add_argument("text")
    s.set_defaults(func=cmd_analyze)

    s = sub.add_parser("file", parents=[common], help="Analizar un GraphSpec JSON")
    s.add_argument("path")
    s.set_defaults(func=cmd_file)

    s = sub.add_parser("demo", parents=[common], help="Ejemplo incluido (no necesita API key)")
    s.add_argument("name", nargs="?", default="ecommerce", choices=sorted(EXAMPLES))
    s.set_defaults(func=cmd_demo)

    s = sub.add_parser("interactive", parents=[common], help="Bucle interactivo")
    s.set_defaults(func=cmd_interactive)

    s = sub.add_parser("web", help="Construye la app web (Pyodide) y la sirve en http://localhost:PORT")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_web)

    s = sub.add_parser("stress", help="Pruebas de estres (argumentos extra se pasan a benchmarks.stress)")
    s.add_argument("rest", nargs=argparse.REMAINDER)
    s.set_defaults(func=cmd_stress)
    return ap


def main(argv: Optional[List[str]] = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv and argv[0] == "stress":                 # sus opciones las interpreta benchmarks.stress
        return cmd_stress(argparse.Namespace(rest=argv[1:]))
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
