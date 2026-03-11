"""
Integration test — end-to-end: define contract → run → snapshot → replay → assert.
"""

import pytest
import os

from pactum.core.contract import contract, MemorySchema
from pactum.core.runtime import PactRuntime
from pactum.plugins.llm_adapter import StubAdapter
from pactum.plugins.tool_adapter import ToolRegistry
from pactum.snapshot.store import SnapshotStore
from pactum.testing.harness import ContractTestCase, MockGenerator, FuzzRunner


@contract(
    name="integration_test:v1",
    inputs={"question": str, "context": str},
    outputs={"answer": str, "confidence": str},
    allowed_tools=["retriever"],
    nondet_budget={"tokens": 100},
)
def integration_contract(ctx, inputs):
    """A contract for integration testing."""
    docs = ctx.tools.retriever(inputs["question"])
    ctx.trace("retrieved_docs", docs)

    prompt = f"Q: {inputs['question']}\nContext: {inputs['context']}\nDocs: {docs}\nAnswer:"
    result = ctx.llm.complete(prompt, temperature=0.5, max_tokens=50)

    return {"answer": result.text, "confidence": "high"}


def _create_runtime(tmp_path):
    stub = StubAdapter(
        default_response="This is the integration test answer.",
        default_tokens=7,
    )
    tools = ToolRegistry()
    tools.register("retriever", lambda q: [f"Doc about: {q}"])

    return PactRuntime(
        llm_adapter=stub,
        snapshot_store=SnapshotStore(os.path.join(str(tmp_path), "snapshots")),
        tool_registry=tools,
        seed=42,
    )


class TestEndToEnd:
    def test_full_lifecycle(self, tmp_path):
        """Full lifecycle: run → snapshot → list → load → replay → assert."""
        runtime = _create_runtime(tmp_path)

        # 1. Run the contract
        result = runtime.run(
            integration_contract,
            {"question": "What is Pactum?", "context": "AI contracts framework"},
        )

        assert result.success
        assert result.outputs["answer"] == "This is the integration test answer."
        assert result.outputs["confidence"] == "high"
        assert result.snapshot_id != "save_failed"

        # 2. Verify snapshot was stored
        snapshots = runtime.snapshot_store.list()
        assert len(snapshots) == 1

        # 3. Load the snapshot
        snapshot = runtime.snapshot_store.load(result.snapshot_id)
        assert snapshot["inputs"]["question"] == "What is Pactum?"
        assert snapshot["success"] is True

        # 4. Verify trace has expected events
        trace = snapshot["trace"]
        event_types = [e["event_type"] for e in trace]
        assert "contract_start" in event_types
        assert "contract_end" in event_types
        assert "tool_call" in event_types
        assert "llm_request" in event_types
        assert "llm_response" in event_types
        assert "user_trace" in event_types

        # 5. Passive replay
        replayed = runtime.replay(result.snapshot_id)
        assert replayed.outputs == result.outputs
        assert replayed.success

        # 6. Active replay (re-execute)
        replayed_active = runtime.replay(result.snapshot_id, integration_contract)
        assert replayed_active.success
        assert replayed_active.outputs == result.outputs

    def test_deterministic_runs(self, tmp_path):
        """Two runs with same seed produce identical outputs."""
        runtime = _create_runtime(tmp_path)

        r1 = runtime.run(
            integration_contract,
            {"question": "Test?", "context": "Testing"},
            seed=999,
        )
        r2 = runtime.run(
            integration_contract,
            {"question": "Test?", "context": "Testing"},
            seed=999,
        )

        assert r1.outputs == r2.outputs

    def test_fuzz_runner(self, tmp_path):
        """Fuzz testing should execute without crashes."""
        runtime = _create_runtime(tmp_path)
        runner = FuzzRunner(runtime=runtime, seed=42)

        report = runner.fuzz(integration_contract, iterations=20)
        assert report.total_iterations == 20
        assert report.successes + len(report.violations) + len(report.crashes) == 20

    def test_mock_generation(self, tmp_path):
        """Generate and verify mock data from a snapshot."""
        runtime = _create_runtime(tmp_path)
        result = runtime.run(
            integration_contract,
            {"question": "Mock test?", "context": "Mocking"},
        )

        generator = MockGenerator(runtime.snapshot_store)
        mocks = generator.from_snapshot(result.snapshot_id)

        assert "adapter" in mocks
        assert isinstance(mocks["adapter"], StubAdapter)
        assert mocks["inputs"]["question"] == "Mock test?"
        assert mocks["expected_outputs"] == result.outputs

    def test_mock_save(self, tmp_path):
        """Save mocks to disk and verify file created."""
        runtime = _create_runtime(tmp_path)
        result = runtime.run(
            integration_contract,
            {"question": "Save test?", "context": "Saving"},
        )

        generator = MockGenerator(runtime.snapshot_store)
        mock_dir = os.path.join(str(tmp_path), "mocks")
        mock_path = generator.save_mocks(result.snapshot_id, mock_dir)

        assert os.path.exists(mock_path)
        assert mock_path.endswith(".json")

    def test_snapshot_diff(self, tmp_path):
        """Diff between two snapshots shows differences."""
        runtime = _create_runtime(tmp_path)

        r1 = runtime.run(integration_contract, {"question": "Q1", "context": "C1"})
        r2 = runtime.run(integration_contract, {"question": "Q2", "context": "C2"})

        diff = runtime.snapshot_store.diff(r1.snapshot_id, r2.snapshot_id)
        assert "differences" in diff
        assert "inputs" in diff["differences"]
