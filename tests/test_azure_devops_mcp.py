"""Tests for Azure DevOps MCP installer."""

from pathlib import Path

from sendsprint.mcp.azure_devops import (
    SECTION_HEADER,
    _upsert_section,
    install_azure_devops_mcp,
)


def test_install_azure_devops_mcp_writes_codex_config(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setattr("sendsprint.mcp.azure_devops._find_executable", lambda name: name)
    monkeypatch.setattr("sendsprint.mcp.azure_devops._package_version", lambda: "2.7.0")
    config = tmp_path / "config.toml"

    result = install_azure_devops_mcp(
        organization="grupointerplayers",
        project="Projetos Ágeis",
        team="Squad Yankee",
        config_path=config,
    )

    text = config.read_text(encoding="utf-8")
    assert result.status == "ok"
    assert SECTION_HEADER in text
    assert "@azure-devops/mcp" in text
    assert 'ado_mcp_project = "Projetos \\u00c1geis"' in text
    assert 'ado_mcp_team = "Squad Yankee"' in text


def test_install_azure_devops_mcp_dry_run_does_not_write(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("sendsprint.mcp.azure_devops._find_executable", lambda name: name)
    monkeypatch.setattr("sendsprint.mcp.azure_devops._package_version", lambda: "2.7.0")
    config = tmp_path / "config.toml"

    result = install_azure_devops_mcp(
        organization="org",
        project="project",
        config_path=config,
        dry_run=True,
    )

    assert result.status == "ok"
    assert result.dry_run is True
    assert not config.exists()


def test_install_azure_devops_mcp_fails_when_npx_missing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("sendsprint.mcp.azure_devops._find_executable", lambda name: None)

    result = install_azure_devops_mcp(
        organization="org",
        project="project",
        config_path=tmp_path / "config.toml",
    )

    assert result.status == "failed"
    assert "npx not found" in (result.message or "")


def test_upsert_section_replaces_existing_azure_devops_section() -> None:
    existing = "\n".join(
        [
            "[other]",
            "value = 1",
            "",
            SECTION_HEADER,
            'command = "old"',
            "",
            "[next]",
            "value = 2",
        ]
    )
    updated = _upsert_section(existing, SECTION_HEADER + '\ncommand = "new"\n')

    assert 'command = "old"' not in updated
    assert 'command = "new"' in updated
    assert "[next]" in updated
