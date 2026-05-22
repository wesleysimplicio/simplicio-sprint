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


def test_install_plugins_packaged_claude_writes_full_tree(tmp_path: Path) -> None:
    result = install_plugins(tmp_path, platforms=["claude"], packaged=True)

    target = tmp_path / ".claude/plugins/sendsprint"
    assert (target / ".claude-plugin/plugin.json").is_file()
    assert (target / "commands/sendsprint.md").is_file()
    assert (target / "agents/sprint-deliverer.md").is_file()
    assert (target / "agents/sprint-reviewer.md").is_file()
    assert (target / "skills/sendsprint/SKILL.md").is_file()
    assert (target / "hooks/hooks.json").is_file()
    assert (target / "hooks/pre-commit.sh").is_file()

    manifest_payload = json.loads(
        (tmp_path / ".sendsprint/plugins/manifest.json").read_text()
    )
    assert manifest_payload["plugins"][0]["mode"] == "packaged"
    assert manifest_payload["plugins"][0]["target"] == ".claude/plugins/sendsprint"
    assert result_to_json(result)["changed"] is True


def test_install_plugins_packaged_codex_writes_agents_and_config(tmp_path: Path) -> None:
    install_plugins(tmp_path, platforms=["codex"], packaged=True)

    target = tmp_path / ".codex/plugins/sendsprint"
    assert (target / "plugin.toml").is_file()
    assert (target / "AGENTS.md").is_file()
    assert (target / "config.toml").is_file()
    assert (target / "prompts/sendsprint.md").is_file()
    assert (target / "hooks/hooks.json").is_file()


def test_install_plugins_packaged_hermes_and_openclaw_have_manifests(tmp_path: Path) -> None:
    install_plugins(tmp_path, platforms=["hermes", "openclaw"], packaged=True)

    hermes = tmp_path / ".hermes/plugins/sendsprint"
    openclaw = tmp_path / ".openclaw/plugins/sendsprint"
    assert (hermes / "hermes-plugin.json").is_file()
    assert (hermes / "skills/sendsprint.md").is_file()
    assert (hermes / "commands/sprint.md").is_file()
    assert (openclaw / "openclaw-plugin.json").is_file()
    assert (openclaw / "commands/review-sprint.md").is_file()
    assert (openclaw / "commands/security-review.md").is_file()


def test_install_plugins_packaged_falls_back_for_unsupported_platforms(tmp_path: Path) -> None:
    # cursor has no package_dir → falls back to flat install even with packaged=True
    install_plugins(tmp_path, platforms=["cursor"], packaged=True)

    assert (tmp_path / ".cursor/rules/sendsprint.mdc").is_file()
    assert not (tmp_path / ".cursor/plugins/sendsprint").exists()


def test_install_plugins_packaged_dry_run_does_not_write(tmp_path: Path) -> None:
    result = install_plugins(
        tmp_path, platforms=["claude"], packaged=True, dry_run=True
    )

    assert result.dry_run is True
    assert not (tmp_path / ".claude/plugins/sendsprint/.claude-plugin/plugin.json").exists()
    # but the path should still be reported as "created"
    created = result_to_json(result)["created"]
    assert any(
        path.endswith(".claude/plugins/sendsprint/.claude-plugin/plugin.json")
        for path in created
    )


def test_plugins_cli_packaged_flag_installs_full_tree(tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "plugins",
            "install",
            "--repo",
            str(tmp_path),
            "--platform",
            "openclaw",
            "--packaged",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    created_paths = set(payload["created"])
    assert ".openclaw/plugins/sendsprint/openclaw-plugin.json" in created_paths
    assert ".openclaw/plugins/sendsprint/commands/review-sprint.md" in created_paths
