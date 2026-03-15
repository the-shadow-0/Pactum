"""
Pactum Tracer — records token-level events, tool calls, LLM completions, 
and memory reads/writes during contract execution.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class EventType(str, Enum):
    """Types of events that can be recorded in a trace."""
    CONTRACT_START = "contract_start"
    CONTRACT_END = "contract_end"
    LLM_REQUEST = "llm_request"
    LLM_RESPONSE = "llm_response"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    MEMORY_READ = "memory_read"
    MEMORY_WRITE = "memory_write"
    VALIDATION = "validation"
    USER_TRACE = "user_trace"
    ERROR = "error"


@dataclass
class TraceEvent:
    """A single event in a trace."""
    event_type: EventType
    data: dict[str, Any]
    timestamp: float
    token_count: Optional[int] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "event_type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp,
            "token_count": self.token_count,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TraceEvent:
        return cls(
            event_type=EventType(data["event_type"]),
            data=data["data"],
            timestamp=data["timestamp"],
            token_count=data.get("token_count"),
            duration_ms=data.get("duration_ms"),
        )


class Tracer:
    """
    Records token-level execution traces during contract runs.
    Captures LLM calls, tool invocations, memory access, and custom user events.
    """

    def __init__(self):
        self._events: list[TraceEvent] = []
        self._total_tokens: int = 0
        self._start_time: Optional[float] = None

    def start(self, contract_name: str, inputs: dict) -> None:
        """Mark the start of a contract execution."""
        self._start_time = time.time()
        self._record(EventType.CONTRACT_START, {
            "contract_name": contract_name,
            "inputs": _safe_serialize(inputs),
        })

    def end(self, contract_name: str, outputs: dict, success: bool = True) -> None:
        """Mark the end of a contract execution."""
        duration = (time.time() - self._start_time) * 1000 if self._start_time else None
        self._record(EventType.CONTRACT_END, {
            "contract_name": contract_name,
            "outputs": _safe_serialize(outputs),
            "success": success,
            "total_tokens": self._total_tokens,
        }, duration_ms=duration)

    def llm_request(self, prompt: str, params: dict) -> None:
        """Record an LLM request."""
        self._record(EventType.LLM_REQUEST, {
            "prompt": prompt,
            "params": _safe_serialize(params),
        })

    def llm_response(self, text: str, tokens_used: int, metadata: Optional[dict] = None) -> None:
        """Record an LLM response."""
        self._total_tokens += tokens_used
        self._record(EventType.LLM_RESPONSE, {
            "text": text,
            "metadata": _safe_serialize(metadata or {}),
        }, token_count=tokens_used)

    def tool_call(self, tool_name: str, args: dict) -> None:
        """Record a tool invocation."""
        self._record(EventType.TOOL_CALL, {
            "tool_name": tool_name,
            "args": _safe_serialize(args),
        })

    def tool_result(self, tool_name: str, result: Any) -> None:
        """Record a tool result."""
        self._record(EventType.TOOL_RESULT, {
            "tool_name": tool_name,
            "result": _safe_serialize(result),
        })

    def memory_read(self, key: str, value: Any) -> None:
        """Record a memory read."""
        self._record(EventType.MEMORY_READ, {
            "key": key,
            "value": _safe_serialize(value),
        })

    def memory_write(self, key: str, value: Any) -> None:
        """Record a memory write."""
        self._record(EventType.MEMORY_WRITE, {
            "key": key,
            "value": _safe_serialize(value),
        })

    def user_trace(self, event_name: str, data: Any) -> None:
        """Record a custom user trace event."""
        self._record(EventType.USER_TRACE, {
            "event_name": event_name,
            "data": _safe_serialize(data),
        })

    def error(self, error_type: str, message: str, details: Optional[dict] = None) -> None:
        """Record an error event."""
        self._record(EventType.ERROR, {
            "error_type": error_type,
            "message": message,
            "details": _safe_serialize(details or {}),
        })

    def _record(
        self,
        event_type: EventType,
        data: dict,
        token_count: Optional[int] = None,
        duration_ms: Optional[float] = None,
    ) -> None:
        """Internal: record a trace event."""
        self._events.append(TraceEvent(
            event_type=event_type,
            data=data,
            timestamp=time.time(),
            token_count=token_count,
            duration_ms=duration_ms,
        ))

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    def get_events(self) -> list[TraceEvent]:
        """Return all recorded events."""
        return list(self._events)

    def get_trace(self) -> list[dict]:
        """Return trace as a list of dicts (serializable)."""
        return [e.to_dict() for e in self._events]

    def to_dict(self) -> dict:
        """Serialize the entire tracer state."""
        return {
            "events": self.get_trace(),
            "total_tokens": self._total_tokens,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Tracer:
        """Reconstruct a Tracer from serialized data."""
        tracer = cls()
        tracer._events = [TraceEvent.from_dict(e) for e in data.get("events", [])]
        tracer._total_tokens = data.get("total_tokens", 0)
        return tracer

    def clear(self) -> None:
        """Clear all recorded events."""
        self._events.clear()
        self._total_tokens = 0
        self._start_time = None


def _safe_serialize(obj: Any) -> Any:
    """Convert an object to a JSON-safe representation."""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {str(k): _safe_serialize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(v) for v in obj]
    try:
        return str(obj)
    except Exception:
        return f"<unserializable: {type(obj).__name__}>"
