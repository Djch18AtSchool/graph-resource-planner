"""Capa web en Python: modelo de vista, API que invoca el Web Worker y construccion del sitio."""
import asyncio
import json
import zipfile

import pytest

from ai_agent import EXAMPLES, GraphSpec
from pipeline import analyze_spec
from scripts.build_web import build, python_sources
from visualization.view_model import CANVAS, MATRIX_MAX_VERTICES, build_view
from visualization.web_api import handle, metadata


def call(req, bridge=None):
    return json.loads(asyncio.run(handle(json.dumps(req), bridge)))


# ------------------------------------------------------------------------ modelo de vista
@pytest.mark.parametrize("key", sorted(EXAMPLES))
def test_view_is_json_and_planar_drawing_has_no_crossings(key):
    a = analyze_spec(GraphSpec.model_validate(EXAMPLES[key]))
    view = json.loads(json.dumps(build_view(a, "## r", "template", ["aviso"], "offline", 0)))
    assert view["planar"]["crossings"] == 0
    for node in view["planar"]["nodes"]:
        assert -1e-6 <= node["x"] <= CANVAS + 1e-6 and -1e-6 <= node["y"] <= CANVAS + 1e-6
    real = [n for n in view["planar"]["nodes"] if not n["virtual"]]
    assert len(real) == len(view["spring"]["nodes"]) == view["facts"]["nodes"]
    constrained = set(a.constrained_vertices())
    for n in real:
        assert (n["batch"] is not None) == (n["id"] in constrained)


def test_view_marks_kuratowski_witness_and_virtual_nodes():
    a = analyze_spec(GraphSpec.model_validate(EXAMPLES["ml"]))
    view = build_view(a)
    planar = view["planar"]
    assert sum(n["kuratowski"] for n in planar["nodes"]) == 6                 # 6 vertices de rama de K3,3
    assert any(e["kuratowski"] for e in planar["edges"])
    assert any(n["virtual"] for n in planar["nodes"])
    assert view["spring"]["crossings"] > 0                                     # el layout de fuerzas si cruza
    matrix = view["conflict_matrix"]
    assert len(matrix["rows"]) == len(matrix["labels"]) == 7


def test_matrix_is_omitted_for_large_graphs():
    n = MATRIX_MAX_VERTICES + 1
    spec = GraphSpec.model_validate({"nodes": [{"id": f"n{i}", "label": f"N{i}"} for i in range(n)]})
    assert build_view(analyze_spec(spec))["conflict_matrix"] is None


# ------------------------------------------------------------------------------ web_api
def test_metadata_lists_examples_and_algorithms():
    meta = json.loads(metadata())
    assert {e["key"] for e in meta["examples"]} == set(EXAMPLES)
    assert meta["algorithms"] == ["dsatur", "welsh_powell"]


def test_handle_example_text_and_json_modes_offline():
    ex = call({"mode": "example", "example": "pipeline", "algorithm": "welsh_powell"})
    assert ex["ok"] and ex["view"]["facts"]["chromatic"]["algorithm"] == "welsh_powell"
    assert ex["view"]["report_source"] == "template"
    txt = call({"mode": "text", "text": "tienda e-commerce con pagos", "with_report": False})
    assert txt["ok"] and txt["view"]["report"] == "" and txt["view"]["attempts"] == 1
    js = call({"mode": "json", "spec_json": json.dumps(EXAMPLES["ml"])})
    assert js["ok"] and not js["view"]["facts"]["planarity"]["is_planar"]


@pytest.mark.parametrize("req,fragment", [
    ({"mode": "nada"}, "Modo desconocido"),
    ({"mode": "example", "example": "zzz"}, "Ejemplo desconocido"),
    ({"mode": "example", "example": "ml", "algorithm": "voraz"}, "Algoritmo desconocido"),
    ({"mode": "json", "spec_json": "{mal"}, "JSON invalido"),
    ({"mode": "json", "spec_json": "x" * 200_001}, "excede"),
    ({"mode": "json", "spec_json": '{"nodes": []}'}, "nodes"),
    ({"mode": "text", "text": "   "}, "vacio"),
    ({"mode": "text", "text": "x", "provider": "anthropic"}, "puente"),
])
def test_handle_returns_friendly_errors(req, fragment):
    out = call(req)
    assert out["ok"] is False and fragment in out["error"]


def test_handle_rejects_non_object_request():
    assert json.loads(asyncio.run(handle("[1, 2]")))["ok"] is False


def test_handle_uses_bridge_for_llm_providers():
    class Bridge:
        def __init__(self):
            self.calls = 0

        async def request(self, provider, payload_json):
            self.calls += 1
            payload = json.loads(payload_json)
            if "format" in payload["output_config"]:
                text = json.dumps(EXAMPLES["pipeline"])
            else:
                text = "## Resumen\nTexto del LLM"
            return json.dumps({"content": [{"type": "text", "text": text}], "stop_reason": "end_turn"})

    bridge = Bridge()
    out = call({"mode": "text", "text": "pipeline", "provider": "anthropic", "model": "m"}, bridge)
    assert out["ok"] and bridge.calls == 2
    assert out["view"]["report_source"] == "llm" and out["view"]["provider"] == "anthropic"
    assert "Datos verificados" in out["view"]["report"]


# --------------------------------------------------------------------------- build web
def test_build_creates_static_site_with_python_bundle(tmp_path):
    site = build(tmp_path / "dist")
    for name in ("index.html", "app.js", "worker.js", "styles.css", ".nojekyll", "py/manifest.json"):
        assert (site / name).exists()
    names = set(zipfile.ZipFile(site / "py" / "bundle.zip").namelist())
    assert {"graph_core/coloring.py", "ai_agent/parser.py", "pipeline.py", "visualization/web_api.py"} <= names
    assert not any("tests/" in n or "cli.py" in n or "plotting.py" in n for n in names)
    assert json.loads((site / "py" / "manifest.json").read_text())["version"]
    assert all(p.suffix == ".py" for p in python_sources())


def test_unexpected_errors_return_generic_message_without_traceback():
    deep = "[" * 50_000 + "]" * 50_000                     # RecursionError dentro de json.loads
    out = call({"mode": "json", "spec_json": deep})
    assert out["ok"] is False and "Traceback" not in out["error"]
    out = call({"mode": "example", "example": "ml", "algorithm": ["x"]})
    assert out["ok"] is False and "Algoritmo desconocido" in out["error"]


def test_unrouted_edges_produce_a_warning():
    from visualization.web_api import _analysis_warnings
    assert _analysis_warnings({"planarity": {"unrouted_edges": 0}}) == []
    assert "3 arista(s)" in _analysis_warnings({"planarity": {"unrouted_edges": 3}})[0]
