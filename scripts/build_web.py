"""
Construye el sitio estatico (GitHub Pages) de la app web.

    uv run python -m scripts.build_web            # -> dist/
    uv run python -m scripts.build_web --serve    # construye y sirve en http://localhost:8000

El sitio = archivos de ``visualization/web/`` + ``py/bundle.zip`` con el MISMO codigo Python del
repositorio (graph_core, ai_agent, pipeline y la parte web de visualization), que Pyodide descomprime
y ejecuta en el navegador. No hay una "copia" del algoritmo en JavaScript: es un unico codigo fuente.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import shutil
import zipfile
from functools import partial
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parent.parent
WEB_SRC = ROOT / "visualization" / "web"
PY_PACKAGES = ("graph_core", "ai_agent")
PY_FILES = ("pipeline.py", "visualization/__init__.py", "visualization/view_model.py",
            "visualization/web_api.py")
DEFAULT_PORT = 8000


def python_sources(root: Path = ROOT) -> List[Path]:
    """Archivos .py que necesita el navegador (sin pruebas, CLI ni graficos de matplotlib)."""
    files: List[Path] = []
    for pkg in PY_PACKAGES:
        files += sorted((root / pkg).rglob("*.py"))
    files += [root / f for f in PY_FILES]
    return [f for f in files if "__pycache__" not in f.parts]


def write_bundle(files: Iterable[Path], target: Path, root: Path = ROOT) -> str:
    """Empaqueta los fuentes en un zip determinista y devuelve su hash corto (cache busting)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            info = zipfile.ZipInfo(f.relative_to(root).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
            zf.writestr(info, f.read_bytes())
    return hashlib.sha256(target.read_bytes()).hexdigest()[:12]


def build(out: Path = ROOT / "dist") -> Path:
    if not WEB_SRC.is_dir():
        raise FileNotFoundError(f"No existe {WEB_SRC}")
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(WEB_SRC, out)
    version = write_bundle(python_sources(), out / "py" / "bundle.zip")
    (out / "py" / "manifest.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    (out / ".nojekyll").write_text("", encoding="utf-8")       # Pages sirve los archivos tal cual
    return out


def serve(site: Path, port: int = DEFAULT_PORT) -> None:
    handler = partial(http.server.SimpleHTTPRequestHandler, directory=str(site))
    handler.func.extensions_map = {**handler.func.extensions_map, ".mjs": "text/javascript",
                                   ".js": "text/javascript", ".wasm": "application/wasm"}
    with http.server.ThreadingHTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Sirviendo {site} en http://localhost:{port}  (Ctrl+C para terminar)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = ap.parse_args(argv)
    site = build(Path(args.out))
    print(f"Sitio construido en {site}")
    if args.serve:
        serve(site, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
