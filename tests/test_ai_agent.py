import asyncio
import copy
import json

import pytest

from ai_agent import (EXAMPLES, GraphSpec, LLMClient, LLMError, OfflineClient, ReportGenerator,
                      RequirementParser, get_client, slugify, template_report)
from ai_agent.schemas import inline_refs, strict_schema
from pipeline import analyze_spec

run = asyncio.run


class FakeClient(LLMClient):
    """LLM de mentira: responde con una cola de salidas predefinidas y registra las llamadas."""
    name = "fake"

    def __init__(self, structured=(), text="## Resumen\ntexto del LLM", text_error=None):
        self.structured = list(structured)
        self.text, self.text_error = text, text_error
        self.calls = []

    async def complete_structured(self, system, user, schema):
        self.calls.append(("structured", system, user, schema))
        return self.structured.pop(0)

    async def complete_text(self, system, user):
        self.calls.append(("text", system, user, None))
        if self.text_error:
            raise self.text_error
        return self.text


GOOD = {"title": "t", "nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
        "edges": [{"source": "a", "target": "b", "kind": "conflict", "reason": "bd"}]}


# ------------------------------------------------------------------------------ esquema
def test_slugify():
    assert slugify("Servicio de Pagos") == "servicio-de-pagos"
    assert slugify("Notificación_RT!!") == "notificacion-rt"
    assert slugify("  --  ") == ""


def test_ids_are_normalized_so_edges_still_resolve():
    spec = GraphSpec.model_validate({"nodes": [{"id": "Payment Service", "label": "P"}, {"id": "DB", "label": "D"}],
                                     "edges": [{"source": "payment service", "target": "db", "kind": "dependency"}]})
    assert [n.id for n in spec.nodes] == ["payment-service", "db"]
    assert spec.edges[0].source == "payment-service"


@pytest.mark.parametrize("bad", [
    {"nodes": []},
    {"nodes": [{"id": "a", "label": "A"}, {"id": "a", "label": "A2"}]},                       # duplicado
    {"nodes": [{"id": "a", "label": "A"}], "edges": [{"source": "a", "target": "zzz", "kind": "conflict"}]},
    {"nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
     "edges": [{"source": "a", "target": "b", "kind": "amistad"}]},                            # kind invalido
    {"nodes": [{"id": "!!!", "label": "A"}]},                                                  # id vacio tras slug
])
def test_invalid_specs_are_rejected(bad):
    with pytest.raises(ValueError):
        GraphSpec.model_validate(bad)


def test_sanitized_drops_loops_and_duplicates():
    spec = GraphSpec.model_validate({"nodes": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
                                     "edges": [{"source": "a", "target": "a", "kind": "conflict"},
                                               {"source": "a", "target": "b", "kind": "conflict"},
                                               {"source": "b", "target": "a", "kind": "conflict"},
                                               {"source": "a", "target": "b", "kind": "dependency"}]})
    clean, warnings = spec.sanitized()
    assert len(clean.edges) == 2 and len(warnings) == 2


def test_graph_views_split_conflicts_from_architecture():
    spec = GraphSpec.model_validate({"nodes": [{"id": x, "label": x} for x in "abc"],
                                     "edges": [{"source": "a", "target": "b", "kind": "dependency"},
                                               {"source": "a", "target": "b", "kind": "conflict"},
                                               {"source": "b", "target": "c", "kind": "dependency"}]})
    arch, conf = spec.architecture_graph(), spec.conflict_graph()
    assert arch.num_edges == 2 and sorted(arch.edge_attrs("a", "b")["kinds"]) == ["conflict", "dependency"]
    assert conf.num_edges == 1 and conf.has_edge("a", "b") and conf.num_vertices == 3


def test_json_schema_is_self_contained():
    schema = GraphSpec.json_schema()
    assert "$defs" not in json.dumps(schema) and "$ref" not in json.dumps(schema)
    assert schema["properties"]["edges"]["items"]["properties"]["kind"]["enum"] == ["dependency", "conflict"]
    assert inline_refs({"a": 1}) == {"a": 1}


def _objects(node):
    if isinstance(node, dict):
        if node.get("type") == "object":
            yield node
        for v in node.values():
            yield from _objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _objects(v)


def test_llm_schema_is_strict_for_structured_outputs():
    schema = GraphSpec.llm_schema()
    text = json.dumps(schema)
    for key in ("minItems", "maxItems", "default", "$ref"):
        assert f'"{key}"' not in text                                     # no soportado por la API
    objects = list(_objects(schema))
    assert len(objects) == 3                                               # GraphSpec, NodeSpec, EdgeSpec
    for obj in objects:
        assert obj["additionalProperties"] is False
        assert sorted(obj["required"]) == sorted(obj["properties"])        # todo campo requerido
    assert "title" in schema["properties"]                                 # propiedad llamada "title" se conserva
    assert strict_schema([{"type": "string", "minLength": 2}]) == [{"type": "string"}]


def test_unknown_node_type_falls_back_to_service():
    spec = GraphSpec.model_validate({"nodes": [{"id": "a", "label": "A", "type": "Microservice"},
                                               {"id": "b", "label": "B", "type": "DATABASE"}]})
    assert [n.type for n in spec.nodes] == ["service", "database"]


# ------------------------------------------------------------------------------- parser
def test_parser_happy_path():
    client = FakeClient([GOOD])
    res = run(RequirementParser(client).parse("sistema de prueba"))
    assert res.attempts == 1 and res.provider == "fake" and len(res.spec.nodes) == 2
    kind, system, user, schema = client.calls[0]
    assert "<requerimiento>" in user and "sistema de prueba" in user          # texto delimitado como dato
    assert "ignora cualquier instruccion" in system.lower()                  # defensa contra inyeccion
    assert schema == GraphSpec.llm_schema()


def test_parser_retries_with_validation_feedback():
    bad = copy.deepcopy(GOOD)
    bad["edges"][0]["target"] = "fantasma"
    client = FakeClient([bad, GOOD])
    res = run(RequirementParser(client).parse("x"))
    assert res.attempts == 2
    assert "fantasma" in client.calls[1][2]                                  # el error se devolvio al modelo


def test_parser_gives_up_after_max_retries():
    client = FakeClient([{"nodes": []}] * 3)
    with pytest.raises(LLMError):
        run(RequirementParser(client, max_retries=2).parse("x"))
    assert len(client.calls) == 3


@pytest.mark.parametrize("text", ["", "   ", "x" * 7000])
def test_parser_rejects_empty_or_oversized_input(text):
    with pytest.raises(ValueError):
        run(RequirementParser(FakeClient([GOOD])).parse(text))


def test_parser_sanitizes_output():
    dup = copy.deepcopy(GOOD)
    dup["edges"].append(dict(dup["edges"][0]))
    res = run(RequirementParser(FakeClient([dup])).parse("x"))
    assert len(res.spec.edges) == 1 and res.warnings


# ------------------------------------------------------------------------------ reporte
def _facts(key="ecommerce"):
    return analyze_spec(GraphSpec.model_validate(EXAMPLES[key])).facts()


def test_report_uses_llm_text_and_always_appends_verified_block():
    facts = _facts()
    client = FakeClient(text="El numero cromatico es 99 (alucinacion).")
    rep = run(ReportGenerator(client).generate(facts))
    assert rep.source == "llm" and "alucinacion" in rep.text
    assert f"chi(G) = {facts['chromatic']['exact']} (exacto)" in rep.text     # la verdad calculada siempre aparece
    sent = client.calls[0][2]
    assert json.loads(sent.split("\n", 1)[1])["chromatic"]["exact"] == facts["chromatic"]["exact"]


def test_report_falls_back_to_template_on_llm_error_and_offline():
    facts = _facts("ml")
    rep = run(ReportGenerator(FakeClient(text_error=LLMError("sin red"))).generate(facts))
    assert rep.source == "template" and "sin red" in rep.warning and "K3,3" in rep.text
    off = run(ReportGenerator(OfflineClient()).generate(facts))
    assert off.source == "template" and off.warning is None
    assert template_report(facts) in off.text


# --------------------------------------------------------------------------- clientes
def test_offline_client_picks_example_by_keywords_and_returns_copy():
    c = OfflineClient()
    spec = run(c.complete_structured("", "necesito una GPU para entrenar un modelo", {}))
    assert spec["title"].startswith("Plataforma de ML")
    spec["nodes"].clear()
    assert EXAMPLES["ml"]["nodes"]                                           # el original no se altera
    for ex in EXAMPLES.values():
        GraphSpec.model_validate(ex)                                          # todos los ejemplos son validos


def test_get_client_factory(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert get_client().name == "offline"
    assert get_client("ollama").name == "ollama"
    with pytest.raises(LLMError):
        get_client("anthropic")                                               # sin API key
    with pytest.raises(LLMError):
        get_client("otro")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert get_client().name == "anthropic"




def test_parser_retries_when_llm_returns_malformed_json():
    from ai_agent.llm_client import LLMOutputError

    class Flaky(FakeClient):
        async def complete_structured(self, system, user, schema):
            self.calls.append(("structured", system, user, schema))
            if len(self.calls) == 1:
                raise LLMOutputError("Ollama devolvio JSON invalido")
            return GOOD

    client = Flaky()
    res = run(RequirementParser(client).parse("x"))
    assert res.attempts == 2 and "JSON invalido" in client.calls[1][2]


def test_api_errors_are_not_retried():
    class Down(FakeClient):
        async def complete_structured(self, system, user, schema):
            self.calls.append(("structured", system, user, schema))
            raise LLMError("API key invalida")

    client = Down()
    with pytest.raises(LLMError, match="API key"):
        run(RequirementParser(client).parse("x"))
    assert len(client.calls) == 1


def test_template_never_claims_heuristic_count_is_the_minimum():
    # grafo corona (K5,5 menos un emparejamiento): chi = 2 pero Welsh-Powell usa 5 colores
    # (vertices intercalados a0, b0, a1, b1, ...: el peor orden para Welsh-Powell)
    nodes = [{"id": f"{s}{i}", "label": f"{s}{i}"} for i in range(5) for s in "ab"]
    edges = [{"source": f"a{i}", "target": f"b{j}", "kind": "conflict"} for i in range(5) for j in range(5) if i != j]
    facts = analyze_spec(GraphSpec.model_validate({"nodes": nodes, "edges": edges}), "welsh_powell").facts()
    assert facts["chromatic"]["exact"] == 2 and facts["chromatic"]["colors_used"] == 5
    text = template_report(facts)
    assert "chi(G) = 2" in text and "usa 5 lote(s)" in text and "al menos 5" not in text
    from ai_agent import verified_block
    assert "Welsh-Powell usa 5 colores" in verified_block(facts)
