"""Formato de texto de tareas/recursos: lectura, validacion y ida y vuelta."""
import pytest

from graph_core.problem import (MAX_TASKS, MAX_TEXT_CHARS, Problem, ProblemError, Task, parse_problem)

SAMPLE = """
# Despliegue nocturno
titulo: Ventana de mantenimiento
Migrar BD pedidos [3]: db_pedidos
Respaldo pedidos [2]: db_pedidos, disco_respaldo
Reindexar busqueda: indice
Limpiar cache
Respaldo pedidos -- Reindexar busqueda
"""


def test_parses_title_tasks_durations_resources_and_explicit_conflicts():
    p = parse_problem(SAMPLE)
    assert p.title == "Ventana de mantenimiento"
    assert [t.name for t in p.tasks] == ["Migrar BD pedidos", "Respaldo pedidos", "Reindexar busqueda", "Limpiar cache"]
    assert p.tasks[0] == Task("Migrar BD pedidos", 3.0, ("db_pedidos",))
    assert p.tasks[1].resources == ("db_pedidos", "disco_respaldo")
    assert p.tasks[3] == Task("Limpiar cache", 1.0, ())
    assert p.conflicts == (("Respaldo pedidos", "Reindexar busqueda"),)


def test_resource_users_lists_tasks_per_resource_in_order():
    users = parse_problem(SAMPLE).resource_users()
    assert users == {"db_pedidos": ["Migrar BD pedidos", "Respaldo pedidos"],
                     "disco_respaldo": ["Respaldo pedidos"], "indice": ["Reindexar busqueda"]}


def test_conflicts_may_reference_tasks_declared_later_and_accept_title_with_accent():
    p = parse_problem("Título: X\nA -- B\nA\nB\n")
    assert p.title == "X" and p.conflicts == (("A", "B"),)


def test_duplicate_resources_on_one_task_are_merged():
    assert parse_problem("A: r, r ,s").tasks[0].resources == ("r", "s")


def test_round_trip_through_text():
    p = parse_problem(SAMPLE)
    assert parse_problem(p.to_text()) == p


@pytest.mark.parametrize("text,fragment", [
    ("", "no tiene tareas"),
    ("# solo comentarios\n", "no tiene tareas"),
    ("A\nA", "aparece dos veces"),
    ("A\nA -- Z", "tarea desconocida"),
    ("A -- A", "consigo misma"),
    ("A [x]: r", "duración"),
    ("A [0]: r", "duración"),
    ("A [-2]", "duración"),
    ("A: r,,s", "recurso vacío"),
    (": r", "nombre"),
    ("A -- B -- C\nA\nB\nC", "conflicto"),
    ("A" * 61, "60 caracteres"),
    ("A: " + "r" * 61, "60 caracteres"),
])
def test_invalid_lines_raise_friendly_errors(text, fragment):
    with pytest.raises(ProblemError) as exc:
        parse_problem(text)
    assert fragment in str(exc.value)


def test_errors_mention_the_line_number():
    with pytest.raises(ProblemError, match="línea 3"):
        parse_problem("A\nB\nC [no]")


def test_limits_on_size_and_number_of_tasks():
    with pytest.raises(ProblemError, match="excede"):
        parse_problem("A\n" + "#" * MAX_TEXT_CHARS)
    with pytest.raises(ProblemError, match=str(MAX_TASKS)):
        parse_problem("\n".join(f"T{i}" for i in range(MAX_TASKS + 1)))


def test_problem_is_immutable():
    p = parse_problem("A")
    with pytest.raises(AttributeError):
        p.title = "otro"
    assert isinstance(p, Problem)


# --------------------------------------------------------------- regresiones de la revision
def test_long_lines_parse_in_linear_time():
    import time
    t0 = time.perf_counter()
    with pytest.raises(ProblemError):
        parse_problem("a" + " " * 50_000 + "b]")           # antes: retroceso cubico de la regex
    assert time.perf_counter() - t0 < 1


def test_hash_inside_names_is_kept_and_only_full_lines_are_comments():
    p = parse_problem("titulo: Plan #2\nCompilar C# [3]: build_server\n  # comentario con sangria")
    assert p.title == "Plan #2"
    assert p.tasks == (Task("Compilar C#", 3.0, ("build_server",)),)


def test_line_numbers_match_the_editor_even_with_form_feeds():
    with pytest.raises(ProblemError, match="línea 2"):
        parse_problem("A\x0cB\nC [x]")


@pytest.mark.parametrize("text", ["A ]: r", "A [2: r", "A [2] extra: r", "A [[2]]"])
def test_malformed_brackets_are_rejected(text):
    with pytest.raises(ProblemError):
        parse_problem(text)
