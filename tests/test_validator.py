"""
Tests for the Pactum Validator — input/output validation, tool access,
non-determinism budget, memory schema, and invariants.
"""

import pytest
from pactum.core.contract import ContractSpec, MemorySchema
from pactum.core.validator import (
    validate_inputs,
    validate_outputs,
    validate_tool_access,
    validate_nondet_budget,
    validate_memory_schema,
    run_invariants,
)
from pactum.core.exceptions import (
    InputValidationError,
    OutputValidationError,
    ToolAccessDeniedError,
    NonDetBudgetExceededError,
    MemorySchemaError,
    InvariantError,
)


def _make_spec(**kwargs):
    defaults = {"name": "test:v1", "inputs": {"q": str}, "outputs": {"r": str}}
    defaults.update(kwargs)
    return ContractSpec(**defaults)


class TestInputValidation:
    def test_valid_inputs(self):
        spec = _make_spec(inputs={"q": str, "n": int})
        validate_inputs(spec, {"q": "hello", "n": 5})  # Should not raise

    def test_missing_input(self):
        spec = _make_spec(inputs={"q": str, "n": int})
        with pytest.raises(InputValidationError, match="missing"):
            validate_inputs(spec, {"q": "hello"})

    def test_wrong_type(self):
        spec = _make_spec(inputs={"q": str})
        with pytest.raises(InputValidationError, match="expected str"):
            validate_inputs(spec, {"q": 42})

    def test_string_type_names(self):
        spec = _make_spec(inputs={"q": "string", "n": "integer"})
        validate_inputs(spec, {"q": "hello", "n": 5})

    def test_string_type_wrong(self):
        spec = _make_spec(inputs={"q": "string"})
        with pytest.raises(InputValidationError):
            validate_inputs(spec, {"q": 123})


class TestOutputValidation:
    def test_valid_outputs(self):
        spec = _make_spec(outputs={"r": str, "count": int})
        validate_outputs(spec, {"r": "result", "count": 3})

    def test_missing_output(self):
        spec = _make_spec(outputs={"r": str, "count": int})
        with pytest.raises(OutputValidationError, match="missing"):
            validate_outputs(spec, {"r": "result"})

    def test_wrong_type_output(self):
        spec = _make_spec(outputs={"r": str})
        with pytest.raises(OutputValidationError, match="expected str"):
            validate_outputs(spec, {"r": 42})

    def test_non_dict_output(self):
        spec = _make_spec(outputs={"r": str})
        with pytest.raises(OutputValidationError, match="expected dict"):
            validate_outputs(spec, "not a dict")


class TestToolAccess:
    def test_allowed_tool(self):
        spec = _make_spec(allowed_tools=["search", "calc"])
        validate_tool_access(spec, "search")  # Should not raise

    def test_denied_tool(self):
        spec = _make_spec(allowed_tools=["search", "calc"])
        with pytest.raises(ToolAccessDeniedError, match="forbidden"):
            validate_tool_access(spec, "forbidden")

    def test_no_restriction(self):
        spec = _make_spec(allowed_tools=None)
        validate_tool_access(spec, "anything")  # Should not raise


class TestNonDetBudget:
    def test_within_budget(self):
        spec = _make_spec(nondet_budget={"tokens": 100})
        validate_nondet_budget(spec, 50)  # Should not raise

    def test_exceeded_budget(self):
        spec = _make_spec(nondet_budget={"tokens": 100})
        with pytest.raises(NonDetBudgetExceededError, match="exceeded"):
            validate_nondet_budget(spec, 150)

    def test_no_budget(self):
        spec = _make_spec(nondet_budget=None)
        validate_nondet_budget(spec, 99999)  # Should not raise

    def test_exact_budget(self):
        spec = _make_spec(nondet_budget={"tokens": 100})
        validate_nondet_budget(spec, 100)  # Exactly at budget — should not raise


class TestMemorySchema:
    def test_valid_memory(self):
        mem = MemorySchema(keys={"profile": {"type": "json"}})
        spec = _make_spec(memory=mem)
        validate_memory_schema(spec, {"profile": {"name": "Alice"}})

    def test_undeclared_key(self):
        mem = MemorySchema(keys={"profile": {"type": "json"}})
        spec = _make_spec(memory=mem)
        with pytest.raises(MemorySchemaError, match="not declared"):
            validate_memory_schema(spec, {"unknown_key": "value"})

    def test_wrong_type_json(self):
        mem = MemorySchema(keys={"profile": {"type": "json"}})
        spec = _make_spec(memory=mem)
        with pytest.raises(MemorySchemaError, match="Expected JSON"):
            validate_memory_schema(spec, {"profile": "not json"})

    def test_no_memory_schema(self):
        spec = _make_spec(memory=None)
        validate_memory_schema(spec, {"any": "thing"})  # Should not raise


class TestInvariants:
    def test_passing_invariant(self):
        def check(inputs, outputs):
            return len(outputs["r"]) > 0

        spec = _make_spec(invariants=[check])
        run_invariants(spec, {"q": "hello"}, {"r": "world"})

    def test_failing_invariant(self):
        def check(inputs, outputs):
            return False

        spec = _make_spec(invariants=[check])
        with pytest.raises(InvariantError, match="returned False"):
            run_invariants(spec, {"q": "hello"}, {"r": "world"})

    def test_exception_in_invariant(self):
        def check(inputs, outputs):
            raise ValueError("something broke")

        spec = _make_spec(invariants=[check])
        with pytest.raises(InvariantError, match="something broke"):
            run_invariants(spec, {"q": "hello"}, {"r": "world"})

    def test_no_invariants(self):
        spec = _make_spec(invariants=None)
        run_invariants(spec, {}, {})  # Should not raise
