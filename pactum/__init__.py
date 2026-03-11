"""
Pactum — AI Contracts: first-class, versioned, testable interfaces
and deterministic runtimes for AI components.
"""

__version__ = "0.1.0"

from pactum.core.contract import contract, ContractSpec, MemorySchema
from pactum.core.runtime import PactRuntime
from pactum.core.context import ExecutionContext
from pactum.plugins.llm_adapter import LLMAdapter, LLMResult, StubAdapter, OpenAIAdapter

__all__ = [
    "contract",
    "ContractSpec",
    "MemorySchema",
    "PactRuntime",
    "ExecutionContext",
    "LLMAdapter",
    "LLMResult",
    "StubAdapter",
    "OpenAIAdapter",
]
