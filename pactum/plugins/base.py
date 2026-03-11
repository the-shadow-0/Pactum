"""
Pactum Plugin System — abstract base class and registry for plugins.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Optional

from pactum.core.tracer import TraceEvent


class PactumPlugin(ABC):
    """
    Base class for Pactum plugins. Override hook methods to extend runtime behavior.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique plugin name."""
        ...

    def before_run(self, context: Any, inputs: dict) -> None:
        """Called before contract execution begins."""
        pass

    def after_run(self, context: Any, inputs: dict, outputs: dict, trace: list[dict]) -> None:
        """Called after contract execution completes."""
        pass

    def on_trace(self, event: TraceEvent) -> None:
        """Called for each trace event."""
        pass

    def on_snapshot_commit(self, snapshot_id: str, snapshot_data: dict) -> None:
        """Called when a snapshot is committed to the store."""
        pass


class PluginRegistry:
    """
    Registry for managing and dispatching hooks to plugins.
    """

    def __init__(self):
        self._plugins: list[PactumPlugin] = []

    def register(self, plugin: PactumPlugin) -> None:
        """Register a plugin instance."""
        self._plugins.append(plugin)

    def unregister(self, name: str) -> None:
        """Unregister a plugin by name."""
        self._plugins = [p for p in self._plugins if p.name != name]

    def get(self, name: str) -> Optional[PactumPlugin]:
        """Get a plugin by name."""
        for p in self._plugins:
            if p.name == name:
                return p
        return None

    @property
    def plugins(self) -> list[PactumPlugin]:
        return list(self._plugins)

    def dispatch_before_run(self, context: Any, inputs: dict) -> None:
        for plugin in self._plugins:
            plugin.before_run(context, inputs)

    def dispatch_after_run(self, context: Any, inputs: dict, outputs: dict, trace: list[dict]) -> None:
        for plugin in self._plugins:
            plugin.after_run(context, inputs, outputs, trace)

    def dispatch_on_trace(self, event: TraceEvent) -> None:
        for plugin in self._plugins:
            plugin.on_trace(event)

    def dispatch_on_snapshot_commit(self, snapshot_id: str, snapshot_data: dict) -> None:
        for plugin in self._plugins:
            plugin.on_snapshot_commit(snapshot_id, snapshot_data)
