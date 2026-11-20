"""
Clase ``Graph``: grafo simple no dirigido con DOS representaciones sincronizadas.

* Lista de adyacencia  -> ``dict[vertice, dict[vertice, None]]``  espacio O(V + E)
                          (dict de insercion ordenada = conjunto ordenado: O(1) y recorrido determinista)
* Matriz de adyacencia -> ``list[list[int]]`` (V x V)          espacio O(V^2)

Ambas se mantienen coherentes en cada mutacion, de modo que el consumidor puede
elegir la que mejor convenga con ``backend="list" | "matrix"`` en las consultas
(vecinos, grado, existencia de arista) y asi comparar su rendimiento en las
pruebas de estres.

Tabla de complejidades (V = |vertices|, E = |aristas|, d = grado del vertice):

    operacion             lista (set)       matriz
    --------------------  ----------------  ---------------------------------
    add_vertex            O(1) amortizado   O(V)  (crece una fila y una columna)
    remove_vertex         O(d)              O(V)  (swap con el ultimo + pop)
    add_edge/remove_edge  O(1)              O(1)
    has_edge              O(1)              O(1)
    neighbors             O(d)              O(V)
    degree                O(1)              O(V)
    espacio               O(V + E)          O(V^2)

Nota: en la matriz, ``remove_vertex`` evita el costo O(V^2) de reconstruirla
intercambiando el vertice eliminado con el ultimo indice y recortando.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Hashable, Iterable, Iterator, List, Literal, Optional, Set, Tuple

Vertex = Hashable
Backend = Literal["list", "matrix"]


class GraphError(ValueError):
    """Error de uso de la clase Graph (vertice inexistente, lazo, etc.)."""


class Graph:
    """Grafo simple (sin lazos ni multiaristas) no dirigido, con atributos opcionales."""

    def __init__(self, vertices: Optional[Iterable[Vertex]] = None,
                 edges: Optional[Iterable[Tuple[Vertex, Vertex]]] = None) -> None:
        # --- lista de adyacencia ------------------------------------------------
        self._adj: Dict[Vertex, Dict[Vertex, None]] = {}
        # --- matriz de adyacencia (+ mapeo vertice <-> indice) -------------------
        self._labels: List[Vertex] = []           # indice -> vertice
        self._index: Dict[Vertex, int] = {}       # vertice -> indice
        self._matrix: List[List[int]] = []
        # --- atributos ---------------------------------------------------------------
        self._vattr: Dict[Vertex, Dict[str, Any]] = {}
        self._eattr: Dict[frozenset, Dict[str, Any]] = {}
        self._num_edges = 0

        for v in vertices or ():
            self.add_vertex(v)
        for u, v in edges or ():
            self.add_edge(u, v)

    # ------------------------------------------------------------------ vertices
    def add_vertex(self, v: Vertex, **attrs: Any) -> None:
        """Agrega un vertice (idempotente; si existe solo actualiza atributos). O(V) por la matriz."""
        if v in self._adj:
            self._vattr[v].update(attrs)
            return
        self._adj[v] = {}
        self._vattr[v] = dict(attrs)
        idx = len(self._labels)
        self._labels.append(v)
        self._index[v] = idx
        for row in self._matrix:
            row.append(0)
        self._matrix.append([0] * (idx + 1))

    def remove_vertex(self, v: Vertex) -> None:
        """Elimina el vertice y sus aristas incidentes. O(d) en lista, O(V) en matriz."""
        self._require(v)
        for w in list(self._adj[v]):          # O(d): limpia aristas incidentes
            self.remove_edge(v, w)
        # matriz: swap con el ultimo indice y recorte -> O(V), sin reconstruir
        i, last = self._index[v], len(self._labels) - 1
        if i != last:
            moved = self._labels[last]
            self._labels[i] = moved
            self._index[moved] = i
            self._matrix[i] = self._matrix[last]
            for row in self._matrix:
                row[i] = row[last]
            self._matrix[i][i] = 0
        self._labels.pop()
        self._matrix.pop()
        for row in self._matrix:
            row.pop()
        del self._index[v], self._adj[v], self._vattr[v]

    def has_vertex(self, v: Vertex) -> bool:
        return v in self._adj

    # --------------------------------------------------------------------- aristas
    def add_edge(self, u: Vertex, v: Vertex, **attrs: Any) -> None:
        """Agrega la arista {u, v}; crea los vertices si no existen. O(1) por representacion."""
        if u == v:
            raise GraphError(f"Lazo no permitido en grafo simple: {u!r}")
        self.add_vertex(u)
        self.add_vertex(v)
        key = frozenset((u, v))
        if v not in self._adj[u]:
            self._adj[u][v] = None
            self._adj[v][u] = None
            i, j = self._index[u], self._index[v]
            self._matrix[i][j] = self._matrix[j][i] = 1
            self._num_edges += 1
            self._eattr[key] = {}
        self._eattr[key].update(attrs)

    def remove_edge(self, u: Vertex, v: Vertex) -> None:
        """Elimina la arista {u, v}. O(1). No hace nada si no existe."""
        self._require(u)
        self._require(v)
        if v not in self._adj[u]:
            return
        del self._adj[u][v]
        del self._adj[v][u]
        i, j = self._index[u], self._index[v]
        self._matrix[i][j] = self._matrix[j][i] = 0
        self._num_edges -= 1
        self._eattr.pop(frozenset((u, v)), None)

    def has_edge(self, u: Vertex, v: Vertex, backend: Backend = "list") -> bool:
        """O(1) con cualquiera de los dos backends."""
        if u not in self._adj or v not in self._adj:
            return False
        if backend == "matrix":
            return bool(self._matrix[self._index[u]][self._index[v]])
        return v in self._adj[u]

    # ---------------------------------------------------------------- consultas
    def neighbors(self, v: Vertex, backend: Backend = "list") -> List[Vertex]:
        """Vecinos de v. Lista: O(d). Matriz: O(V) (hay que barrer la fila)."""
        self._require(v)
        if backend == "matrix":
            row = self._matrix[self._index[v]]
            return [self._labels[j] for j, x in enumerate(row) if x]
        return list(self._adj[v])

    def degree(self, v: Vertex, backend: Backend = "list") -> int:
        """Grado de v. Lista: O(1). Matriz: O(V)."""
        self._require(v)
        if backend == "matrix":
            return sum(self._matrix[self._index[v]])
        return len(self._adj[v])

    def degrees(self, backend: Backend = "list") -> Dict[Vertex, int]:
        """Grado de todos los vertices. Lista: O(V). Matriz: O(V^2)."""
        return {v: self.degree(v, backend) for v in self._labels}

    @property
    def vertices(self) -> List[Vertex]:
        return list(self._labels)

    @property
    def edges(self) -> List[Tuple[Vertex, Vertex]]:
        """Cada arista una sola vez, orientada segun el orden de insercion. O(V + E)."""
        out = []
        for u in self._labels:
            iu = self._index[u]
            for v in self._adj[u]:
                if self._index[v] > iu:
                    out.append((u, v))
        return out

    @property
    def num_vertices(self) -> int:
        return len(self._labels)

    @property
    def num_edges(self) -> int:
        return self._num_edges

    def density(self) -> float:
        n = self.num_vertices
        return 0.0 if n < 2 else 2 * self._num_edges / (n * (n - 1))

    def adjacency_matrix(self) -> List[List[int]]:
        """Copia de la matriz (filas/columnas segun ``self.vertices``)."""
        return [row[:] for row in self._matrix]

    def adjacency_list(self) -> Dict[Vertex, List[Vertex]]:
        return {v: list(self._adj[v]) for v in self._labels}

    def vertex_attrs(self, v: Vertex) -> Dict[str, Any]:
        self._require(v)
        return self._vattr[v]

    def edge_attrs(self, u: Vertex, v: Vertex) -> Dict[str, Any]:
        if not self.has_edge(u, v):
            raise GraphError(f"No existe la arista {u!r}-{v!r}")
        return self._eattr[frozenset((u, v))]

    def is_consistent(self) -> bool:
        """Verifica que lista y matriz describan el mismo grafo (usado en tests). O(V^2)."""
        for u in self._labels:
            for v in self._labels:
                in_list = v in self._adj[u]
                in_mat = bool(self._matrix[self._index[u]][self._index[v]])
                if in_list != in_mat:
                    return False
        return sum(len(s) for s in self._adj.values()) == 2 * self._num_edges

    def copy(self) -> "Graph":
        g = Graph()
        for v in self._labels:
            g.add_vertex(v, **self._vattr[v])
        for u, v in self.edges:
            g.add_edge(u, v, **self._eattr[frozenset((u, v))])
        return g

    def subgraph(self, vertices: Iterable[Vertex]) -> "Graph":
        keep = set(vertices)
        g = Graph()
        for v in self._labels:
            if v in keep:
                g.add_vertex(v, **self._vattr[v])
        for u, v in self.edges:
            if u in keep and v in keep:
                g.add_edge(u, v, **self._eattr[frozenset((u, v))])
        return g

    def connected_components(self) -> List[List[Vertex]]:
        """Recorrido iterativo. O(V + E)."""
        seen: Set[Vertex] = set()
        comps = []
        for s in self._labels:
            if s in seen:
                continue
            comp, stack = [], [s]
            seen.add(s)
            while stack:
                x = stack.pop()
                comp.append(x)
                for y in self._adj[x]:
                    if y not in seen:
                        seen.add(y)
                        stack.append(y)
            comps.append(comp)
        return comps

    # ------------------------------------------------------------------ exportacion
    def to_dict(self) -> Dict[str, Any]:
        return {
            "nodes": [{"id": v, **self._vattr[v]} for v in self._labels],
            "edges": [{"source": u, "target": v, **self._eattr[frozenset((u, v))]}
                      for u, v in self.edges],
        }

    def to_json(self, indent: Optional[int] = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False, default=str)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Graph":
        g = cls()
        for n in data.get("nodes", []):
            n = dict(n)
            g.add_vertex(n.pop("id"), **n)
        for e in data.get("edges", []):
            e = dict(e)
            g.add_edge(e.pop("source"), e.pop("target"), **e)
        return g

    @classmethod
    def from_json(cls, text: str) -> "Graph":
        return cls.from_dict(json.loads(text))

    def to_networkx(self):
        """Exporta a ``networkx.Graph`` conservando atributos. O(V + E)."""
        import networkx as nx
        G = nx.Graph()
        for v in self._labels:
            G.add_node(v, **self._vattr[v])
        for u, v in self.edges:
            G.add_edge(u, v, **self._eattr[frozenset((u, v))])
        return G

    @classmethod
    def from_networkx(cls, G) -> "Graph":
        g = cls()
        for v, data in G.nodes(data=True):
            g.add_vertex(v, **data)
        for u, v, data in G.edges(data=True):
            if u != v:
                g.add_edge(u, v, **data)
        return g

    # ------------------------------------------------------------------------- misc
    def _require(self, v: Vertex) -> None:
        if v not in self._adj:
            raise GraphError(f"El vertice {v!r} no existe")

    def __contains__(self, v: Vertex) -> bool:
        return v in self._adj

    def __iter__(self) -> Iterator[Vertex]:
        return iter(self._labels)

    def __len__(self) -> int:
        return self.num_vertices

    def __repr__(self) -> str:
        return f"Graph(V={self.num_vertices}, E={self.num_edges})"
