"""
Problema de asignacion de recursos: tareas, duraciones, recursos exclusivos y conflictos explicitos.

Formato de texto (una linea por elemento; las lineas que empiezan con ``#`` son comentarios):

    titulo: Ventana de mantenimiento          titulo opcional
    Migrar BD [3]: db_pedidos                  tarea de 3 unidades de tiempo que usa db_pedidos
    Respaldo [2]: db_pedidos, disco            tarea que usa dos recursos
    Limpiar cache                              tarea sin recursos (duracion 1)
    Respaldo -- Reindexar                      conflicto explicito entre dos tareas

Cada recurso es EXCLUSIVO (capacidad 1): dos tareas que lo usan no pueden ejecutarse a la vez.
La lectura es lineal en el largo del texto (sin expresiones regulares con retroceso).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

MAX_TEXT_CHARS = 200_000
MAX_TASKS = 2000
MAX_NAME_CHARS = 60
MAX_DURATION = 1_000_000.0
DEFAULT_DURATION = 1.0
CONFLICT_SEP = "--"
FORBIDDEN_NAME_CHARS = ":[],"

TITLE_KEYS = ("titulo", "título")
COMMENT = "#"


class ProblemError(ValueError):
    """Error de validacion con un mensaje pensado para el usuario final."""


@dataclass(frozen=True)
class Task:
    name: str
    duration: float = DEFAULT_DURATION
    resources: Tuple[str, ...] = ()


@dataclass(frozen=True)
class Problem:
    title: str
    tasks: Tuple[Task, ...]
    conflicts: Tuple[Tuple[str, str], ...] = ()

    def resource_users(self) -> Dict[str, List[str]]:
        """Recurso -> tareas que lo usan (en orden). Esas tareas forman una clique del grafo de conflictos."""
        users: Dict[str, List[str]] = {}
        for task in self.tasks:
            for r in task.resources:
                users.setdefault(r, []).append(task.name)
        return users

    def to_text(self) -> str:
        lines = [f"titulo: {self.title}"] if self.title else []
        for t in self.tasks:
            dur = "" if t.duration == DEFAULT_DURATION else f" [{_format_number(t.duration)}]"
            res = f": {', '.join(t.resources)}" if t.resources else ""
            lines.append(f"{t.name}{dur}{res}")
        lines += [f"{a} {CONFLICT_SEP} {b}" for a, b in self.conflicts]
        return "\n".join(lines) + "\n"


def _format_number(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x)


# ------------------------------------------------------------------------------- lectura
def _fail(lineno: int, message: str) -> ProblemError:
    return ProblemError(f"línea {lineno}: {message}")


def _check_name(raw: str, lineno: int, what: str) -> str:
    name = raw.strip()
    if not name:
        raise _fail(lineno, f"falta el nombre de la {what}")
    if len(name) > MAX_NAME_CHARS:
        raise _fail(lineno, f"el nombre «{name[:20]}…» supera {MAX_NAME_CHARS} caracteres")
    if CONFLICT_SEP in name or any(c in name for c in FORBIDDEN_NAME_CHARS):
        raise _fail(lineno, f"el nombre «{name}» no puede contener «{CONFLICT_SEP}» ni {' '.join(FORBIDDEN_NAME_CHARS)}")
    return name


def _parse_duration(raw: Optional[str], lineno: int) -> float:
    if raw is None:
        return DEFAULT_DURATION
    try:
        value = float(raw.strip().replace(",", "."))
    except ValueError:
        raise _fail(lineno, f"duración inválida «{raw.strip()}»; use un número, p. ej. [2]") from None
    if not 0 < value <= MAX_DURATION:
        raise _fail(lineno, f"la duración debe ser mayor que 0 y como máximo {_format_number(MAX_DURATION)}")
    return value


def _parse_resources(raw: Optional[str], lineno: int) -> Tuple[str, ...]:
    if raw is None or not raw.strip():
        return ()
    out: List[str] = []
    for part in raw.split(","):
        if not part.strip():
            raise _fail(lineno, "hay un recurso vacío (revise las comas)")
        name = _check_name(part, lineno, "recurso")
        if name not in out:
            out.append(name)
    return tuple(out)


def _split_task(line: str, lineno: int) -> Tuple[str, Optional[str], Optional[str]]:
    """«Nombre [duracion]: recursos» -> (nombre, duracion | None, recursos | None)."""
    head, sep, res = line.partition(":")
    resources = res if sep else None
    if "[" not in head:
        if "]" in head:
            raise _fail(lineno, "falta «[» antes de la duración")
        return head, None, resources
    name, _, rest = head.partition("[")
    duration, close, tail = rest.partition("]")
    if not close or tail.strip() or "[" in duration:
        raise _fail(lineno, "no se entiende la línea; use «Tarea [duración]: recurso1, recurso2»")
    return name, duration, resources


def _parse_task(line: str, lineno: int) -> Task:
    name, duration, resources = _split_task(line, lineno)
    return Task(_check_name(name, lineno, "tarea"), _parse_duration(duration, lineno),
                _parse_resources(resources, lineno))


def _title(line: str) -> Optional[str]:
    key, sep, value = line.partition(":")
    return value.strip()[:120] if sep and key.strip().lower() in TITLE_KEYS else None


def _parse_conflict(line: str, lineno: int) -> Tuple[str, str]:
    parts = line.split(CONFLICT_SEP)
    if len(parts) != 2:
        raise _fail(lineno, f"un conflicto une exactamente dos tareas: «A {CONFLICT_SEP} B»")
    a, b = (_check_name(p, lineno, "tarea") for p in parts)
    if a == b:
        raise _fail(lineno, f"la tarea «{a}» no puede tener conflicto consigo misma")
    return a, b


def parse_problem(text: str) -> Problem:
    """Lee el formato de texto. Lanza ``ProblemError`` con el numero de linea si algo no es valido."""
    if len(text) > MAX_TEXT_CHARS:
        raise ProblemError(f"El texto excede {MAX_TEXT_CHARS} caracteres")
    title, tasks, conflicts = "", [], []
    declared: Dict[str, int] = {}
    for lineno, raw in enumerate(text.split("\n"), start=1):     # split("\n"): numeros de linea del editor
        line = raw.strip()
        if not line or line.startswith(COMMENT):
            continue
        if (heading := _title(line)) is not None:
            title = heading
        elif CONFLICT_SEP in line:
            conflicts.append((_parse_conflict(line, lineno), lineno))
        else:
            task = _parse_task(line, lineno)
            if task.name in declared:
                raise _fail(lineno, f"la tarea «{task.name}» aparece dos veces (ver línea {declared[task.name]})")
            declared[task.name] = lineno
            tasks.append(task)
            if len(tasks) > MAX_TASKS:
                raise ProblemError(f"Se admiten como máximo {MAX_TASKS} tareas")
    if not tasks:
        raise ProblemError("El problema no tiene tareas; escriba una por línea, p. ej. «Backup [2]: base_datos»")
    for (a, b), lineno in conflicts:
        missing = next((x for x in (a, b) if x not in declared), None)
        if missing:
            raise _fail(lineno, f"tarea desconocida «{missing}» en el conflicto")
    return Problem(title, tuple(tasks), tuple(pair for pair, _ in conflicts))
