"""
Pactum CLI Helpers — config loading, contract discovery, and output formatting.
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Optional

import yaml
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from pactum.core.contract import get_contract_spec, is_contract
from pactum.core.exceptions import ConfigError

console = Console()


def load_config(path: Optional[str] = None) -> dict:
    """
    Load pactum.yaml configuration.

    Searches in order: provided path, ./pactum.yaml, ~/.pactum/config.yaml
    """
    search_paths = []
    if path:
        search_paths.append(path)
    search_paths.extend([
        os.path.join(os.getcwd(), "pactum.yaml"),
        os.path.join(os.path.expanduser("~"), ".pactum", "config.yaml"),
    ])

    for p in search_paths:
        if os.path.exists(p):
            with open(p, "r") as f:
                config = yaml.safe_load(f) or {}
            return config

    # Return default config if no file found
    return {
        "version": 1,
        "name": "pactum-config",
        "snapshot_store": {"type": "local", "path": ".pactum/snapshots"},
        "llm_adapters": [],
        "plugins": [],
    }


def resolve_contract(module_path: str) -> Any:
    """
    Resolve a contract function from a module path.

    Supports formats:
        - "module.path:function_name" (direct import)
        - "path/to/file.py:function_name" (file-based import)
    """
    if ":" not in module_path:
        raise ConfigError(f"Invalid contract path: {module_path}. Use 'module:function' format.")

    module_str, func_name = module_path.rsplit(":", 1)

    # Handle file-based paths
    if module_str.endswith(".py") or "/" in module_str:
        file_path = os.path.abspath(module_str)
        if not os.path.exists(file_path):
            raise ConfigError(f"Contract file not found: {file_path}")

        # Add parent directory to sys.path
        parent_dir = os.path.dirname(file_path)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)

        module_name = os.path.basename(file_path).replace(".py", "")
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    else:
        # Add cwd to sys.path for module imports
        if os.getcwd() not in sys.path:
            sys.path.insert(0, os.getcwd())
        module = importlib.import_module(module_str)

    func = getattr(module, func_name, None)
    if func is None:
        raise ConfigError(f"Function '{func_name}' not found in module '{module_str}'")

    if not is_contract(func):
        raise ConfigError(f"Function '{func_name}' is not decorated with @contract")

    return func


def discover_contracts(directory: str = ".") -> list[dict]:
    """
    Discover all contract-decorated functions in Python files under a directory.

    Returns list of dicts with 'module', 'function', 'contract_name'.
    """
    contracts = []
    directory = os.path.abspath(directory)

    for root, _, files in os.walk(directory):
        for fn in files:
            if fn.endswith(".py") and not fn.startswith("_"):
                filepath = os.path.join(root, fn)
                try:
                    rel_path = os.path.relpath(filepath, directory)
                    module_name = rel_path.replace("/", ".").replace(".py", "")

                    # Add directory to path
                    if directory not in sys.path:
                        sys.path.insert(0, directory)

                    spec = importlib.util.spec_from_file_location(module_name, filepath)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)

                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if callable(attr) and is_contract(attr):
                            contract_spec = get_contract_spec(attr)
                            contracts.append({
                                "module": module_name,
                                "function": attr_name,
                                "contract_name": contract_spec.name if contract_spec else "unknown",
                                "path": filepath,
                            })
                except Exception:
                    continue

    return contracts


def print_result(result: Any) -> None:
    """Pretty-print an execution result."""
    from pactum.core.runtime import ExecutionResult

    if isinstance(result, ExecutionResult):
        status = "[green]✓ SUCCESS[/green]" if result.success else "[red]✗ FAILED[/red]"
        panel = Panel(
            f"Run ID:      {result.run_id}\n"
            f"Snapshot ID: {result.snapshot_id}\n"
            f"Status:      {status}\n"
            f"Tokens Used: {result.total_tokens}\n"
            f"Outputs:     {result.outputs}",
            title="[bold]Pactum Execution Result[/bold]",
            box=box.ROUNDED,
        )
        console.print(panel)

        if result.error:
            console.print(f"\n[red]Error:[/red] {result.error}")


def print_snapshots(snapshots: list[dict]) -> None:
    """Pretty-print a list of snapshots."""
    if not snapshots:
        console.print("[yellow]No snapshots found.[/yellow]")
        return

    table = Table(title="Pactum Snapshots", box=box.ROUNDED)
    table.add_column("Snapshot ID", style="cyan")
    table.add_column("Contract", style="green")
    table.add_column("Timestamp", style="dim")

    for snap in snapshots:
        table.add_row(
            snap["snapshot_id"],
            snap["contract_name"],
            snap["timestamp"],
        )

    console.print(table)


def print_fuzz_report(report: Any) -> None:
    """Pretty-print a fuzz report."""
    from pactum.testing.harness import FuzzReport

    if isinstance(report, FuzzReport):
        status_color = "green" if report.failure_rate == 0 else "red"
        panel = Panel(
            f"Contract:     {report.contract_name}\n"
            f"Iterations:   {report.total_iterations}\n"
            f"Successes:    [green]{report.successes}[/green]\n"
            f"Violations:   [yellow]{len(report.violations)}[/yellow]\n"
            f"Crashes:      [red]{len(report.crashes)}[/red]\n"
            f"Failure Rate: [{status_color}]{report.failure_rate:.1%}[/{status_color}]",
            title="[bold]Fuzz Report[/bold]",
            box=box.ROUNDED,
        )
        console.print(panel)

        if report.violations:
            console.print("\n[yellow]Sample Violations:[/yellow]")
            for v in report.violations[:5]:
                console.print(f"  #{v['iteration']}: {v['error_type']}: {v['error']}")

        if report.crashes:
            console.print("\n[red]Sample Crashes:[/red]")
            for c in report.crashes[:5]:
                console.print(f"  #{c['iteration']}: {c['error_type']}: {c['error']}")
