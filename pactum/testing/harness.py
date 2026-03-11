"""
Pactum Testing Harness — test cases, mock generation, and fuzzing.
"""

from __future__ import annotations

import copy
import random
import string
from typing import Any, Callable, Optional

from pactum.core.contract import ContractSpec, get_contract_spec
from pactum.core.runtime import PactRuntime, ExecutionResult
from pactum.core.exceptions import PactumError
from pactum.plugins.llm_adapter import StubAdapter, LLMResult
from pactum.snapshot.store import SnapshotStore


class ContractTestCase:
    """
    Load a snapshot and replay it to assert outputs match.
    Useful for regression testing contract behavior.
    """

    def __init__(
        self,
        snapshot_store: Optional[SnapshotStore] = None,
    ):
        self.snapshot_store = snapshot_store or SnapshotStore()

    def replay_and_assert(
        self,
        snapshot_id: str,
        contract_fn: Callable,
        runtime: Optional[PactRuntime] = None,
    ) -> ExecutionResult:
        """
        Replay a snapshot and assert outputs match the original.

        Returns the ExecutionResult if assertion passes.
        Raises AssertionError if outputs differ.
        """
        original = self.snapshot_store.load(snapshot_id)
        original_outputs = original.get("outputs", {})

        rt = runtime or PactRuntime(
            llm_adapter=StubAdapter(default_response=self._extract_llm_response(original)),
            snapshot_store=self.snapshot_store,
            seed=original.get("seed"),
        )

        result = rt.replay(snapshot_id, contract_fn)

        # Compare outputs
        for key, expected_value in original_outputs.items():
            actual_value = result.outputs.get(key)
            if actual_value != expected_value:
                raise AssertionError(
                    f"Output '{key}' mismatch: expected {expected_value!r}, got {actual_value!r}"
                )

        return result

    def _extract_llm_response(self, snapshot: dict) -> str:
        """Extract the first LLM response text from a snapshot trace."""
        for event in snapshot.get("trace", []):
            if event.get("event_type") == "llm_response":
                return event.get("data", {}).get("text", "stub response")
        return "stub response"


class MockGenerator:
    """
    Generate mock data from snapshots for testing.
    Creates a StubAdapter with recorded responses and tool stubs.
    """

    def __init__(self, snapshot_store: Optional[SnapshotStore] = None):
        self.snapshot_store = snapshot_store or SnapshotStore()

    def from_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        """
        Generate mock data from a snapshot.

        Returns:
            Dict with 'adapter' (StubAdapter), 'inputs', 'expected_outputs',
            'tool_responses', and 'memory_state'.
        """
        snapshot = self.snapshot_store.load(snapshot_id)
        trace = snapshot.get("trace", [])

        # Extract LLM responses
        llm_responses = {}
        for event in trace:
            if event.get("event_type") == "llm_request":
                prompt = event.get("data", {}).get("prompt", "")
                # Find the next llm_response event
                idx = trace.index(event)
                for subsequent in trace[idx + 1:]:
                    if subsequent.get("event_type") == "llm_response":
                        response_text = subsequent.get("data", {}).get("text", "")
                        # Use a key substring from the prompt
                        key = prompt[:50] if prompt else "default"
                        llm_responses[key] = response_text
                        break

        # Extract tool responses
        tool_responses = {}
        for event in trace:
            if event.get("event_type") == "tool_call":
                tool_name = event.get("data", {}).get("tool_name", "")
                idx = trace.index(event)
                for subsequent in trace[idx + 1:]:
                    if subsequent.get("event_type") == "tool_result":
                        result = subsequent.get("data", {}).get("result", "")
                        tool_responses[tool_name] = result
                        break

        # Create a stub adapter with the recorded responses
        first_response = next(iter(llm_responses.values()), "mock response")
        adapter = StubAdapter(
            default_response=first_response,
            responses=llm_responses,
        )

        return {
            "adapter": adapter,
            "inputs": snapshot.get("inputs", {}),
            "expected_outputs": snapshot.get("outputs", {}),
            "tool_responses": tool_responses,
            "memory_state": snapshot.get("memory_state", {}),
            "seed": snapshot.get("seed"),
        }

    def save_mocks(self, snapshot_id: str, output_path: str) -> str:
        """
        Generate mock data and save as a Python test fixture file.

        Args:
            snapshot_id: Snapshot to generate mocks from.
            output_path: Directory to write mock files to.

        Returns:
            Path to the generated mock file.
        """
        import os
        import json

        mocks = self.from_snapshot(snapshot_id)
        os.makedirs(output_path, exist_ok=True)

        fixture_path = os.path.join(output_path, f"mock_{snapshot_id[:8]}.json")
        fixture_data = {
            "snapshot_id": snapshot_id,
            "inputs": mocks["inputs"],
            "expected_outputs": mocks["expected_outputs"],
            "tool_responses": mocks["tool_responses"],
            "memory_state": mocks["memory_state"],
            "seed": mocks["seed"],
        }

        with open(fixture_path, "w") as f:
            json.dump(fixture_data, f, indent=2, default=str)

        return fixture_path


class FuzzRunner:
    """
    Basic fuzzing engine — generates random valid inputs and runs contracts
    to discover violations, crashes, or unexpected behavior.
    """

    def __init__(
        self,
        runtime: Optional[PactRuntime] = None,
        seed: Optional[int] = None,
    ):
        self.runtime = runtime or PactRuntime(
            llm_adapter=StubAdapter(),
            seed=seed,
        )
        self.rng = random.Random(seed)

    def fuzz(
        self,
        contract_fn: Callable,
        iterations: int = 100,
        input_generator: Optional[Callable] = None,
    ) -> FuzzReport:
        """
        Run fuzz testing on a contract.

        Args:
            contract_fn: Contract function to fuzz.
            iterations: Number of random inputs to try.
            input_generator: Optional custom function to generate inputs.
                             If None, generates random strings for each input field.

        Returns:
            FuzzReport with results summary.
        """
        spec = get_contract_spec(contract_fn)
        if spec is None:
            raise PactumError("Function is not decorated with @contract")

        results = FuzzReport(contract_name=spec.name, total_iterations=iterations)

        for i in range(iterations):
            if input_generator:
                inputs = input_generator(self.rng, spec)
            else:
                inputs = self._generate_random_inputs(spec)

            try:
                result = self.runtime.run(contract_fn, inputs, seed=self.rng.randint(0, 2**32))
                results.successes += 1
            except PactumError as e:
                results.violations.append({
                    "iteration": i,
                    "inputs": inputs,
                    "error_type": type(e).__name__,
                    "error": str(e),
                })
            except Exception as e:
                results.crashes.append({
                    "iteration": i,
                    "inputs": inputs,
                    "error_type": type(e).__name__,
                    "error": str(e),
                })

        return results

    def _generate_random_inputs(self, spec: ContractSpec) -> dict[str, Any]:
        """Generate random inputs matching the contract's input schema."""
        inputs = {}
        for field_name, field_type in spec.inputs.items():
            inputs[field_name] = self._random_value(field_type)
        return inputs

    def _random_value(self, field_type: type | str) -> Any:
        """Generate a random value for a given type."""
        type_name = field_type if isinstance(field_type, str) else field_type.__name__

        if type_name in ("str", "string"):
            length = self.rng.randint(1, 50)
            return "".join(self.rng.choices(string.ascii_letters + string.digits + " ", k=length))
        elif type_name in ("int", "integer"):
            return self.rng.randint(-1000, 1000)
        elif type_name in ("float", "number"):
            return self.rng.uniform(-1000, 1000)
        elif type_name in ("bool", "boolean"):
            return self.rng.choice([True, False])
        elif type_name in ("list", "array"):
            return [self._random_value("str") for _ in range(self.rng.randint(0, 5))]
        elif type_name in ("dict", "object"):
            return {f"key_{i}": self._random_value("str") for i in range(self.rng.randint(0, 3))}
        else:
            return "fuzz_" + "".join(self.rng.choices(string.ascii_lowercase, k=8))


class FuzzReport:
    """Summary of a fuzz testing run."""

    def __init__(self, contract_name: str, total_iterations: int):
        self.contract_name = contract_name
        self.total_iterations = total_iterations
        self.successes: int = 0
        self.violations: list[dict] = []
        self.crashes: list[dict] = []

    @property
    def failure_rate(self) -> float:
        total_failures = len(self.violations) + len(self.crashes)
        return total_failures / self.total_iterations if self.total_iterations > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "contract_name": self.contract_name,
            "total_iterations": self.total_iterations,
            "successes": self.successes,
            "violations": len(self.violations),
            "crashes": len(self.crashes),
            "failure_rate": f"{self.failure_rate:.1%}",
            "violation_details": self.violations[:10],  # First 10
            "crash_details": self.crashes[:10],
        }

    def summary(self) -> str:
        return (
            f"Fuzz Report: {self.contract_name}\n"
            f"  Iterations: {self.total_iterations}\n"
            f"  Successes:  {self.successes}\n"
            f"  Violations: {len(self.violations)}\n"
            f"  Crashes:    {len(self.crashes)}\n"
            f"  Failure Rate: {self.failure_rate:.1%}"
        )
