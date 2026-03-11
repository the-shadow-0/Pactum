# Pactum Runtime

> How the deterministic runtime works.

## Overview

The `PactRuntime` is the central execution engine. When you call `runtime.run(contract_fn, inputs)`, it:

1. **Validates inputs** against the contract schema
2. **Creates an ExecutionContext** with traced LLM, tools, memory, and seeded RNG
3. **Dispatches `before_run` plugin hooks**
4. **Executes the contract function** with full tracing
5. **Validates outputs** against the contract schema
6. **Checks memory schema** conformance
7. **Runs invariants** (custom assertions)
8. **Creates and stores a snapshot** (content-addressed)
9. **Dispatches `after_run` plugin hooks**

## Determinism

Pactum achieves deterministic execution through:

- **Seeded PRNG**: Every run gets a `random.Random` instance seeded with a known seed.
- **Snapshot Store**: Full execution state (inputs, outputs, trace, seed) is captured.
- **Replay**: Given a snapshot ID, the runtime can re-execute with the same seed and inputs.

```python
runtime = PactRuntime(llm_adapter=stub, seed=42)
result1 = runtime.run(my_contract, inputs, seed=42)
result2 = runtime.run(my_contract, inputs, seed=42)
assert result1.outputs == result2.outputs  # Always true with stub adapter
```

## Token-Level Tracing

The `Tracer` records every significant event:

| Event Type | When |
|-----------|------|
| `contract_start` | Execution begins |
| `contract_end` | Execution completes |
| `llm_request` | LLM prompt sent |
| `llm_response` | LLM response received |
| `tool_call` | Tool invoked |
| `tool_result` | Tool response received |
| `memory_read` | Memory key read |
| `memory_write` | Memory key written |
| `user_trace` | Custom trace via `ctx.trace()` |
| `error` | Error occurred |

## ExecutionContext

The context object (`ctx`) passed to contract functions provides:

```python
def my_contract(ctx, inputs):
    ctx.llm.complete(prompt)       # Traced LLM calls
    ctx.tools.my_tool(args)        # Traced tool calls
    ctx.memory.get("key")          # Traced memory access
    ctx.trace("event", data)       # Custom trace points
    ctx.random.randint(0, 100)     # Seeded randomness
```
