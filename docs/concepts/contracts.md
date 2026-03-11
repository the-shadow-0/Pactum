# AI Contracts

> What are AI Contracts and why you need them.

## The Problem

AI components are notoriously difficult to test, debug, and reproduce. When an LLM-powered feature misbehaves:

1. **You can't reproduce the bug** — randomness, temperature, model updates all contribute.
2. **You can't unit-test AI logic** — no clear inputs/outputs boundary, no determinism.
3. **Silent failures** — a prompt template change or memory schema update can break everything with no warning.
4. **No compliance trail** — who called what LLM, with what data, and what was returned?

## What is an AI Contract?

An **AI Contract** is a declarative, versioned, enforceable interface that wraps an AI component. It defines:

| Aspect | What it specifies |
|--------|------------------|
| **Inputs** | Required fields and their types |
| **Outputs** | Expected return fields and types |
| **Memory Schema** | What memory keys the component can read/write, and their types |
| **Allowed Tools** | Which external tools/APIs the component may call |
| **Non-determinism Budget** | Maximum number of LLM tokens (controls randomness exposure) |
| **Invariants** | Custom assertions that must hold after execution |

## Example

```python
from pactum import contract, MemorySchema

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
    return {"reply": result.text, "intent": "general"}
```

## Benefits

- **Reproducibility** — Seeded execution + snapshots = deterministic replay.
- **Testability** — Input/output types are enforced, stubs can replace LLMs.
- **Safety** — Tool access and token budgets are enforced at runtime.
- **Auditability** — Every execution produces a traceable snapshot.
- **Versioning** — Contract names include versions; changes are explicit.
