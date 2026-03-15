"""
Pactum Validator — enforces contract rules: input/output types, 
memory schema, tool access, non-determinism budget, and invariants.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from pactum.core.contract import ContractSpec, MemorySchema
from pactum.core.exceptions import (
    InputValidationError,
    OutputValidationError,
    ToolAccessDeniedError,
    NonDetBudgetExceededError,
    MemorySchemaError,
    InvariantError,
)


# Mapping from string type names to Python types
_TYPE_MAP: dict[str, type] = {
    "str": str,
    "string": str,
    "int": int,
    "integer": int,
    "float": float,
    "number": float,
    "bool": bool,
    "boolean": bool,
    "list": list,
    "array": list,
    "dict": dict,
    "object": dict,
}


def _resolve_type(t: type | str) -> type:
    """Resolve a type specification to an actual Python type."""
    if isinstance(t, type):
        return t
    return _TYPE_MAP.get(t.lower(), str)


def validate_inputs(spec: ContractSpec, inputs: dict[str, Any]) -> None:
    """
    Validate that inputs match the contract's declared input schema.
    Raises InputValidationError if validation fails.
    """
    # Check for missing required inputs
    for field_name, expected_type in spec.inputs.items():
        if field_name not in inputs:
            raise InputValidationError(
                spec.name, field_name,
                expected=f"{expected_type}",
                got="missing"
            )
        value = inputs[field_name]
        resolved = _resolve_type(expected_type)
        if not isinstance(value, resolved):
            raise InputValidationError(
                spec.name, field_name,
                expected=resolved.__name__,
                got=type(value).__name__
            )


def validate_outputs(spec: ContractSpec, outputs: dict[str, Any]) -> None:
    """
    Validate that outputs match the contract's declared output schema.
    Raises OutputValidationError if validation fails.
    """
    if not isinstance(outputs, dict):
        raise OutputValidationError(
            spec.name, "<root>",
            expected="dict",
            got=type(outputs).__name__
        )

    for field_name, expected_type in spec.outputs.items():
        if field_name not in outputs:
            raise OutputValidationError(
                spec.name, field_name,
                expected=f"{expected_type}",
                got="missing"
            )
        value = outputs[field_name]
        resolved = _resolve_type(expected_type)
        if not isinstance(value, resolved):
            raise OutputValidationError(
                spec.name, field_name,
                expected=resolved.__name__,
                got=type(value).__name__
            )


def validate_tool_access(spec: ContractSpec, tool_name: str) -> None:
    """
    Validate that a tool is in the contract's allowed_tools list.
    Raises ToolAccessDeniedError if not allowed.
    """
    if spec.allowed_tools is not None and tool_name not in spec.allowed_tools:
        raise ToolAccessDeniedError(spec.name, tool_name, spec.allowed_tools)


def validate_nondet_budget(spec: ContractSpec, tokens_used: int) -> None:
    """
    Validate that the token usage hasn't exceeded the non-determinism budget.
    Raises NonDetBudgetExceededError if exceeded.
    """
    if spec.nondet_budget is not None:
        budget = spec.nondet_budget.get("tokens")
        if budget is not None and tokens_used > budget:
            raise NonDetBudgetExceededError(spec.name, budget, tokens_used)


def validate_memory_schema(spec: ContractSpec, memory_state: dict[str, Any]) -> None:
    """
    Validate that the memory state conforms to the declared schema.
    Raises MemorySchemaError if validation fails.
    """
    if spec.memory is None:
        return

    for key in memory_state:
        if not spec.memory.validate_key(key):
            raise MemorySchemaError(
                spec.name, key,
                f"Key '{key}' is not declared in the memory schema"
            )

    # Validate types if specified
    for key, key_spec in spec.memory.keys.items():
        if key in memory_state:
            value = memory_state[key]
            expected_type = key_spec.get("type", "").lower()
            if expected_type == "json" and not isinstance(value, (dict, list)):
                raise MemorySchemaError(
                    spec.name, key,
                    f"Expected JSON (dict or list), got {type(value).__name__}"
                )
            elif expected_type == "string" and not isinstance(value, str):
                raise MemorySchemaError(
                    spec.name, key,
                    f"Expected string, got {type(value).__name__}"
                )


def run_invariants(
    spec: ContractSpec,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
) -> None:
    """
    Run all user-defined invariant functions on the inputs/outputs.
    Raises InvariantError if any invariant fails.
    """
    if spec.invariants is None:
        return

    for i, invariant_fn in enumerate(spec.invariants):
        name = getattr(invariant_fn, "__name__", f"invariant_{i}")
        try:
            result = invariant_fn(inputs, outputs)
            if result is False:
                raise InvariantError(spec.name, name, "Invariant returned False")
        except InvariantError:
            raise
        except Exception as e:
            raise InvariantError(spec.name, name, str(e))
