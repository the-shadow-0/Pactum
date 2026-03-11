"""
Pactum CLI — command-line interface for init, run, replay, test, mock, and fuzz.
"""

from __future__ import annotations

import json
import os
import sys

import click
from rich.console import Console

from pactum.cli.helpers import (
    load_config,
    resolve_contract,
    discover_contracts,
    print_result,
    print_snapshots,
    print_fuzz_report,
    console,
)

PACTUM_BANNER = r"""
    ____             __
   / __ \____ ______/ /___  ______ ___
  / /_/ / __ `/ ___/ __/ / / / __ `__ \
 / ____/ /_/ / /__/ /_/ /_/ / / / / / /
/_/    \__,_/\___/\__/\__,_/_/ /_/ /_/

  AI Contracts — Reproducible · Testable · Deterministic
"""


@click.group()
@click.version_option(version="0.1.0", prog_name="pactum")
@click.option("--config", "-c", default=None, help="Path to pactum.yaml config file.")
@click.pass_context
def cli(ctx, config):
    """Pactum — The AI Contract Runtime CLI."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config)


@cli.command()
@click.option("--name", "-n", default="my-pactum-project", help="Project name.")
@click.option("--dir", "-d", "directory", default=".", help="Directory to initialize in.")
def init(name, directory):
    """Initialize a new Pactum project."""
    console.print(PACTUM_BANNER, style="bold cyan")

    target = os.path.abspath(directory)
    os.makedirs(target, exist_ok=True)

    # Create pactum.yaml
    config_path = os.path.join(target, "pactum.yaml")
    if not os.path.exists(config_path):
        with open(config_path, "w") as f:
            f.write(f"""version: 1
name: {name}

llm_adapters:
  - name: openai
    type: openai
    env_prefix: OPENAI_
  - name: stub
    type: stub
    default_response: "This is a stub response."

snapshot_store:
  type: local
  path: .pactum/snapshots

ci:
  test_command: "pactum test --ci"
  fail_on_violation: true

plugins: []
""")
        console.print(f"  [green]✓[/green] Created pactum.yaml")
    else:
        console.print(f"  [yellow]⊘[/yellow] pactum.yaml already exists")

    # Create .pactum directory
    pactum_dir = os.path.join(target, ".pactum")
    snapshots_dir = os.path.join(pactum_dir, "snapshots")
    os.makedirs(snapshots_dir, exist_ok=True)
    console.print(f"  [green]✓[/green] Created .pactum/snapshots/")

    # Create .gitignore for .pactum
    gitignore_path = os.path.join(pactum_dir, ".gitignore")
    if not os.path.exists(gitignore_path):
        with open(gitignore_path, "w") as f:
            f.write("# Pactum snapshots are Git-friendly but may be large\n")
            f.write("# Uncomment the next line to exclude snapshots from Git:\n")
            f.write("# snapshots/\n")

    # Create example contract
    contracts_dir = os.path.join(target, "contracts")
    os.makedirs(contracts_dir, exist_ok=True)
    example_path = os.path.join(contracts_dir, "example.py")
    if not os.path.exists(example_path):
        with open(example_path, "w") as f:
            f.write('''"""Example Pactum contract."""

from pactum import contract, MemorySchema


@contract(
    name="hello_world:v1",
    inputs={"name": str},
    outputs={"greeting": str},
)
def hello_world(ctx, inputs):
    """A simple hello world contract."""
    prompt = f"Say hello to {inputs[\'name\']} in one sentence."
    result = ctx.llm.complete(prompt, temperature=0.5, max_tokens=50)
    return {"greeting": result.text}
''')
        console.print(f"  [green]✓[/green] Created contracts/example.py")
    else:
        console.print(f"  [yellow]⊘[/yellow] contracts/example.py already exists")

    # Create tests directory with example test
    tests_dir = os.path.join(target, "tests")
    os.makedirs(tests_dir, exist_ok=True)
    test_path = os.path.join(tests_dir, "test_example.py")
    if not os.path.exists(test_path):
        with open(test_path, "w") as f:
            f.write('''"""Example contract test."""

from pactum import PactRuntime
from pactum.plugins.llm_adapter import StubAdapter
from contracts.example import hello_world


def test_hello_world():
    runtime = PactRuntime(
        llm_adapter=StubAdapter(default_response="Hello, World!"),
        seed=42,
    )
    result = runtime.run(hello_world, {"name": "Alice"})
    assert result.success
    assert "greeting" in result.outputs
''')
        console.print(f"  [green]✓[/green] Created tests/test_example.py")

    console.print(f"\n[bold green]✓ Project '{name}' initialized![/bold green]")
    console.print(f"  Next steps:")
    console.print(f"    1. Define contracts in contracts/")
    console.print(f"    2. Run: [cyan]pactum run contracts/example.py:hello_world --input-file input.json[/cyan]")
    console.print(f"    3. Test: [cyan]pactum test[/cyan]")


@cli.command()
@click.argument("contract_path")
@click.option("--input-file", "-i", required=True, help="Path to JSON input file.")
@click.option("--seed", "-s", type=int, default=None, help="Random seed for deterministic execution.")
@click.pass_context
def run(ctx, contract_path, input_file, seed):
    """Run a contract with the given inputs."""
    config = ctx.obj["config"]

    # Load inputs
    if not os.path.exists(input_file):
        console.print(f"[red]Error:[/red] Input file not found: {input_file}")
        raise SystemExit(1)

    with open(input_file, "r") as f:
        inputs = json.load(f)

    # Resolve the contract
    try:
        contract_fn = resolve_contract(contract_path)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    # Create runtime
    from pactum.core.runtime import PactRuntime
    from pactum.plugins.llm_adapter import LLMAdapter
    from pactum.snapshot.store import SnapshotStore

    snapshot_path = config.get("snapshot_store", {}).get("path", ".pactum/snapshots")
    runtime = PactRuntime(
        llm_adapter=LLMAdapter.from_env(),
        snapshot_store=SnapshotStore(snapshot_path),
        seed=seed,
        config=config,
    )

    # Run
    try:
        result = runtime.run(contract_fn, inputs, seed=seed)
        print_result(result)
    except Exception as e:
        console.print(f"[red]Execution failed:[/red] {e}")
        raise SystemExit(1)


@cli.command()
@click.option("--snapshot", "-s", required=True, help="Snapshot ID to replay.")
@click.option("--contract", "-c", default=None, help="Contract path for active replay.")
@click.pass_context
def replay(ctx, snapshot, contract):
    """Replay a contract execution from a snapshot."""
    config = ctx.obj["config"]

    from pactum.core.runtime import PactRuntime
    from pactum.plugins.llm_adapter import LLMAdapter
    from pactum.snapshot.store import SnapshotStore

    snapshot_path = config.get("snapshot_store", {}).get("path", ".pactum/snapshots")
    runtime = PactRuntime(
        llm_adapter=LLMAdapter.from_env(),
        snapshot_store=SnapshotStore(snapshot_path),
        config=config,
    )

    contract_fn = None
    if contract:
        try:
            contract_fn = resolve_contract(contract)
        except Exception as e:
            console.print(f"[red]Error:[/red] {e}")
            raise SystemExit(1)

    try:
        result = runtime.replay(snapshot, contract_fn)
        print_result(result)
    except Exception as e:
        console.print(f"[red]Replay failed:[/red] {e}")
        raise SystemExit(1)


@cli.command()
@click.option("--ci", is_flag=True, help="Run in CI mode (non-interactive, exit code reflects test results).")
@click.option("--directory", "-d", default=".", help="Directory to discover tests in.")
@click.pass_context
def test(ctx, ci, directory):
    """Run contract tests."""
    import subprocess

    config = ctx.obj["config"]

    if ci:
        console.print("[bold]Running contract tests in CI mode...[/bold]")
    else:
        console.print("[bold]Running contract tests...[/bold]")

    # Use pytest to discover and run tests
    test_dir = os.path.join(os.path.abspath(directory), "tests")
    if not os.path.exists(test_dir):
        console.print(f"[yellow]No tests/ directory found in {directory}[/yellow]")
        raise SystemExit(0)

    cmd = [sys.executable, "-m", "pytest", test_dir, "-v", "--tb=short"]
    if ci:
        cmd.append("--no-header")

    result = subprocess.run(cmd, cwd=os.path.abspath(directory))

    if ci and result.returncode != 0:
        raise SystemExit(result.returncode)


@cli.group()
def mock():
    """Mock generation commands."""
    pass


@mock.command("generate")
@click.option("--snapshot", "-s", required=True, help="Snapshot ID to generate mocks from.")
@click.option("--output", "-o", required=True, help="Output directory for mock files.")
@click.pass_context
def mock_generate(ctx, snapshot, output):
    """Generate mock data from a snapshot."""
    config = ctx.obj["config"]

    from pactum.testing.harness import MockGenerator
    from pactum.snapshot.store import SnapshotStore

    snapshot_path = config.get("snapshot_store", {}).get("path", ".pactum/snapshots")
    generator = MockGenerator(SnapshotStore(snapshot_path))

    try:
        mock_path = generator.save_mocks(snapshot, output)
        console.print(f"[green]✓[/green] Mock data saved to: {mock_path}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)


@cli.command()
@click.argument("contract_path")
@click.option("--iterations", "-n", type=int, default=100, help="Number of fuzz iterations.")
@click.option("--seed", "-s", type=int, default=None, help="Random seed for fuzzing.")
@click.pass_context
def fuzz(ctx, contract_path, iterations, seed):
    """Fuzz test a contract with random inputs."""
    config = ctx.obj["config"]

    try:
        contract_fn = resolve_contract(contract_path)
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    from pactum.testing.harness import FuzzRunner
    from pactum.plugins.llm_adapter import StubAdapter

    from pactum.core.runtime import PactRuntime
    from pactum.snapshot.store import SnapshotStore

    snapshot_path = config.get("snapshot_store", {}).get("path", ".pactum/snapshots")
    runtime = PactRuntime(
        llm_adapter=StubAdapter(),
        snapshot_store=SnapshotStore(snapshot_path),
        seed=seed,
        config=config,
    )

    runner = FuzzRunner(runtime=runtime, seed=seed)
    console.print(f"[bold]Fuzzing {contract_path} with {iterations} iterations...[/bold]")

    report = runner.fuzz(contract_fn, iterations=iterations)
    print_fuzz_report(report)

    if report.crashes:
        raise SystemExit(1)


@cli.group()
def snapshots():
    """Snapshot management commands."""
    pass


@snapshots.command("list")
@click.pass_context
def snapshots_list(ctx):
    """List all stored snapshots."""
    config = ctx.obj["config"]

    from pactum.snapshot.store import SnapshotStore

    snapshot_path = config.get("snapshot_store", {}).get("path", ".pactum/snapshots")
    store = SnapshotStore(snapshot_path)

    all_snapshots = store.list()
    print_snapshots(all_snapshots)


if __name__ == "__main__":
    cli()
