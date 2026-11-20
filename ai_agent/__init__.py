"""ai_agent: capa de IA generativa (lenguaje natural -> JSON -> reporte tecnico)."""
from .browser_client import BrowserClient
from .llm_client import (DEFAULT_ANTHROPIC_MODEL, AnthropicClient, LLMClient, LLMError, OfflineClient,
                         OllamaClient, get_client)
from .offline_examples import EXAMPLES
from .parser import ParseResult, RequirementParser
from .reporter import Report, ReportGenerator, template_report, verified_block
from .schemas import EdgeSpec, GraphSpec, NodeSpec, slugify

__all__ = [
    "LLMClient", "LLMError", "AnthropicClient", "OllamaClient", "OfflineClient", "BrowserClient", "get_client",
    "DEFAULT_ANTHROPIC_MODEL", "GraphSpec", "NodeSpec", "EdgeSpec", "slugify", "EXAMPLES",
    "RequirementParser", "ParseResult", "ReportGenerator", "Report", "template_report", "verified_block",
]
