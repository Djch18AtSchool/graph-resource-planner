"""Ejemplos incluidos (``examples/*.txt``), en el orden en que se muestran en la web y la CLI."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from graph_core import parse_problem

EXAMPLES_DIR = Path(__file__).resolve().parent.parent / "examples"
ORDER = ("microservicios", "examenes", "ml", "corona")


def load_examples(folder: Path = EXAMPLES_DIR) -> Dict[str, Dict[str, str]]:
    """clave -> {"title", "text"}. Los archivos que no estan en ORDER van al final, por nombre."""
    files = sorted(folder.glob("*.txt"), key=lambda f: (ORDER.index(f.stem) if f.stem in ORDER else len(ORDER), f.stem))
    out: Dict[str, Dict[str, str]] = {}
    for f in files:
        text = f.read_text(encoding="utf-8")
        out[f.stem] = {"title": parse_problem(text).title or f.stem, "text": text}
    return out
