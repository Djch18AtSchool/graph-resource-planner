"""
Empaqueta el motor en Python para la app web (Pyodide).

    uv run python -m scripts.build_web --out web/public/py

Escribe ``bundle.zip`` con el MISMO codigo Python del repositorio (graph_core, los ejemplos y la API web de
visualization) y ``manifest.json`` con su hash. La interfaz (``web/``, React + TypeScript) descarga el zip,
Pyodide lo descomprime en el navegador y lo ejecuta dentro de un Web Worker: el algoritmo no se reescribe en
JavaScript.
"""
from __future__ import annotations

import argparse
import hashlib
import http.server
import json
import zipfile
from functools import partial
from pathlib import Path
from typing import Iterable, List

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "web" / "public" / "py"
PY_PACKAGES = ("graph_core",)
PY_FILES = ("visualization/__init__.py", "visualization/examples.py", "visualization/view_model.py",
            "visualization/web_api.py")
DATA_GLOBS = ("examples/*.txt",)
ZIP_DATE = (2026, 1, 1, 0, 0, 0)            # fecha fija: el zip (y su hash) solo cambia si cambia el codigo
DEFAULT_PORT = 8000


def python_sources(root: Path = ROOT) -> List[Path]:
    """Archivos que necesita el navegador: .py (sin pruebas, CLI ni matplotlib) y los ejemplos .txt."""
    files: List[Path] = []
    for pkg in PY_PACKAGES:
        files += sorted((root / pkg).rglob("*.py"))
    files += [root / f for f in PY_FILES]
    for pattern in DATA_GLOBS:
        files += sorted(root.glob(pattern))
    return [f for f in files if "__pycache__" not in f.parts]


def write_bundle(files: Iterable[Path], target: Path, root: Path = ROOT) -> str:
    """Empaqueta los fuentes en un zip determinista y devuelve su hash corto (cache busting)."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            zf.writestr(zipfile.ZipInfo(f.relative_to(root).as_posix(), date_time=ZIP_DATE), f.read_bytes())
    return hashlib.sha256(target.read_bytes()).hexdigest()[:12]


def build(out: Path = DEFAULT_OUT) -> Path:
    """Escribe ``bundle.zip`` y ``manifest.json`` en ``out`` y devuelve esa carpeta."""
    version = write_bundle(python_sources(), out / "bundle.zip")
    (out / "manifest.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    return out


def serve(site: Path, port: int = DEFAULT_PORT) -> None:
    """Sirve una carpeta estatica (por ejemplo ``web/dist``) en http://localhost:PORT."""
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
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args(argv)
    out = build(Path(args.out))
    print(f"Motor Python empaquetado en {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
