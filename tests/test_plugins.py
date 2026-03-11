"""
Tests for plugins — LLM adapters, tool registry, memory backend, and plugin hooks.
"""

import pytest

from pactum.plugins.llm_adapter import StubAdapter, LLMResult, LLMAdapter
from pactum.plugins.tool_adapter import ToolRegistry, ToolProxy, ToolNamespace
from pactum.plugins.memory_backend import InMemoryBackend, TracedMemory
from pactum.plugins.base import PactumPlugin, PluginRegistry
from pactum.core.tracer import Tracer
from pactum.core.exceptions import ToolAccessDeniedError


class TestStubAdapter:
    def test_default_response(self):
        adapter = StubAdapter(default_response="Hello!")
        result = adapter.complete("What's up?")
        assert result.text == "Hello!"
        assert result.tokens_used > 0

    def test_custom_responses(self):
        adapter = StubAdapter(responses={"weather": "It's sunny!", "stock": "AAPL is up."})
        r1 = adapter.complete("What's the weather?")
        assert r1.text == "It's sunny!"
        r2 = adapter.complete("How's the stock market?")
        assert r2.text == "AAPL is up."

    def test_call_tracking(self):
        adapter = StubAdapter()
        adapter.complete("prompt 1")
        adapter.complete("prompt 2")
        assert adapter.call_count == 2
        assert len(adapter.calls) == 2
        assert adapter.calls[0]["prompt"] == "prompt 1"

    def test_reset(self):
        adapter = StubAdapter()
        adapter.complete("test")
        adapter.reset()
        assert adapter.call_count == 0

    def test_from_env_stub(self):
        adapter = LLMAdapter.from_env("stub")
        assert isinstance(adapter, StubAdapter)


class TestToolRegistry:
    def test_register_and_call(self):
        registry = ToolRegistry()
        registry.register("add", lambda a, b: a + b)

        fn = registry.get("add")
        assert fn(2, 3) == 5

    def test_proxy_with_tracing(self):
        registry = ToolRegistry()
        registry.register("search", lambda q: f"Results for {q}")
        tracer = Tracer()

        proxy = registry.get_proxy("search", tracer=tracer)
        result = proxy("test query")

        assert result == "Results for test query"
        events = tracer.get_events()
        assert any(e.event_type.value == "tool_call" for e in events)
        assert any(e.event_type.value == "tool_result" for e in events)

    def test_proxy_access_control(self):
        registry = ToolRegistry()
        registry.register("forbidden", lambda: "secret")

        proxy = registry.get_proxy(
            "forbidden",
            contract_name="test:v1",
            allowed_tools=["search"],
        )
        with pytest.raises(ToolAccessDeniedError):
            proxy()

    def test_namespace(self):
        registry = ToolRegistry()
        registry.register("calc", lambda x: x * 2)

        ns = registry.create_proxy_namespace()
        result = ns.calc(5)
        assert result == 10

    def test_namespace_missing_tool(self):
        registry = ToolRegistry()
        ns = registry.create_proxy_namespace()
        with pytest.raises(AttributeError, match="not registered"):
            ns.nonexistent()

    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register("a", lambda: None)
        registry.register("b", lambda: None)
        assert set(registry.list_tools()) == {"a", "b"}


class TestMemoryBackend:
    def test_in_memory_basic(self):
        backend = InMemoryBackend()
        backend.set("key1", "value1")
        assert backend.get("key1") == "value1"
        assert backend.list_keys() == ["key1"]

    def test_initial_state(self):
        backend = InMemoryBackend({"k": "v"})
        assert backend.get("k") == "v"

    def test_delete(self):
        backend = InMemoryBackend({"k": "v"})
        backend.delete("k")
        assert backend.get("k") is None

    def test_clear(self):
        backend = InMemoryBackend({"a": 1, "b": 2})
        backend.clear()
        assert backend.list_keys() == []

    def test_traced_memory(self):
        backend = InMemoryBackend()
        tracer = Tracer()
        traced = TracedMemory(backend, tracer)

        traced.set("key", "value")
        result = traced.get("key")

        assert result == "value"
        events = tracer.get_events()
        assert any(e.event_type.value == "memory_write" for e in events)
        assert any(e.event_type.value == "memory_read" for e in events)


class TestPluginRegistry:
    def test_register_and_dispatch(self):
        calls = []

        class MyPlugin(PactumPlugin):
            @property
            def name(self):
                return "my-plugin"

            def before_run(self, context, inputs):
                calls.append("before")

            def after_run(self, context, inputs, outputs, trace):
                calls.append("after")

        registry = PluginRegistry()
        registry.register(MyPlugin())

        registry.dispatch_before_run(None, {})
        registry.dispatch_after_run(None, {}, {}, [])

        assert calls == ["before", "after"]

    def test_unregister(self):
        class P(PactumPlugin):
            @property
            def name(self):
                return "test"

        registry = PluginRegistry()
        registry.register(P())
        assert len(registry.plugins) == 1

        registry.unregister("test")
        assert len(registry.plugins) == 0

    def test_get_plugin(self):
        class P(PactumPlugin):
            @property
            def name(self):
                return "finder"

        registry = PluginRegistry()
        p = P()
        registry.register(p)
        assert registry.get("finder") is p
        assert registry.get("nonexistent") is None
