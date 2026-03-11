"""
Pactum LLM Adapters — abstract interface and concrete adapters for LLMs.
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LLMResult:
    """Result from an LLM completion."""
    text: str
    tokens_used: int
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "tokens_used": self.tokens_used,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> LLMResult:
        return cls(
            text=data["text"],
            tokens_used=data["tokens_used"],
            metadata=data.get("metadata", {}),
        )


class LLMAdapter(ABC):
    """
    Abstract base class for LLM adapters.
    All LLM interactions go through this interface for tracing and control.
    """

    @abstractmethod
    def complete(self, prompt: str, **kwargs) -> LLMResult:
        """
        Send a completion request to the LLM.

        Args:
            prompt: The prompt to send.
            **kwargs: Additional parameters (temperature, max_tokens, etc.)

        Returns:
            LLMResult with text, token count, and metadata.
        """
        ...

    @classmethod
    def from_env(cls, adapter_type: Optional[str] = None) -> LLMAdapter:
        """
        Factory method: create an LLM adapter from environment variables.

        If OPENAI_API_KEY is set, returns OpenAIAdapter.
        Otherwise, returns StubAdapter.
        """
        if adapter_type == "stub":
            return StubAdapter()

        if adapter_type == "openai" or os.environ.get("OPENAI_API_KEY"):
            return OpenAIAdapter()

        return StubAdapter()


class StubAdapter(LLMAdapter):
    """
    Deterministic stub adapter for testing.
    Returns configurable fixed responses — no external API calls.
    """

    def __init__(
        self,
        default_response: str = "This is a stub response.",
        default_tokens: int = 5,
        responses: Optional[dict[str, str]] = None,
    ):
        self.default_response = default_response
        self.default_tokens = default_tokens
        self._responses = responses or {}
        self._call_count = 0
        self._calls: list[dict] = []

    def complete(self, prompt: str, **kwargs) -> LLMResult:
        self._call_count += 1
        self._calls.append({"prompt": prompt, "kwargs": kwargs})

        # Check for prompt-specific responses
        for key, response in self._responses.items():
            if key in prompt:
                return LLMResult(
                    text=response,
                    tokens_used=len(response.split()),
                    metadata={"adapter": "stub", "call_number": self._call_count},
                )

        max_tokens = kwargs.get("max_tokens", self.default_tokens)
        return LLMResult(
            text=self.default_response,
            tokens_used=min(self.default_tokens, max_tokens),
            metadata={"adapter": "stub", "call_number": self._call_count},
        )

    @property
    def call_count(self) -> int:
        return self._call_count

    @property
    def calls(self) -> list[dict]:
        return list(self._calls)

    def reset(self) -> None:
        self._call_count = 0
        self._calls.clear()


class OpenAIAdapter(LLMAdapter):
    """
    OpenAI LLM adapter — wraps the openai Python SDK.
    Requires OPENAI_API_KEY environment variable.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        api_key: Optional[str] = None,
    ):
        self.model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")

    def _get_client(self):
        """Lazy-load the OpenAI client."""
        try:
            import openai
            return openai.OpenAI(api_key=self._api_key)
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAIAdapter. "
                "Install it with: pip install openai"
            )

    def complete(self, prompt: str, **kwargs) -> LLMResult:
        client = self._get_client()

        temperature = kwargs.get("temperature", 0.7)
        max_tokens = kwargs.get("max_tokens", 256)

        response = client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=temperature,
            max_tokens=max_tokens,
        )

        choice = response.choices[0]
        text = choice.message.content or ""
        usage = response.usage

        tokens_used = usage.completion_tokens if usage else len(text.split())

        return LLMResult(
            text=text,
            tokens_used=tokens_used,
            metadata={
                "adapter": "openai",
                "model": self.model,
                "finish_reason": choice.finish_reason,
                "prompt_tokens": usage.prompt_tokens if usage else None,
                "total_tokens": usage.total_tokens if usage else None,
            },
        )
