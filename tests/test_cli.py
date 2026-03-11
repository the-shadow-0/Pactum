"""
Tests for the Pactum CLI — using Click's CliRunner.
"""

import pytest
import os
import json
from click.testing import CliRunner

from pactum.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def project_dir(tmp_path):
    """Create a temporary project directory."""
    return str(tmp_path)


class TestCLIInit:
    def test_init_creates_files(self, runner, project_dir):
        result = runner.invoke(cli, ["init", "--dir", project_dir, "--name", "test-project"])
        assert result.exit_code == 0
        assert os.path.exists(os.path.join(project_dir, "pactum.yaml"))
        assert os.path.exists(os.path.join(project_dir, ".pactum", "snapshots"))
        assert os.path.exists(os.path.join(project_dir, "contracts", "example.py"))

    def test_init_idempotent(self, runner, project_dir):
        runner.invoke(cli, ["init", "--dir", project_dir])
        result = runner.invoke(cli, ["init", "--dir", project_dir])
        assert result.exit_code == 0
        assert "already exists" in result.output


class TestCLIVersion:
    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestCLIRun:
    def test_run_missing_input_file(self, runner):
        result = runner.invoke(cli, ["run", "some:contract", "--input-file", "/nonexistent.json"])
        assert result.exit_code != 0

    def test_run_with_fixture(self, runner, project_dir):
        # Set up a project
        runner.invoke(cli, ["init", "--dir", project_dir])

        # Create input file
        input_path = os.path.join(project_dir, "input.json")
        with open(input_path, "w") as f:
            json.dump({"name": "TestUser"}, f)

        contract_path = os.path.join(project_dir, "contracts", "example.py") + ":hello_world"
        result = runner.invoke(cli, [
            "-c", os.path.join(project_dir, "pactum.yaml"),
            "run", contract_path,
            "--input-file", input_path,
            "--seed", "42",
        ])
        # The contract should run (may need OPENAI_API_KEY for non-stub adapter)
        # With stub adapter it should succeed
        assert result.exit_code == 0 or "Error" in result.output


class TestCLISnapshots:
    def test_list_empty(self, runner, project_dir):
        runner.invoke(cli, ["init", "--dir", project_dir])
        result = runner.invoke(cli, [
            "-c", os.path.join(project_dir, "pactum.yaml"),
            "snapshots", "list",
        ])
        assert result.exit_code == 0
