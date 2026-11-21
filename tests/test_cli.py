"""CLI y dibujo con matplotlib."""
import json

import matplotlib
import pytest

matplotlib.use("Agg")

from graph_core import parse_problem, plan  # noqa: E402
from visualization.cli import format_summary, main  # noqa: E402
from visualization.plotting import batch_positions, draw_plan  # noqa: E402


def test_demo_prints_plan(capsys):
    assert main(["demo", "examenes"]) == 0
    out = capsys.readouterr().out
    assert "Lote 1" in out and "χ(G) 4 (exacto)" in out and "Ejecutores necesarios" in out


def test_file_command_saves_outputs(tmp_path, capsys):
    src = tmp_path / "t.txt"
    src.write_text("titulo: Mini\nA [2]: r\nB: r\nC\n", encoding="utf-8")
    assert main(["file", str(src), "--algorithm", "welsh_powell", "--layout", "batches", "--out", str(tmp_path / "o")]) == 0
    view = json.loads((tmp_path / "o" / "plan.json").read_text(encoding="utf-8"))
    assert view["algorithm"] == "welsh_powell" and view["metrics"]["colors"] == 2
    assert (tmp_path / "o" / "grafo.png").stat().st_size > 0
    assert parse_problem((tmp_path / "o" / "problema.txt").read_text(encoding="utf-8")).title == "Mini"


def test_file_command_reports_errors(tmp_path, capsys):
    bad = tmp_path / "bad.txt"
    bad.write_text("A\nA\n", encoding="utf-8")
    assert main(["file", str(bad)]) == 1
    assert "aparece dos veces" in capsys.readouterr().err
    assert main(["file", str(tmp_path / "missing.txt")]) == 1


def test_random_command_and_invalid_arguments(capsys):
    assert main(["random", "--n", "50", "--p", "0.1", "--seed", "2"]) == 0
    assert "G(50, 0.1)" in capsys.readouterr().out
    assert main(["random", "--n", "0"]) == 1


def test_summary_mentions_clique_and_both_algorithms():
    text = format_summary(plan(parse_problem("A: r\nB: r\nC: r")))
    assert "DSatur: 3 lotes" in text and "Welsh-Powell: 3 lotes" in text and "al menos 3 lotes" in text


def test_batch_layout_puts_each_batch_in_its_own_column():
    p = plan(parse_problem("A: r\nB: r\nC: s\nD"))
    pos = batch_positions(p)
    for u, v in p.graph.edges:
        assert pos[u][0] != pos[v][0]


def test_draw_plan_rejects_unknown_layout():
    p = plan(parse_problem("A"))
    assert draw_plan(p, "spring") is not None
    with pytest.raises(ValueError):
        draw_plan(p, "planar")


def test_stress_quick_writes_results(tmp_path):
    assert main(["stress", "--sizes", "10", "--out", str(tmp_path)]) == 0
    for name in ("stress_results.csv", "stress_representations.csv", "stress_times.png", "stress_colors.png"):
        assert (tmp_path / name).exists()
