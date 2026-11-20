"""
Contrato JSON entre el LLM y el motor de grafos.

    {
      "title": "E-commerce de microservicios",
      "nodes": [{"id": "payment-service", "label": "Pagos", "type": "service", "description": "..."}],
      "edges": [{"source": "checkout", "target": "payment-service", "kind": "dependency", "reason": "..."},
                {"source": "inventory", "target": "reports-job",   "kind": "conflict",   "reason": "misma BD"}]
    }

* ``dependency``: A necesita / se comunica con B (aristas de la arquitectura).
* ``conflict``  : A y B comparten un recurso y NO pueden ejecutarse a la vez (aristas del
                  grafo de conflictos que se colorea).

Los ids se normalizan (slug) en la validacion para que el LLM pueda escribir
"Payment Service" o "payment-service" y las aristas sigan resolviendose.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Dict, List, Literal, Tuple, get_args

from pydantic import BaseModel, Field, field_validator, model_validator

from graph_core import Graph

MAX_NODES = 60
EdgeKind = Literal["dependency", "conflict"]
NodeType = Literal["service", "task", "database", "queue", "gateway", "job", "external"]
NODE_TYPES = get_args(NodeType)
DEFAULT_NODE_TYPE = "service"

# Palabras clave de JSON Schema que la salida estructurada de la API no admite (se validan en
# el cliente con Pydantic): restricciones numericas, de longitud y de arreglos, y valores por defecto.
UNSUPPORTED_SCHEMA_KEYS = frozenset({"default", "minItems", "maxItems", "minLength", "maxLength",
                                     "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
                                     "multipleOf", "uniqueItems", "title"})


def slugify(text: str) -> str:
    """'Servicio de Pagos' -> 'servicio-de-pagos' (sin acentos, minusculas, [a-z0-9-])."""
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


class NodeSpec(BaseModel):
    id: str = Field(description="Identificador corto en kebab-case, unico")
    label: str = Field(description="Nombre legible para mostrar en el diagrama")
    type: NodeType = Field(default=DEFAULT_NODE_TYPE, description="Tipo de componente")
    description: str = Field(default="", description="Responsabilidad en una frase")

    @field_validator("id", mode="before")
    @classmethod
    def _slug(cls, v: Any) -> str:
        s = slugify(v)
        if not s:
            raise ValueError("id vacio")
        return s

    @field_validator("type", mode="before")
    @classmethod
    def _known_type(cls, v: Any) -> str:
        """Tolerante: un tipo desconocido (p. ej. 'microservice') se trata como 'service'."""
        t = str(v or "").strip().lower()
        return t if t in NODE_TYPES else DEFAULT_NODE_TYPE


class EdgeSpec(BaseModel):
    source: str
    target: str
    kind: EdgeKind = Field(description="dependency = depende/se comunica; conflict = comparte recurso, no concurrente")
    reason: str = Field(default="", description="Por que existe la relacion (recurso compartido, llamada, etc.)")

    @field_validator("source", "target", mode="before")
    @classmethod
    def _slug(cls, v: Any) -> str:
        return slugify(v)


class GraphSpec(BaseModel):
    title: str = Field(default="", description="Titulo corto del sistema")
    nodes: List[NodeSpec] = Field(min_length=1, max_length=MAX_NODES)
    edges: List[EdgeSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_references(self) -> "GraphSpec":
        ids = [n.id for n in self.nodes]
        dup = sorted({i for i in ids if ids.count(i) > 1})
        if dup:
            raise ValueError(f"ids de nodos duplicados: {dup}")
        known = set(ids)
        unknown = sorted({x for e in self.edges for x in (e.source, e.target) if x not in known})
        if unknown:
            raise ValueError(f"aristas que referencian nodos inexistentes: {unknown}. "
                             f"Ids validos: {sorted(known)}")
        return self

    # ------------------------------------------------------------------ limpieza
    def sanitized(self) -> Tuple["GraphSpec", List[str]]:
        """Elimina lazos y aristas repetidas (mismo par y tipo). Devuelve (spec, advertencias)."""
        warnings: List[str] = []
        seen, edges = set(), []
        for e in self.edges:
            if e.source == e.target:
                warnings.append(f"Se descarto el lazo {e.source}->{e.target}")
                continue
            key = (frozenset((e.source, e.target)), e.kind)
            if key in seen:
                warnings.append(f"Se descarto la arista repetida {e.source}-{e.target} ({e.kind})")
                continue
            seen.add(key)
            edges.append(e)
        return self.model_copy(update={"edges": edges}), warnings

    # ------------------------------------------------------------------ grafos
    def _base_graph(self) -> Graph:
        g = Graph()
        for n in self.nodes:
            g.add_vertex(n.id, label=n.label, type=n.type, description=n.description)
        return g

    def architecture_graph(self) -> Graph:
        """Union no dirigida de dependencias y conflictos (lo que se dibuja y se prueba para planaridad)."""
        g = self._base_graph()
        for e in self.edges:
            if g.has_edge(e.source, e.target):
                attrs = g.edge_attrs(e.source, e.target)
                attrs["kinds"] = sorted(set(attrs["kinds"]) | {e.kind})
                attrs["reason"] = "; ".join(x for x in (attrs.get("reason", ""), e.reason) if x)
            else:
                g.add_edge(e.source, e.target, kinds=[e.kind], reason=e.reason)
        return g

    def conflict_graph(self) -> Graph:
        """Solo las aristas de conflicto: es el grafo que se colorea (color = lote paralelo)."""
        g = self._base_graph()
        for e in self.edges:
            if e.kind == "conflict":
                g.add_edge(e.source, e.target, kinds=["conflict"], reason=e.reason)
        return g

    @classmethod
    def json_schema(cls) -> Dict[str, Any]:
        """JSON Schema completo (con las restricciones de Pydantic) y $ref resueltos."""
        return inline_refs(cls.model_json_schema())

    @classmethod
    def llm_schema(cls) -> Dict[str, Any]:
        """
        Esquema ESTRICTO para la salida estructurada del LLM (``output_config.format`` de Claude y
        ``format`` de Ollama): todo objeto con ``additionalProperties: false`` y todos sus campos
        requeridos, sin palabras clave no soportadas. Lo que se quita aqui (p. ej. maximo de 60
        nodos) lo sigue validando Pydantic al recibir la respuesta.
        """
        return strict_schema(cls.json_schema())


def strict_schema(node: Any) -> Any:
    """Transforma un JSON Schema al subconjunto estricto que acepta la salida estructurada."""
    if isinstance(node, list):
        return [strict_schema(x) for x in node]
    if not isinstance(node, dict):
        return node
    out = {k: strict_schema(v) for k, v in node.items()
           if k not in UNSUPPORTED_SCHEMA_KEYS or k == "properties"}
    if out.get("type") == "object" and "properties" in out:
        out["properties"] = {k: strict_schema(v) for k, v in node["properties"].items()}
        out["required"] = list(out["properties"])
        out["additionalProperties"] = False
    return out


def inline_refs(schema: Dict[str, Any]) -> Dict[str, Any]:
    """Resuelve ``$ref``/``$defs`` de un JSON Schema para obtener un esquema autocontenido."""
    defs = schema.get("$defs", {})

    def resolve(node: Any) -> Any:
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(defs[node["$ref"].split("/")[-1]])
            return {k: resolve(v) for k, v in node.items() if k != "$defs"}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(schema)
