"""
Tests for PactRuntime — execution, snapshotting, replay, and plugin hooks.
"""

import pytest
import tempfile
import os

from pactum.core.contract import contract, MemorySchema
from pactum.core.runtime import PactRuntime, ExecutionResult
from pactum.core.exceptions import (
    PactumError,
    InputValidationError,
    OutputValidationError,
    NonDetBudgetExceededError,
)
from pactum.plugins.llm_adapter import StubAdapter
from pactum.plugins.tool_adapter import ToolRegistry
from pactum.plugins.base import PactumPlugin, PluginRegistry
from pactum.snapshot.store import SnapshotStore


@contract(
    name="simple:v1",
    inputs={"name": str},
    outputs={"greeting": str},
)
def simple_contract(ctx, inputs):
    result = ctx.llm.complete(f"Hello {inputs['name']}", max_tokens=10)
    return {"greeting": result.text}


@contract(
    name="with_tools:v1",
    inputs={"query": str},
    outputs={"answer": str},
    allowed_tools=["search"],
)
def contract_with_tools(ctx, inputs):
    results = ctx.tools.search(inputs["query"])
    return {"answer": str(results)}


@contract(
    name="with_budget:v1",
    inputs={"q": str},
    outputs={"r": str},
    nondet_budget={"tokens": 3},
)
def contract_with_budget(ctx, inputs):
    result = ctx.llm.complete(inputs["q"], max_tokens=10)
    return {"r": result.text}


@contract(
    name="bad_output:v1",
    inputs={"x": str},
    outputs={"y": int},
)
def bad_output_contract(ctx, inputs):
    return {"y": "not_an_int"}


def _make_runtime(tmpdir, **kwargs):
    defaults = {
        "llm_adapter": StubAdapter(default_response="Hello!", default_tokens=2),
        "snapshot_store": SnapshotStore(os.path.join(tmpdir, "snapshots")),
        "seed": 42,
    }
    defaults.update(kwargs)
    return PactRuntime(**defaults)


class TestPactRuntime:
    def test_basic_run(self, tmp_path):
        runtime = _make_runtime(str(tmp_path))
        result = runtime.run(simple_contract, {"name": "World"})

        assert result.success
        assert result.outputs["greeting"] == "Hello!"
        assert result.snapshot_id != "save_failed"
        assert result.run_id

    def test_run_creates_snapshot(self, tmp_path):
        runtime = _make_runtime(str(tmp_path))
        result = runtime.run(simple_contract, {"name": "Test"})

        snapshots = runtime.snapshot_store.list()
        assert len(snapshots) == 1
        assert snapshots[0]["snapshot_id"] == result.snapshot_id

    def test_run_with_tools(self, tmp_path):
        tools = ToolRegistry()
        tools.register("search", lambda q: f"Results for: {q}")

        runtime = _make_runtime(str(tmp_path), tool_registry=tools)
        result = runtime.run(contract_with_tools, {"query": "test"})

        assert result.success
        assert "Results for: test" in result.outputs["answer"]

    def test_input_validation_fails(self, tmp_path):
        runtime = _make_runtime(str(tmp_path))
        with pytest.raises(InputValidationError):
            runtime.run(simple_contract, {"name": 42})

    def test_output_validation_fails(self, tmp_path):
        runtime = _make_runtime(str(tmp_path))
        with pytest.raises(OutputValidationError):
            runtime.run(bad_output_contract, {"x": "hello"})

    def test_nondet_budget_exceeded(self, tmp_path):
        # StubAdapter returns 2 tokens by default — budget is 3, so should exceed after twice
        stub = StubAdapter(default_response="Hey!", default_tokens=4)
        runtime = _make_runtime(str(tmp_path), llm_adapter=stub)

        with pytest.raises(NonDetBudgetExceededError):
            runtime.run(contract_with_budget, {"q": "test"})

    def test_seeded_determinism(self, tmp_path):
        runtime1 = _make_runtime(str(tmp_path), seed=123)
        runtime2 = _make_runtime(str(tmp_path), seed=123)

        result1 = runtime1.run(simple_contract, {"name": "A"}, seed=123)
        result2 = runtime2.run(simple_contract, {"name": "A"}, seed=123)

        assert result1.outputs == result2.outputs

    def test_non_contract_function(self, tmp_path):
        def plain_fn(ctx, inputs):
            return {}

        runtime = _make_runtime(str(tmp_path))
        with pytest.raises(PactumError, match="not decorated"):
            runtime.run(plain_fn, {})

    def test_runs_history(self, tmp_path):
        runtime = _make_runtime(str(tmp_path))
        runtime.run(simple_contract, {"name": "A"})
        runtime.run(simple_contract, {"name": "B"})

        assert len(runtime.runs) == 2
        assert runtime.last_run.outputs["greeting"] == "Hello!"


class TestReplay:
    def test_passive_replay(self, tmp_path):
        runtime = _make_runtime(str(tmp_path))
        result = runtime.run(simple_contract, {"name": "Replay"})

        replayed = runtime.replay(result.snapshot_id)
        assert replayed.outputs == result.outputs
        assert replayed.success

    def test_active_replay(self, tmp_path):
        runtime = _make_runtime(str(tmp_path))
        result = runtime.run(simple_contract, {"name": "Replay"})

        replayed = runtime.replay(result.snapshot_id, simple_contract)
        assert replayed.success
        assert replayed.outputs["greeting"] == "Hello!"


class TestPluginHooks:
    def test_before_after_hooks(self, tmp_path):
        calls = []

        class TestPlugin(PactumPlugin):
            @property
            def name(self):
                return "test-plugin"

            def before_run(self, context, inputs):
                calls.append(("before", inputs))

            def after_run(self, context, inputs, outputs, trace):
                calls.append(("after", outputs))

        registry = PluginRegistry()
        registry.register(TestPlugin())

        runtime = _make_runtime(str(tmp_path), plugin_registry=registry)
        runtime.run(simple_contract, {"name": "Plugin"})

        assert len(calls) == 2
        assert calls[0][0] == "before"
        assert calls[1][0] == "after"
