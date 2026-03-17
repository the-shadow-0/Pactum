 <p align="center">
  <h1 align="center">🔏 Pactum</h1>
  <p align="center"><strong>The AI Contract Runtime</strong></p>
  <p align="center">
    <em>First-class, versioned, testable interfaces and deterministic runtimes for AI components.</em>
  </p>
</p>

<p align="center">
  <a href="#-quickstart">Quickstart</a> •
  <a href="#-features">Features</a> •
  <a href="#-examples">Examples</a> •
  <a href="docs/">Documentation</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-0.1.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/python-3.10+-green" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-brightgreen" alt="License">
  <img src="https://img.shields.io/badge/status-alpha-orange" alt="Status">
</p>

---

## 🤔 The Problem

AI bugs are **non-reproducible**. LLM-powered features are a nightmare to test, debug, and audit:

- 🐛 **Non-reproducible bugs** — randomness, model updates, temperature all conspire against you
- 🧪 **Can't unit-test AI logic** — no clear input/output boundaries, no determinism
- 💥 **Silent failures** — prompt template or memory schema changes break things without warning
- 📋 **No compliance trail** — who called what LLM, with what data, when?
- 🐌 **Slow feedback loops** — no way to quickly iterate on AI behavior changes

## 💡 The Solution

**Pactum** introduces **AI Contracts** — declarative, versioned, enforceable interfaces for AI components:

```python
from pactum import contract, PactRuntime, MemorySchema

@contract(
    name="customer_support_reply:v1",
    inputs={"query": str, "customer_id": str},
    outputs={"reply": str, "intent": str},
    memory=MemorySchema(keys={"customer_profile": {"type": "json", "version": 1}}),
    allowed_tools=["kb_retriever", "crm_get"],
    nondet_budget={"tokens": 8}
)
def support_reply(ctx, inputs):
    snippets = ctx.tools.kb_retriever(inputs["query"], top_k=3)
    prompt = f"Query: {inputs['query']}\nContext: {snippets}\nAnswer concisely."
    result = ctx.llm.complete(prompt, temperature=0.7, max_tokens=256)
    return {"reply": result.text, "intent": result.classification}

# Run with full tracing and snapshotting
runtime = PactRuntime(seed=42)
result = runtime.run(support_reply, {"query": "Where's my order?", "customer_id": "C-12345"})
print(f"Snapshot: {result.snapshot_id}")  # Replay this anytime!
```

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔏 **AI Contracts** | Declarative input/output schemas, memory schemas, tool access controls |
| 🎯 **Deterministic Runtime** | Seeded PRNG, token-level tracing, reproducible execution |
| 📸 **Snapshot Store** | Content-addressed (SHA-256), Git-friendly execution snapshots |
| 🔄 **Replay Engine** | Deterministic replay from any snapshot — reproduce any bug |
| 🧪 **Test Harness** | Mock generation, regression testing from snapshots |
| 🌀 **Fuzzing** | Auto-generate random inputs to find contract violations |
| 🔌 **Plugin System** | Hooks for LLMs, tools, memory, validators (`before_run`, `after_run`, etc.) |
| 🖥️ **CLI** | `init`, `run`, `replay`, `test`, `mock`, `fuzz` — everything from the terminal |

---

## 🚀 Quickstart

### Installation

```bash
pip install -e ".[dev]"
```

### Initialize a Project

```bash
pactum init --name my-ai-project
```

This creates:
- `pactum.yaml` — configuration
- `.pactum/snapshots/` — snapshot storage
- `contracts/example.py` — starter contract
- `tests/test_example.py` — starter test

### Run a Contract

```bash
pactum run contracts/example.py:hello_world --input-file input.json --seed 42
```

### Replay from Snapshot

```bash
pactum replay --snapshot 9f2c3a
```

### Run Tests

```bash
pactum test --ci
```

### Fuzz Testing

```bash
pactum fuzz contracts/example.py:hello_world --iterations 1000 --seed 42
```

---

## 🏗️ Architecture

```
┌──────────────────┐
│   AI Component   │
│  (@contract)     │
└────────┬─────────┘
         │
┌────────▼─────────┐
│  Pactum Runtime   │ ← Seeded PRNG, Tool Access, Tracer
│                   │
│  ┌─────────────┐  │
│  │  Validator   │  │ ← Input/Output, Memory, Tools, Budget
│  └─────────────┘  │
│  ┌─────────────┐  │
│  │   Tracer     │  │ ← Token-level event recording
│  └─────────────┘  │
└────────┬─────────┘
         │
┌────────▼─────────┐
│  Snapshot Store   │ ← Content-addressed (SHA-256)
│  (.pactum/)       │
└────────┬─────────┘
         │
┌────────▼─────────────────────────────┐
│  Replay Engine / Test Harness        │
│  Mocks · Fuzzing · CI Integration    │
└──────────────────────────────────────┘
         │
┌────────▼─────────────────────────────┐
│  Plugins                              │
│  LLM · Memory · Tool · Validator     │
└──────────────────────────────────────┘
```

---

## 📂 Project Structure

```
pactum/
├── core/           # Runtime, tracer, contract DSL, validator
├── cli/            # Command-line interface
├── plugins/        # LLM adapters, tools, memory, plugin base
├── snapshot/       # Content-addressed snapshot store
├── testing/        # Test harness, mock generator, fuzzer
examples/
├── support-bot/    # Customer support contract example
├── rag-app/        # RAG retrieval example
docs/
├── concepts/       # What are contracts, runtime, snapshots
├── cli/            # CLI reference
├── api/            # Python SDK reference
tests/              # Full test suite
```

---

## 📝 Examples

### Support Bot

```python
from pactum import contract, PactRuntime, MemorySchema
from pactum.plugins.llm_adapter import StubAdapter
from pactum.plugins.tool_adapter import ToolRegistry

@contract(
    name="support:v1",
    inputs={"query": str, "customer_id": str},
    outputs={"reply": str, "intent": str},
    allowed_tools=["kb_retriever"],
    nondet_budget={"tokens": 256},
)
def support_reply(ctx, inputs):
    docs = ctx.tools.kb_retriever(inputs["query"])
    result = ctx.llm.complete(f"Answer: {inputs['query']}\nContext: {docs}")
    return {"reply": result.text, "intent": "general"}

# Test with stub adapter — no API key needed!
tools = ToolRegistry()
tools.register("kb_retriever", lambda q, **kw: ["FAQ: Check tracking page."])

runtime = PactRuntime(
    llm_adapter=StubAdapter(default_response="Your order is on its way!"),
    tool_registry=tools,
    seed=42,
)
result = runtime.run(support_reply, {"query": "Where's my order?", "customer_id": "C-123"})
print(result.outputs)   # {"reply": "Your order is on its way!", "intent": "general"}
print(result.snapshot_id)  # Replay this anytime!
```

---

## 🔌 Plugin System

```python
from pactum.plugins.base import PactumPlugin

class MetricsPlugin(PactumPlugin):
    @property
    def name(self):
        return "metrics"

    def after_run(self, ctx, inputs, outputs, trace):
        tokens = sum(e.get("token_count", 0) or 0 for e in trace)
        print(f"Total tokens used: {tokens}")
```

**Plugin Hooks:**
- `before_run(context, inputs)` — Before contract execution
- `after_run(context, inputs, outputs, trace)` — After execution
- `on_trace(event)` — On each trace event
- `on_snapshot_commit(snapshot_id, data)` — When snapshot is stored

---


## 🤝 Contributing

Contributions are welcome! See our [docs](docs/) for architecture details.

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=pactum --cov-report=term-missing
```

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>Pactum</strong> — Build AI components that are <em>observable, reproducible, testable, and safe</em>.
</p>
