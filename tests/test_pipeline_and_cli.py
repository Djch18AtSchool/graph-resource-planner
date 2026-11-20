import asyncio
import json

import pytest

from ai_agent import EXAMPLES, GraphSpec, OfflineClient
from graph_core import check_planarity, count_crossings, is_valid_coloring
from pipeline import analyze_spec, run_pipeline
from visualization.cli import main


@pytest.mark.parametrize("key", sorted(EXAMPLES))
def test_pipeline_on_all_examples(key):
    a = analyze_spec(GraphSpec.model_validate(EXAMPLES[key]))
    assert a.coloring.valid and is_valid_coloring(a.conflict_graph, a.coloring.colors)
    assert a.bounds["lower"] <= a.coloring.num_colors <= a.bounds["upper"] + 3
    assert a.coloring.num_colors == a.bounds["exact"] or a.bounds["exact"] is None
    assert count_crossings(a.positions, a.drawing_graph.edges) == 0               # el dibujo final nunca cruza
    assert check_planarity(a.drawing_graph, with_positions=False).is_planar
    f = a.facts()
    assert f["planarity"]["is_planar"] == (f["planarity"]["virtual_nodes"] == 0)
    # el plan solo contiene componentes en conflicto y cubre todos exactamente una vez
    scheduled = [v for batch in a.schedule_vertices() for v in batch]
    assert sorted(scheduled) == sorted(a.constrained_vertices())
    assert not set(scheduled) & set(a.unconstrained_vertices())
    json.dumps(f)                                                                    # serializable


def test_no_conflicts_means_a_single_slot():
    spec = GraphSpec.model_validate({"nodes": [{"id": x, "label": x} for x in "abc"],
                                     "edges": [{"source": "a", "target": "b", "kind": "dependency"}]})
    a = analyze_spec(spec)
    assert a.coloring.num_colors == 1 and len(a.schedule()) == 1 and a.facts()["max_parallel_tasks"] == 3


def test_ecommerce_expected_numbers():
    a = analyze_spec(GraphSpec.model_validate(EXAMPLES["ecommerce"]))
    assert a.bounds["exact"] == 4 and a.planarity.is_planar and len(a.clique) == 4   # K4 de conflictos
    ml = analyze_spec(GraphSpec.model_validate(EXAMPLES["ml"]))
    assert not ml.planarity.is_planar and ml.planarity.witness_kind == "K3,3" and ml.planarization.num_crossings >= 1


def test_run_pipeline_end_to_end_offline():
    parsed, a, rep = asyncio.run(run_pipeline("arquitectura de e-commerce con pagos e inventario", OfflineClient()))
    assert parsed.provider == "offline" and rep.source == "template" and "chi(G) = 4" in rep.text
    _, _, no_rep = asyncio.run(run_pipeline("pipeline etl de datos", OfflineClient(), algorithm="welsh_powell",
                                            with_report=False))
    assert no_rep is None


# -------------------------------------------------------------------------------------- CLI
def test_cli_demo_writes_outputs(tmp_path, capsys):
    assert main(["demo", "ml", "--provider", "offline", "--out", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "NO plano" in out and "Lote 1" in out
    for name in ("spec.json", "analysis.json", "graph.png", "report.md"):
        assert (tmp_path / name).stat().st_size > 0
    facts = json.loads((tmp_path / "analysis.json").read_text())["facts"]
    assert facts["planarity"]["witness"] == "K3,3"


def test_cli_file_and_analyze(tmp_path, capsys):
    path = tmp_path / "spec.json"
    path.write_text(json.dumps(EXAMPLES["pipeline"]), encoding="utf-8")
    assert main(["file", str(path), "--provider", "offline", "--no-report", "--algorithm", "welsh_powell"]) == 0
    assert "Pipeline de datos diario" in capsys.readouterr().out
    assert main(["analyze", "e-commerce con pagos", "--provider", "offline", "--no-report"]) == 0
    assert main(["analyze", "   ", "--provider", "offline"]) == 1                    # error controlado
    assert main(["file", str(tmp_path / "nope.json"), "--provider", "offline"]) == 1


def test_cli_reports_missing_api_key_cleanly(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert main(["analyze", "x", "--provider", "anthropic"]) == 1
    assert main(["demo", "ml", "--provider", "anthropic"]) == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
