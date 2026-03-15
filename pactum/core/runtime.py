"""
Pactum Runtime — the central execution engine for AI Contracts. 
Orchestrates contract execution, validation, tracing, snapshots, and plugins.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from pactum.core.contract import ContractSpec, get_contract_spec
from pactum.core.context import ExecutionContext, TracedLLM
from pactum.core.tracer import Tracer
from pactum.core.validator import (
    validate_inputs,
    validate_outputs,
    validate_memory_schema,
    run_invariants,
)
from pactum.core.exceptions import (
    PactumError,
    ContractViolationError,
    ReplayError,
    SnapshotNotFoundError,
)
from pactum.plugins.base import PluginRegistry
from pactum.plugins.llm_adapter import LLMAdapter, StubAdapter
from pactum.plugins.tool_adapter import ToolRegistry
from pactum.plugins.memory_backend import InMemoryBackend, TracedMemory
from pactum.snapshot.store import SnapshotStore


@dataclass
class ExecutionResult:
    """Result of a contract execution."""
    run_id: str
    snapshot_id: str
    outputs: dict[str, Any]
    trace: list[dict]
    success: bool = True
    error: Optional[str] = None
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "snapshot_id": self.snapshot_id,
            "outputs": self.outputs,
            "trace": self.trace,
            "success": self.success,
            "error": self.error,
            "total_tokens": self.total_tokens,
        }


class PactRuntime:
    """
    Central execution engine for AI Contracts.

    Orchestrates:
        - Input validation
        - Execution with tracing
        - Output validation & invariant checks
        - Snapshot creation
        - Plugin hook dispatch
        - Deterministic replay
    """

    def __init__(
        self,
        llm_adapter: Optional[LLMAdapter] = None,
        snapshot_store: Optional[SnapshotStore] = None,
        tool_registry: Optional[ToolRegistry] = None,
        plugin_registry: Optional[PluginRegistry] = None,
        seed: Optional[int] = None,
        config: Optional[dict] = None,
    ):
        self.llm_adapter = llm_adapter or StubAdapter()
        self.snapshot_store = snapshot_store or SnapshotStore()
        self.tool_registry = tool_registry or ToolRegistry()
        self.plugin_registry = plugin_registry or PluginRegistry()
        self.seed = seed
        self.config = config or {}
        self._runs: list[ExecutionResult] = []

    def run(
        self,
        contract_fn: Callable,
        inputs: dict[str, Any],
        memory_state: Optional[dict[str, Any]] = None,
        seed: Optional[int] = None,
    ) -> ExecutionResult:
        """
        Execute a contract function with full validation, tracing, and snapshotting.

        Args:
            contract_fn: A function decorated with @contract.
            inputs: Input dict matching the contract's input schema.
            memory_state: Optional initial memory state.
            seed: Optional seed for this specific run (overrides instance seed).

        Returns:
            ExecutionResult with run_id, snapshot_id, outputs, and trace.
        """
        spec = get_contract_spec(contract_fn)
        if spec is None:
            raise PactumError(
                "Function is not decorated with @contract. "
                "Use @contract(...) to define an AI Contract."
            )

        run_id = str(uuid.uuid4())[:8]
        run_seed = seed if seed is not None else (self.seed if self.seed is not None else random.randint(0, 2**32))
        tracer = Tracer()

        # Set up execution context
        rng = random.Random(run_seed)
        memory_backend = InMemoryBackend(initial_state=memory_state)
        traced_memory = TracedMemory(memory_backend, tracer)
        traced_llm = TracedLLM(self.llm_adapter, tracer, spec)
        tool_namespace = self.tool_registry.create_proxy_namespace(
            tracer=tracer,
            contract_name=spec.name,
            allowed_tools=spec.allowed_tools,
        )

        ctx = ExecutionContext(
            llm=traced_llm,
            tools=tool_namespace,
            memory=traced_memory,
            tracer=tracer,
            rng=rng,
            run_id=run_id,
            spec=spec,
        )

        # Validate inputs
        validate_inputs(spec, inputs)

        # Dispatch before_run hooks
        self.plugin_registry.dispatch_before_run(ctx, inputs)

        # Start trace
        tracer.start(spec.name, inputs)

        outputs = {}
        success = True
        error_msg = None

        try:
            # Execute the contract function
            outputs = contract_fn(ctx, inputs)

            # Validate outputs
            validate_outputs(spec, outputs)

            # Validate memory schema
            if spec.memory:
                validate_memory_schema(spec, memory_backend.get_state())

            # Run invariants
            run_invariants(spec, inputs, outputs)

            # End trace (success)
            tracer.end(spec.name, outputs, success=True)

        except PactumError as e:
            success = False
            error_msg = str(e)
            tracer.error(type(e).__name__, str(e))
            tracer.end(spec.name, outputs, success=False)
            raise

        except Exception as e:
            success = False
            error_msg = str(e)
            tracer.error("UnexpectedError", str(e))
            tracer.end(spec.name, outputs, success=False)
            raise PactumError(f"Contract execution failed: {e}") from e

        finally:
            # Create snapshot
            snapshot_data = {
                "run_id": run_id,
                "contract": spec.to_dict(),
                "inputs": inputs,
                "outputs": outputs,
                "trace": tracer.get_trace(),
                "seed": run_seed,
                "memory_state": memory_backend.get_state(),
                "success": success,
                "error": error_msg,
                "config": self.config,
            }

            try:
                snapshot_id = self.snapshot_store.save(snapshot_data)
            except Exception:
                snapshot_id = "save_failed"

            # Dispatch after_run hooks
            try:
                self.plugin_registry.dispatch_after_run(ctx, inputs, outputs, tracer.get_trace())
            except Exception:
                pass

            # Dispatch snapshot commit hook
            if snapshot_id != "save_failed":
                try:
                    self.plugin_registry.dispatch_on_snapshot_commit(snapshot_id, snapshot_data)
                except Exception:
                    pass

            result = ExecutionResult(
                run_id=run_id,
                snapshot_id=snapshot_id,
                outputs=outputs,
                trace=tracer.get_trace(),
                success=success,
                error=error_msg,
                total_tokens=tracer.total_tokens,
            )
            self._runs.append(result)

        return result

    def replay(
        self,
        snapshot_id: str,
        contract_fn: Optional[Callable] = None,
    ) -> ExecutionResult:
        """
        Replay a previous execution from a snapshot.

        Uses the same seed, inputs, and memory state to achieve
        deterministic reproduction.

        Args:
            snapshot_id: ID of the snapshot to replay.
            contract_fn: Optional contract function (if not provided, cannot re-execute).

        Returns:
            ExecutionResult from the replayed execution.
        """
        try:
            snapshot = self.snapshot_store.load(snapshot_id)
        except Exception as e:
            raise SnapshotNotFoundError(snapshot_id)

        if contract_fn is None:
            # Return the snapshot data as a "passive replay"
            return ExecutionResult(
                run_id=snapshot.get("run_id", "replay"),
                snapshot_id=snapshot_id,
                outputs=snapshot.get("outputs", {}),
                trace=snapshot.get("trace", []),
                success=snapshot.get("success", True),
                error=snapshot.get("error"),
                total_tokens=sum(
                    e.get("token_count", 0) or 0
                    for e in snapshot.get("trace", [])
                ),
            )

        # Active replay — re-execute with same seed and inputs
        return self.run(
            contract_fn=contract_fn,
            inputs=snapshot.get("inputs", {}),
            memory_state=snapshot.get("memory_state"),
            seed=snapshot.get("seed"),
        )

    @property
    def runs(self) -> list[ExecutionResult]:
        """Get all execution results from this runtime instance."""
        return list(self._runs)

    @property
    def last_run(self) -> Optional[ExecutionResult]:
        """Get the most recent execution result."""
        return self._runs[-1] if self._runs else None
