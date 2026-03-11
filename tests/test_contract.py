"""
Tests for the Contract DSL — @contract decorator, ContractSpec, MemorySchema.
"""

import pytest
from pactum.core.contract import (
    contract,
    ContractSpec,
    MemorySchema,
    get_contract_spec,
    is_contract,
)


class TestContractDecorator:
    def test_basic_contract(self):
        @contract(
            name="test:v1",
            inputs={"query": str},
            outputs={"answer": str},
        )
        def my_fn(ctx, inputs):
            return {"answer": "hello"}

        assert is_contract(my_fn)
        spec = get_contract_spec(my_fn)
        assert spec is not None
        assert spec.name == "test:v1"
        assert spec.inputs == {"query": str}
        assert spec.outputs == {"answer": str}

    def test_contract_with_memory(self):
        mem = MemorySchema(keys={"profile": {"type": "json", "version": 1}})

        @contract(
            name="mem_test:v1",
            inputs={"x": str},
            outputs={"y": str},
            memory=mem,
        )
        def fn(ctx, inputs):
            return {"y": inputs["x"]}

        spec = get_contract_spec(fn)
        assert spec.memory is not None
        assert spec.memory.validate_key("profile")
        assert not spec.memory.validate_key("nonexistent")

    def test_contract_with_tools_and_budget(self):
        @contract(
            name="tools_test:v1",
            inputs={"q": str},
            outputs={"r": str},
            allowed_tools=["search", "calc"],
            nondet_budget={"tokens": 100},
        )
        def fn(ctx, inputs):
            return {"r": "result"}

        spec = get_contract_spec(fn)
        assert spec.allowed_tools == ["search", "calc"]
        assert spec.nondet_budget == {"tokens": 100}

    def test_decorated_function_callable(self):
        @contract(name="call_test:v1", inputs={"a": str}, outputs={"b": str})
        def fn(ctx, inputs):
            return {"b": inputs["a"].upper()}

        result = fn(None, {"a": "hello"})
        assert result == {"b": "HELLO"}

    def test_is_contract_false_for_plain_fn(self):
        def plain_fn():
            pass

        assert not is_contract(plain_fn)
        assert get_contract_spec(plain_fn) is None

    def test_contract_with_invariants(self):
        def check_non_empty(inputs, outputs):
            return len(outputs["r"]) > 0

        @contract(
            name="inv_test:v1",
            inputs={"q": str},
            outputs={"r": str},
            invariants=[check_non_empty],
        )
        def fn(ctx, inputs):
            return {"r": "result"}

        spec = get_contract_spec(fn)
        assert spec.invariants is not None
        assert len(spec.invariants) == 1


class TestContractSpec:
    def test_base_name(self):
        spec = ContractSpec(name="support:v2", inputs={}, outputs={})
        assert spec.base_name == "support"
        assert spec.contract_version == "v2"

    def test_base_name_no_version(self):
        spec = ContractSpec(name="support", inputs={}, outputs={})
        assert spec.base_name == "support"
        assert spec.contract_version == "1"

    def test_serialization(self):
        spec = ContractSpec(
            name="test:v1",
            inputs={"query": str, "count": int},
            outputs={"result": str},
            memory=MemorySchema(keys={"k1": {"type": "json"}}),
            allowed_tools=["tool1"],
            nondet_budget={"tokens": 50},
        )

        data = spec.to_dict()
        assert data["name"] == "test:v1"
        assert data["inputs"] == {"query": "str", "count": "int"}
        assert data["outputs"] == {"result": "str"}

        # Round-trip
        spec2 = ContractSpec.from_dict(data)
        assert spec2.name == spec.name
        assert spec2.allowed_tools == spec.allowed_tools
        assert spec2.nondet_budget == spec.nondet_budget


class TestMemorySchema:
    def test_basic(self):
        schema = MemorySchema(keys={"profile": {"type": "json", "version": 1}})
        assert schema.validate_key("profile")
        assert not schema.validate_key("other")
        assert schema.get_key_spec("profile") == {"type": "json", "version": 1}

    def test_empty_schema(self):
        schema = MemorySchema()
        assert not schema.validate_key("anything")

    def test_serialization(self):
        schema = MemorySchema(keys={"k": {"type": "string"}})
        data = schema.to_dict()
        schema2 = MemorySchema.from_dict(data)
        assert schema2.keys == schema.keys
