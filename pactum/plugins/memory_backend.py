"""
Pactum Memory Backends — in-memory and extensible storage for contract memory.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pactum.core.tracer import Tracer


class MemoryBackend(ABC):
    """Abstract base class for memory storage backends."""

    @abstractmethod
    def get(self, key: str) -> Any:
        """Retrieve a value by key. Returns None if not found."""
        ...

    @abstractmethod
    def set(self, key: str, value: Any) -> None:
        """Store a value by key."""
        ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Delete a key."""
        ...

    @abstractmethod
    def list_keys(self) -> list[str]:
        """List all stored keys."""
        ...

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        """Get the full memory state as a dict."""
        ...

    @abstractmethod
    def clear(self) -> None:
        """Clear all stored data."""
        ...


class InMemoryBackend(MemoryBackend):
    """
    Simple dict-based in-memory backend. Default for all contracts.
    """

    def __init__(self, initial_state: Optional[dict[str, Any]] = None):
        self._store: dict[str, Any] = dict(initial_state or {})

    def get(self, key: str) -> Any:
        return self._store.get(key)

    def set(self, key: str, value: Any) -> None:
        self._store[key] = value

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def list_keys(self) -> list[str]:
        return list(self._store.keys())

    def get_state(self) -> dict[str, Any]:
        return dict(self._store)

    def clear(self) -> None:
        self._store.clear()


class TracedMemory:
    """
    Wrapper around a MemoryBackend that traces all reads and writes.
    Used by the ExecutionContext.
    """

    def __init__(self, backend: MemoryBackend, tracer: Optional[Tracer] = None):
        self._backend = backend
        self._tracer = tracer

    def get(self, key: str) -> Any:
        value = self._backend.get(key)
        if self._tracer:
            self._tracer.memory_read(key, value)
        return value

    def set(self, key: str, value: Any) -> None:
        if self._tracer:
            self._tracer.memory_write(key, value)
        self._backend.set(key, value)

    def delete(self, key: str) -> None:
        self._backend.delete(key)

    def list_keys(self) -> list[str]:
        return self._backend.list_keys()

    def get_state(self) -> dict[str, Any]:
        return self._backend.get_state()

    def clear(self) -> None:
        self._backend.clear()
