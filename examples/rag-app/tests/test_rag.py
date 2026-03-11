"""Tests for the RAG app example contract."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pactum import PactRuntime
from pactum.plugins.llm_adapter import StubAdapter
from pactum.plugins.tool_adapter import ToolRegistry
from examples.rag_app_contract import rag_answer


def _make_runtime():
    stub = StubAdapter(default_response="Based on the context, electronics can be returned within 30 days.")
    tools = ToolRegistry()
    tools.register("document_retriever", lambda q, top_k=5: [
        "Electronics return policy: 30-day return window.",
        "All items must be in original packaging.",
    ])

    return PactRuntime(llm_adapter=stub, tool_registry=tools, seed=42)


def test_rag_answer_basic():
    runtime = _make_runtime()
    result = runtime.run(rag_answer, {"question": "What is the return policy?"})

    assert result.success
    assert "answer" in result.outputs
    assert "sources" in result.outputs
    assert isinstance(result.outputs["sources"], list)


def test_rag_answer_deterministic():
    """Two runs with the same seed should produce identical outputs."""
    runtime = _make_runtime()

    result1 = runtime.run(rag_answer, {"question": "How to return?", "seed": 42}, seed=42)
    result2 = runtime.run(rag_answer, {"question": "How to return?", "seed": 42}, seed=42)

    assert result1.outputs == result2.outputs
