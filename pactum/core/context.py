""" 
Pactum ExecutionContext — the context object passed to contract functions.
Provides access to LLM, tools, memory, tracing, and seeded randomness.
"""

from __future__ import annotations

import random
from typing import Any, Optional

from pactum.core.contract import ContractSpec
from pactum.core.tracer import Tracer
from pactum.core.validator import validate_nondet_budget
from pactum.plugins.llm_adapter import LLMAdapter, LLMResult
from pactum.plugins.tool_adapter import ToolNamespace
from pactum.plugins.memory_backend import TracedMemory


class TracedLLM:
    """
    Wraps an LLM adapter with tracing and non-determinism budget enforcement.
    """

    def __init__(
        self,
        adapter: LLMAdapter,
        tracer: Tracer,
        spec: Optional[ContractSpec] = None,
    ):
        self._adapter = adapter
        self._tracer = tracer
        self._spec = spec
        self._total_tokens = 0

    def complete(self, prompt: str, **kwargs) -> LLMResult:
        """Send a completion request, trace it, and enforce budget."""
        self._tracer.llm_request(prompt, kwargs)

        result = self._adapter.complete(prompt, **kwargs)

        self._total_tokens += result.tokens_used
        self._tracer.llm_response(result.text, result.tokens_used, result.metadata)

        # Enforce non-determinism budget
        if self._spec:
            validate_nondet_budget(self._spec, self._total_tokens)

        return result

    @property
    def total_tokens(self) -> int:
        return self._total_tokens


class ExecutionContext:
    """
    The context object passed to contract functions.

    Provides:
        - ctx.llm — TracedLLM proxy for LLM completions
        - ctx.tools — ToolNamespace for calling registered tools
        - ctx.memory — TracedMemory for reading/writing memory
        - ctx.trace(event, data) — manual trace points
        - ctx.random — seeded Random instance
        - ctx.run_id — unique run identifier
    """

    def __init__(
        self,
        llm: TracedLLM,
        tools: ToolNamespace,
        memory: TracedMemory,
        tracer: Tracer,
        rng: random.Random,
        run_id: str,
        spec: Optional[ContractSpec] = None,
    ):
        self.llm = llm
        self.tools = tools
        self.memory = memory
        self._tracer = tracer
        self.random = rng
        self.run_id = run_id
        self._spec = spec

    def trace(self, event_name: str, data: Any = None) -> None:
        """Record a custom user trace event."""
        self._tracer.user_trace(event_name, data)

    @property
    def contract_name(self) -> Optional[str]:
        return self._spec.name if self._spec else None

    @property
    def contract_spec(self) -> Optional[ContractSpec]:
        return self._spec
