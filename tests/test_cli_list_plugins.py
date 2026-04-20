"""Tests for `pet list-plugins` CLI subcommand."""
from __future__ import annotations

import json

from click.testing import CliRunner

from pet_infra.cli import main


class TestListPlugins:
    """Tests for the list-plugins subcommand."""

    def test_plain_output_exit_zero(self) -> None:
        """list-plugins exits 0 and prints registry names and plugin keys."""
        runner = CliRunner()
        result = runner.invoke(main, ["list-plugins"])
        assert result.exit_code == 0, result.output
        assert "storage" in result.output
        assert "local" in result.output

    def test_json_output_valid_json(self) -> None:
        """list-plugins --json exits 0 and emits valid JSON with all 6 registry keys."""
        runner = CliRunner()
        result = runner.invoke(main, ["list-plugins", "--json"])
        assert result.exit_code == 0, result.output
        data = json.loads(result.output)
        expected_keys = {"trainers", "evaluators", "converters", "metrics", "datasets", "storage"}
        assert expected_keys == set(data.keys())
        assert "local" in data["storage"]
