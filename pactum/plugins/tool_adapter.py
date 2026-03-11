"""
Pactum Tool Adapter — registry for named tool callables with tracing and access control.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from pactum.core.tracer import Tracer
from pactum.core.exceptions import ToolAccessDeniedError


class ToolProxy:
    """
    Wraps a tool callable with tracing and access control.
    When called, records the invocation and result in the tracer.
    """

    def __init__(
        self,
        name: str,
        fn: Callable,
        tracer: Optional[Tracer] = None,
        contract_name: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
    ):
        self.name = name
        self._fn = fn
        self._tracer = tracer
        self._contract_name = contract_name
        self._allowed_tools = allowed_tools

    def __call__(self, *args, **kwargs) -> Any:
        # Enforce access control
        if self._allowed_tools is not None and self.name not in self._allowed_tools:
            raise ToolAccessDeniedError(
                self._contract_name or "<unknown>",
                self.name,
                self._allowed_tools,
            )

        # Trace the call
        if self._tracer:
            self._tracer.tool_call(self.name, {
                "args": list(args),
                "kwargs": kwargs,
            })

        # Execute
        result = self._fn(*args, **kwargs)

        # Trace the result
        if self._tracer:
            self._tracer.tool_result(self.name, result)

        return result


class ToolRegistry:
    """
    Registry for named tool callables.
    Tools are wrapped with ToolProxy for tracing and access control.
    """

    def __init__(self):
        self._tools: dict[str, Callable] = {}

    def register(self, name: str, fn: Callable) -> None:
        """Register a tool by name."""
        self._tools[name] = fn

    def unregister(self, name: str) -> None:
        """Remove a tool."""
        self._tools.pop(name, None)

    def get(self, name: str) -> Optional[Callable]:
        """Get a raw tool callable by name."""
        return self._tools.get(name)

    def get_proxy(
        self,
        name: str,
        tracer: Optional[Tracer] = None,
        contract_name: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
    ) -> ToolProxy:
        """
        Get a traced, access-controlled proxy for a tool.
        Raises KeyError if tool is not registered.
        """
        fn = self._tools.get(name)
        if fn is None:
            raise KeyError(f"Tool '{name}' is not registered")
        return ToolProxy(name, fn, tracer, contract_name, allowed_tools)

    def list_tools(self) -> list[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def create_proxy_namespace(
        self,
        tracer: Optional[Tracer] = None,
        contract_name: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
    ) -> ToolNamespace:
        """Create a namespace with all tools wrapped as proxies."""
        return ToolNamespace(self, tracer, contract_name, allowed_tools)


class ToolNamespace:
    """
    Attribute-based access to tool proxies.
    Allows `ctx.tools.tool_name(args)` syntax.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        tracer: Optional[Tracer] = None,
        contract_name: Optional[str] = None,
        allowed_tools: Optional[list[str]] = None,
    ):
        self._registry = registry
        self._tracer = tracer
        self._contract_name = contract_name
        self._allowed_tools = allowed_tools

    def __getattr__(self, name: str) -> ToolProxy:
        if name.startswith("_"):
            raise AttributeError(name)
        try:
            return self._registry.get_proxy(
                name, self._tracer, self._contract_name, self._allowed_tools
            )
        except KeyError:
            raise AttributeError(f"Tool '{name}' is not registered")

    def __contains__(self, name: str) -> bool:
        return name in self._registry.list_tools()
