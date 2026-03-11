# Python SDK API Reference

> Complete API reference for the `pactum` Python package.

## Core — `pactum`

### `@contract(...)`

Decorator to define an AI Contract on a function.

```python
from pactum import contract, MemorySchema

@contract(
    name="my_contract:v1",     # Contract name with version
    inputs={"query": str},      # Input schema
    outputs={"answer": str},    # Output schema
    memory=MemorySchema(...),   # Optional memory schema
    allowed_tools=["search"],   # Optional tool whitelist
    nondet_budget={"tokens": 8},# Optional token budget
    invariants=[check_fn],      # Optional assertion functions
)
def my_contract(ctx, inputs):
    ...
```

### `ContractSpec`

Dataclass holding the full contract specification. Attached to decorated functions via `__pactum_contract__`.

**Properties:**
- `name: str` — Full contract name (e.g., `"support:v1"`)
- `base_name: str` — Name without version
- `contract_version: str` — Version string
- `inputs: dict` — Input schema
- `outputs: dict` — Output schema
- `memory: MemorySchema | None`
- `allowed_tools: list[str] | None`
- `nondet_budget: dict | None`
- `invariants: list[Callable] | None`

**Methods:**
- `to_dict() -> dict` — Serialize for snapshots
- `from_dict(data) -> ContractSpec` — Deserialize

### `MemorySchema`

```python
schema = MemorySchema(keys={
    "profile": {"type": "json", "version": 1},
    "settings": {"type": "string"},
})
```

### `PactRuntime`

Central execution engine.

```python
runtime = PactRuntime(
    llm_adapter=LLMAdapter.from_env(),
    snapshot_store=SnapshotStore(".pactum/snapshots"),
    tool_registry=ToolRegistry(),
    plugin_registry=PluginRegistry(),
    seed=42,
)
```

**Methods:**
- `run(contract_fn, inputs, memory_state=None, seed=None) -> ExecutionResult`
- `replay(snapshot_id, contract_fn=None) -> ExecutionResult`

**Properties:**
- `runs: list[ExecutionResult]`
- `last_run: ExecutionResult | None`

### `ExecutionResult`

```python
result.run_id          # str — unique run ID
result.snapshot_id     # str — content-addressed snapshot ID
result.outputs         # dict — contract outputs
result.trace           # list[dict] — execution trace
result.success         # bool
result.error           # str | None
result.total_tokens    # int
```

---

## Plugins — `pactum.plugins`

### `LLMAdapter`

Abstract base class for LLM adapters.

```python
from pactum.plugins.llm_adapter import LLMAdapter, StubAdapter, OpenAIAdapter

# Factory
adapter = LLMAdapter.from_env()        # Auto-detect
adapter = LLMAdapter.from_env("stub")  # Force stub

# Stub (for testing)
stub = StubAdapter(
    default_response="Hello!",
    default_tokens=5,
    responses={"weather": "It's sunny!"},  # Pattern matching
)

# OpenAI
openai = OpenAIAdapter(model="gpt-4o-mini")
```

### `ToolRegistry`

```python
from pactum.plugins.tool_adapter import ToolRegistry

registry = ToolRegistry()
registry.register("search", lambda q: f"Results for {q}")
```

### `PactumPlugin`

```python
from pactum.plugins.base import PactumPlugin

class MyPlugin(PactumPlugin):
    @property
    def name(self): return "my-plugin"

    def before_run(self, ctx, inputs): ...
    def after_run(self, ctx, inputs, outputs, trace): ...
    def on_trace(self, event): ...
    def on_snapshot_commit(self, snapshot_id, data): ...
```

---

## Testing — `pactum.testing`

### `FuzzRunner`

```python
from pactum.testing.harness import FuzzRunner

runner = FuzzRunner(runtime=runtime, seed=42)
report = runner.fuzz(my_contract, iterations=1000)
print(report.summary())
```

### `MockGenerator`

```python
from pactum.testing.harness import MockGenerator

gen = MockGenerator(snapshot_store)
mocks = gen.from_snapshot("9f2c3a")
gen.save_mocks("9f2c3a", "tests/mocks/")
```
