from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from sendsprint.cli import app
from sendsprint.plugins import install_plugins, result_to_json


def test_install_plugins_writes_all_agent_host_files_and_manifest(tmp_path: Path) -> None:
    result = install_plugins(tmp_path)

    assert (tmp_path / ".claude/skills/sendsprint/SKILL.md").is_file()
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / ".hermes/skills/sendsprint.md").is_file()
    assert (tmp_path / ".openclaw/skills/sendsprint.md").is_file()
    assert (tmp_path / ".cursor/rules/sendsprint.mdc").is_file()
    assert (tmp_path / ".windsurf/rules/sendsprint.md").is_file()
    assert (tmp_path / ".kiro/steering/sendsprint.md").is_file()
    assert (tmp_path / ".antigravity/rules/sendsprint.md").is_file()
    assert (tmp_path / ".github/copilot-instructions.md").is_file()

    manifest = json.loads((tmp_path / ".sendsprint/plugins/manifest.json").read_text())
    assert manifest["runtime"] == "python-cli"
    assert manifest["entrypoints"]["full"] == "sendsprint full --workspace workspace.yaml"
    assert {item["platform"] for item in manifest["plugins"]} == {
        "claude",
        "codex",
        "hermes",
        "openclaw",
        "cursor",
        "windsurf",
        "kiro",
        "antigravity",
        "github-copilot",
    }
    assert "manifest_path" in result_to_json(result)


def test_install_plugins_preserves_existing_plugin_without_force(tmp_path: Path) -> None:
    target = tmp_path / "AGENTS.md"
    target.write_text("local override\n", encoding="utf-8")

    result = install_plugins(tmp_path, platforms=["codex"])

    assert target.read_text(encoding="utf-8") == "local override\n"
    assert result_to_json(result)["skipped"] == ["AGENTS.md"]


def test_install_plugins_dry_run_reports_without_writing(tmp_path: Path) -> None:
    result = install_plugins(tmp_path, platforms=["hermes"], dry_run=True)

    assert result.dry_run is True
    assert not (tmp_path / ".hermes/skills/sendsprint.md").exists()
    assert result_to_json(result)["created"] == [
        ".hermes/skills/sendsprint.md",
        ".sendsprint/plugins/manifest.json",
    ]


def test_plugins_cli_lists_profiles() -> None:
    result = CliRunner().invoke(app, ["plugins", "list", "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert {item["platform"] for item in payload} >= {
        "codex",
        "hermes",
        "github-copilot",
        "windsurf",
        "kiro",
        "antigravity",
    }


def test_plugins_cli_installs_selected_platforms(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "plugins",
            "install",
            "--repo",
            str(tmp_path),
            "--platform",
            "codex",
            "--platform",
            "cursor",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert sorted(payload["created"]) == [
        ".cursor/rules/sendsprint.mdc",
        ".sendsprint/plugins/manifest.json",
        "AGENTS.md",
    ]


def test_plugins_cli_rejects_unknown_platform(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        ["plugins", "install", "--repo", str(tmp_path), "--platform", "unknown"],
    )

    assert result.exit_code != 0
    assert "unknown plugin platform" in result.output
