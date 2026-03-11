# Snapshots

> Content-addressed, Git-friendly storage for execution traces.

## Overview

Every contract execution produces a **snapshot** — a complete record of the execution state stored in a content-addressed format (SHA-256 hashed).

## Snapshot Contents

```json
{
  "snapshot_id": "9f2c3a4b1e7d8f90",
  "run_id": "a1b2c3d4",
  "timestamp": "2024-01-15T10:30:00Z",
  "pactum_version": "0.1.0",
  "contract": {
    "name": "customer_support_reply:v1",
    "inputs": {"query": "str", "customer_id": "str"},
    "outputs": {"reply": "str", "intent": "str"}
  },
  "inputs": {"query": "Where's my order?", "customer_id": "C-12345"},
  "outputs": {"reply": "Your order is on its way!", "intent": "order_status"},
  "trace": [...],
  "seed": 42,
  "memory_state": {},
  "success": true,
  "config": {}
}
```

## Storage Layout

Snapshots are stored at `.pactum/snapshots/{id[:2]}/{id[2:]}.json`:

```
.pactum/snapshots/
  9f/
    2c3a4b1e7d8f90.json
  a1/
    b3c5d7e9f01234.json
```

## Operations

```bash
# List all snapshots
pactum snapshots list

# Replay from a snapshot (passive — displays stored data)
pactum replay --snapshot 9f2c3a

# Replay with re-execution (active — runs the contract again)
pactum replay --snapshot 9f2c3a --contract contracts/support.py:support_reply

# Generate mocks from a snapshot
pactum mock generate --snapshot 9f2c3a --output tests/mocks/

# Diff two snapshots
# (programmatic via Python API)
store.diff("9f2c3a4b1e7d8f90", "a1b3c5d7e9f01234")
```

## Git Integration

Snapshots are JSON files — fully Git-friendly:

- Review snapshot changes in PRs
- Track when contract behavior drifted
- Audit execution history
