"""graph_core: estructuras de grafos y algoritmos (coloracion, planaridad) del motor de planificacion."""
from .graph import Graph, GraphError
from .coloring import (ALGORITHMS, ColoringResult, chromatic_bounds, clique_lower_bound, color_graph, dsatur,
                       exact_chromatic_number, greedy_clique, is_valid_coloring, welsh_powell)
from .drawing import planar_drawing, tutte_positions
from .planarity import (PlanarityResult, PlanarizationResult, check_planarity, count_crossings,
                        kuratowski_witness, planarize)

__all__ = [
    "Graph", "GraphError",
    "ALGORITHMS", "ColoringResult", "dsatur", "welsh_powell", "color_graph", "is_valid_coloring",
    "clique_lower_bound", "greedy_clique", "exact_chromatic_number", "chromatic_bounds",
    "planar_drawing", "tutte_positions",
    "PlanarityResult", "PlanarizationResult", "check_planarity", "kuratowski_witness", "planarize", "count_crossings",
]
