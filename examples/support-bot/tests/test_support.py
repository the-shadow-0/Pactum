"""Tests for the support bot example contract."""

import sys
import os

# Ensure the project root is in the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from pactum import PactRuntime
from pactum.plugins.llm_adapter import StubAdapter
from pactum.plugins.tool_adapter import ToolRegistry
from examples.support_bot_contract import support_reply


def _make_runtime():
    stub = StubAdapter(default_response="I'll check on your order right away!")
    tools = ToolRegistry()
    tools.register("kb_retriever", lambda query, top_k=3: ["Order FAQ: Check tracking page."])
    tools.register("crm_get", lambda customer_id: {"name": "Test User", "tier": "gold"})

    return PactRuntime(llm_adapter=stub, tool_registry=tools, seed=42)


def test_support_reply_basic():
    runtime = _make_runtime()
    result = runtime.run(support_reply, {"query": "Where's my order?", "customer_id": "C-12345"})

    assert result.success
    assert "reply" in result.outputs
    assert "intent" in result.outputs
    assert result.snapshot_id != "save_failed"


def test_support_reply_snapshot_created():
    runtime = _make_runtime()
    result = runtime.run(support_reply, {"query": "Refund please", "customer_id": "C-99"})

    # Verify snapshot was stored
    snapshots = runtime.snapshot_store.list()
    assert len(snapshots) > 0

    # Verify we can load the snapshot
    snapshot = runtime.snapshot_store.load(result.snapshot_id)
    assert snapshot["inputs"]["customer_id"] == "C-99"
