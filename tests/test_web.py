"""Capa web en Python: ejemplos, modelo de vista, API que invoca el Web Worker y construccion del sitio."""
import json
import zipfile

import pytest

from graph_core import parse_problem, plan
from graph_core.generators import random_problem
from scripts.build_web import build, python_sources
from visualization.examples import ORDER, load_examples
from visualization.view_model import DRAW_MAX_EDGES, MATRIX_MAX_VERTICES, build_view
from visualization.web_api import handle, metadata


def call(req):
    return json.loads(handle(json.dumps(req)))


# ------------------------------------------------------------------------------ ejemplos
def test_examples_load_in_display_order_and_all_parse():
    ex = load_examples()
    assert list(ex)[: len(ORDER)] == list(ORDER)
    for item in ex.values():
        assert item["title"] and parse_problem(item["text"]).tasks


def test_corona_example_shows_welsh_powell_weakness():
    text = load_examples()["corona"]["text"]
    dsatur, wp = plan(parse_problem(text), "dsatur"), plan(parse_problem(text), "welsh_powell")
    assert dsatur.coloring.num_colors == 2 and wp.coloring.num_colors > 2


# ------------------------------------------------------------------------ modelo de vista
@pytest.mark.parametrize("key", ORDER)
def test_view_is_json_and_batches_match_tasks(key):
    p = plan(parse_problem(load_examples()[key]["text"]))
    view = json.loads(json.dumps(build_view(p)))
    batch_of = {t["id"]: t["batch"] for t in view["tasks"]}
    for b in view["batches"]:
        assert all(batch_of[t] == b["index"] for t in b["tasks"])
    for c in view["conflicts"]:
        assert batch_of[c["source"]] != batch_of[c["target"]]       # coloracion valida
    assert len(view["steps"]) == view["metrics"]["tasks"]
    assert view["metrics"]["lower"] <= view["metrics"]["colors"] <= view["metrics"]["greedy_bound"]


def test_view_lists_resources_by_usage_and_matrix_for_small_graphs():
    view = build_view(plan(parse_problem(load_examples()["examenes"]["text"])))
    usage = [len(r["tasks"]) for r in view["resources"]]
    assert usage == sorted(usage, reverse=True)
    m = view["matrix"]
    assert len(m["rows"]) == len(m["labels"]) == view["metrics"]["tasks"]


def test_large_graphs_omit_matrix_and_drawing():
    p = plan(random_problem(MATRIX_MAX_VERTICES + 1, 0.0), try_exact=False)
    assert build_view(p)["matrix"] is None
    n = 400
    dense = plan(random_problem(n, (DRAW_MAX_EDGES + 500) / (n * (n - 1) / 2), seed=2), try_exact=False)
    view = build_view(dense)
    assert view["drawable"] is False and view["conflicts"] == []


# ------------------------------------------------------------------------------ web_api
def test_metadata_lists_examples_algorithms_and_limits():
    meta = json.loads(metadata())
    assert [e["key"] for e in meta["examples"]][: len(ORDER)] == list(ORDER)
    assert meta["algorithms"] == ["dsatur", "welsh_powell"]
    assert meta["limits"]["max_tasks"] > 0


def test_handle_text_and_random_modes():
    out = call({"mode": "text", "text": "A: r\nB: r\nC", "algorithm": "welsh_powell"})
    assert out["ok"] and out["view"]["algorithm"] == "welsh_powell" and out["view"]["metrics"]["colors"] == 2
    rnd = call({"mode": "random", "n": 100, "p": 0.05, "seed": 3})
    assert rnd["ok"] and rnd["view"]["metrics"]["tasks"] == 100


@pytest.mark.parametrize("req,fragment", [
    ({"mode": "nada"}, "Modo desconocido"),
    ({"mode": "text", "text": "   "}, "al menos una tarea"),
    ({"mode": "text", "text": "A\nA"}, "aparece dos veces"),
    ({"mode": "text", "text": "A", "algorithm": "voraz"}, "Algoritmo desconocido"),
    ({"mode": "text", "text": "A", "algorithm": ["x"]}, "Algoritmo desconocido"),
    ({"mode": "random", "n": "100", "p": 0.1}, "número"),
    ({"mode": "random", "n": 10.5, "p": 0.1}, "entero"),
    ({"mode": "random", "n": True, "p": 0.1}, "número"),
    ({"mode": "random", "n": 0, "p": 0.1}, "entre"),
    ({"mode": "random", "n": 100, "p": 2}, "entre"),
    ({"mode": "random", "n": 2000, "p": 0.5}, "probabilidad máxima"),
])
def test_handle_returns_friendly_errors(req, fragment):
    out = call(req)
    assert out["ok"] is False and fragment in out["error"]


def test_handle_rejects_non_object_and_hides_unexpected_errors():
    assert json.loads(handle("[1, 2]"))["ok"] is False
    deep = "[" * 50_000 + "]" * 50_000                     # RecursionError dentro de json.loads
    out = json.loads(handle(deep))
    assert out["ok"] is False and "Traceback" not in out["error"]


# --------------------------------------------------------------------------- build web
def test_build_creates_static_site_with_python_bundle(tmp_path):
    site = build(tmp_path / "dist")
    for name in ("index.html", "app.js", "worker.js", "styles.css", ".nojekyll", "py/manifest.json"):
        assert (site / name).exists()
    names = set(zipfile.ZipFile(site / "py" / "bundle.zip").namelist())
    assert {"graph_core/coloring.py", "graph_core/scheduling.py", "visualization/web_api.py",
            "examples/corona.txt"} <= names
    assert not any("tests/" in n or "cli.py" in n or "plotting.py" in n for n in names)
    assert json.loads((site / "py" / "manifest.json").read_text())["version"]
    assert all(p.suffix in {".py", ".txt"} for p in python_sources())
