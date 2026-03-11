# CLI Reference

> Complete command reference for the `pactum` CLI.

## Global Options

```
pactum [OPTIONS] COMMAND [ARGS]...

Options:
  --version        Show the version and exit.
  -c, --config     Path to pactum.yaml config file.
  --help           Show this message and exit.
```

---

## Commands

### `pactum init`

Initialize a new Pactum project.

```bash
pactum init [--name NAME] [--dir DIRECTORY]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--name, -n` | `my-pactum-project` | Project name |
| `--dir, -d` | `.` | Directory to initialize in |

Creates:
- `pactum.yaml` — configuration file
- `.pactum/snapshots/` — snapshot storage directory
- `contracts/example.py` — example contract
- `tests/test_example.py` — example test

---

### `pactum run`

Run a contract with given inputs.

```bash
pactum run CONTRACT_PATH --input-file PATH [--seed INT]
```

| Argument/Option | Required | Description |
|----------------|----------|-------------|
| `CONTRACT_PATH` | Yes | Module path (e.g., `contracts/example.py:hello_world`) |
| `--input-file, -i` | Yes | Path to JSON input file |
| `--seed, -s` | No | Random seed for deterministic execution |

---

### `pactum replay`

Replay a contract execution from a snapshot.

```bash
pactum replay --snapshot ID [--contract PATH]
```

| Option | Required | Description |
|--------|----------|-------------|
| `--snapshot, -s` | Yes | Snapshot ID (full or prefix) |
| `--contract, -c` | No | Contract path for active replay |

---

### `pactum test`

Run contract tests using pytest.

```bash
pactum test [--ci] [--directory DIR]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--ci` | `false` | CI mode (non-interactive, exit code reflects results) |
| `--directory, -d` | `.` | Directory to discover tests in |

---

### `pactum fuzz`

Fuzz test a contract with random inputs.

```bash
pactum fuzz CONTRACT_PATH [--iterations N] [--seed INT]
```

| Argument/Option | Default | Description |
|----------------|---------|-------------|
| `CONTRACT_PATH` | — | Contract module path |
| `--iterations, -n` | `100` | Number of fuzz iterations |
| `--seed, -s` | random | Random seed for reproducibility |

---

### `pactum mock generate`

Generate mock data from a snapshot.

```bash
pactum mock generate --snapshot ID --output DIR
```

---

### `pactum snapshots list`

List all stored snapshots.

```bash
pactum snapshots list
```
