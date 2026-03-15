"""
Pactum Contract DSL — declarative, versioned, enforceable interfaces for AI components. 
"""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, Callable, Optional


@dataclass
class MemorySchema:
    """
    Defines the expected keys and types for memory used by a contract.

    Example:
        MemorySchema(keys={"customer_profile": {"type": "json", "version": 1}})
    """
    keys: dict[str, dict[str, Any]] = field(default_factory=dict)

    def validate_key(self, key: str) -> bool:
        """Check if a key is declared in the schema."""
        return key in self.keys

    def get_key_spec(self, key: str) -> Optional[dict[str, Any]]:
        """Get the spec for a memory key."""
        return self.keys.get(key)

    def to_dict(self) -> dict:
        return {"keys": self.keys}

    @classmethod
    def from_dict(cls, data: dict) -> MemorySchema:
        return cls(keys=data.get("keys", {}))


@dataclass
class ContractSpec:
    """
    Specification of an AI Contract — defines inputs, outputs, memory,
    allowed tools, non-determinism budget, and invariants.
    """
    name: str
    inputs: dict[str, type | str]
    outputs: dict[str, type | str]
    memory: Optional[MemorySchema] = None
    allowed_tools: Optional[list[str]] = None
    nondet_budget: Optional[dict[str, int]] = None
    invariants: Optional[list[Callable]] = None
    version: str = "1"

    @property
    def base_name(self) -> str:
        """Contract name without version suffix."""
        if ":" in self.name:
            return self.name.rsplit(":", 1)[0]
        return self.name

    @property
    def contract_version(self) -> str:
        """Extract version from contract name (e.g., 'v1' from 'name:v1')."""
        if ":" in self.name:
            return self.name.rsplit(":", 1)[1]
        return self.version

    def to_dict(self) -> dict:
        """Serialize to a dictionary for snapshotting."""
        def _type_to_str(t: type | str) -> str:
            if isinstance(t, type):
                return t.__name__
            return str(t)

        return {
            "name": self.name,
            "inputs": {k: _type_to_str(v) for k, v in self.inputs.items()},
            "outputs": {k: _type_to_str(v) for k, v in self.outputs.items()},
            "memory": self.memory.to_dict() if self.memory else None,
            "allowed_tools": self.allowed_tools,
            "nondet_budget": self.nondet_budget,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ContractSpec:
        """Deserialize from a dictionary."""
        TYPE_MAP = {"str": str, "int": int, "float": float, "bool": bool, "list": list, "dict": dict}

        def _str_to_type(s: str) -> type | str:
            return TYPE_MAP.get(s, s)

        return cls(
            name=data["name"],
            inputs={k: _str_to_type(v) for k, v in data["inputs"].items()},
            outputs={k: _str_to_type(v) for k, v in data["outputs"].items()},
            memory=MemorySchema.from_dict(data["memory"]) if data.get("memory") else None,
            allowed_tools=data.get("allowed_tools"),
            nondet_budget=data.get("nondet_budget"),
            version=data.get("version", "1"),
        )


def contract(
    name: str,
    inputs: dict[str, type | str],
    outputs: dict[str, type | str],
    memory: Optional[MemorySchema] = None,
    allowed_tools: Optional[list[str]] = None,
    nondet_budget: Optional[dict[str, int]] = None,
    invariants: Optional[list[Callable]] = None,
) -> Callable:
    """
    Decorator to define an AI Contract on a function.

    Usage:
        @contract(
            name="customer_support_reply:v1",
            inputs={"query": str, "customer_id": str},
            outputs={"reply": str, "intent": str},
            memory=MemorySchema(keys={"customer_profile": {"type": "json", "version": 1}}),
            allowed_tools=["kb_retriever", "crm_get"],
            nondet_budget={"tokens": 8}
        )
        def support_reply(ctx, inputs):
            ...
    """
    spec = ContractSpec(
        name=name,
        inputs=inputs,
        outputs=outputs,
        memory=memory,
        allowed_tools=allowed_tools,
        nondet_budget=nondet_budget,
        invariants=invariants,
    )

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # The runtime will call this directly — the wrapper
            # just carries the spec on the function object.
            return fn(*args, **kwargs)

        # Attach the contract spec to the function for runtime introspection
        wrapper.__pactum_contract__ = spec
        wrapper.__pactum_original__ = fn
        return wrapper

    return decorator


def get_contract_spec(fn: Callable) -> Optional[ContractSpec]:
    """Extract the ContractSpec from a decorated function, if any."""
    return getattr(fn, "__pactum_contract__", None)


def is_contract(fn: Callable) -> bool:
    """Check if a function is decorated with @contract."""
    return hasattr(fn, "__pactum_contract__")
