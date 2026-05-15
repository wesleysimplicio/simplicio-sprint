"""Installer/configurator for the official Azure DevOps MCP server."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

MCP_PACKAGE = "@azure-devops/mcp"
DEFAULT_CODEX_CONFIG = Path.home() / ".codex" / "config.toml"
SECTION_HEADER = "[mcp_servers.azure-devops]"


class AzureDevopsMcpInstallResult(BaseModel):
    """Result of installing/configuring Azure DevOps MCP."""

    status: str
    config_path: str
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    package_version: str | None = None
    message: str | None = None
    dry_run: bool = False


def install_azure_devops_mcp(
    *,
    organization: str,
    project: str,
    team: str | None = None,
    config_path: Path | None = None,
    dry_run: bool = False,
    validate_package: bool = True,
) -> AzureDevopsMcpInstallResult:
    """Configure Codex to run Azure DevOps MCP through ``npx``.

    ``npx -y`` installs/updates the package on first server startup, so this
    installer does not pin a global npm install or require admin rights.
    """
    if not organization.strip():
        raise ValueError("organization is required")
    if not project.strip():
        raise ValueError("project is required")

    npx = _find_executable("npx")
    if not npx:
        return AzureDevopsMcpInstallResult(
            status="failed",
            config_path=str((config_path or DEFAULT_CODEX_CONFIG).expanduser()),
            message=(
                "Node.js/npx not found. Install Node.js 20+ before configuring Azure DevOps MCP."
            ),
            dry_run=dry_run,
        )

    package_version = _package_version() if validate_package else None
    cfg_path = (config_path or DEFAULT_CODEX_CONFIG).expanduser()
    args = ["-y", MCP_PACKAGE, organization.strip(), "-d", "core", "work", "work-items"]
    section = _render_codex_section(command=npx, args=args, project=project, team=team)

    if dry_run:
        return AzureDevopsMcpInstallResult(
            status="ok",
            config_path=str(cfg_path),
            command=npx,
            args=args,
            package_version=package_version,
            message=section,
            dry_run=True,
        )

    cfg_path.parent.mkdir(parents=True, exist_ok=True)
    existing = cfg_path.read_text(encoding="utf-8") if cfg_path.exists() else ""
    cfg_path.write_text(_upsert_section(existing, section), encoding="utf-8")

    return AzureDevopsMcpInstallResult(
        status="ok",
        config_path=str(cfg_path),
        command=npx,
        args=args,
        package_version=package_version,
        message="Azure DevOps MCP configured. Restart Codex so the new MCP server is loaded.",
        dry_run=False,
    )


def _find_executable(name: str) -> str | None:
    return shutil.which(name) or shutil.which(f"{name}.cmd")


def _package_version() -> str | None:
    npm = _find_executable("npm")
    if not npm:
        return None
    try:
        result = subprocess.run(
            [npm, "view", MCP_PACKAGE, "version", "--silent"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() or None


def _render_codex_section(
    *,
    command: str,
    args: list[str],
    project: str,
    team: str | None,
) -> str:
    env = {"ado_mcp_project": project.strip()}
    if team and team.strip():
        env["ado_mcp_team"] = team.strip()

    return "\n".join(
        [
            SECTION_HEADER,
            f"command = {_toml_string(command)}",
            f"args = {_toml_array(args)}",
            f"env = {_toml_inline_table(env)}",
            "startup_timeout_sec = 60",
            "",
        ]
    )


def _upsert_section(existing: str, section: str) -> str:
    lines = existing.splitlines()
    output: list[str] = []
    i = 0
    replaced = False
    while i < len(lines):
        if lines[i].strip() == SECTION_HEADER:
            replaced = True
            output.extend(section.rstrip().splitlines())
            i += 1
            while i < len(lines) and not lines[i].lstrip().startswith("["):
                i += 1
            continue
        output.append(lines[i])
        i += 1

    if not replaced:
        if output and output[-1].strip():
            output.append("")
        output.extend(section.rstrip().splitlines())

    return "\n".join(output).rstrip() + "\n"


def _toml_string(value: str) -> str:
    return json.dumps(value)


def _toml_array(values: list[str]) -> str:
    return "[" + ", ".join(_toml_string(value) for value in values) + "]"


def _toml_inline_table(values: dict[str, str]) -> str:
    body = ", ".join(f"{key} = {_toml_string(value)}" for key, value in values.items())
    return "{ " + body + " }"
