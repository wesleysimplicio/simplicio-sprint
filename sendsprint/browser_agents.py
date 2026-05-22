"""Browser-agent fallback helpers for sprint capture."""

from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from sendsprint.platform import is_windows

logger = logging.getLogger(__name__)

BrowserAgentKey = Literal["claude", "codex", "hermes", "openclaw"]
_AGENT_ORDER: tuple[BrowserAgentKey, ...] = ("claude", "codex", "hermes", "openclaw")


class BrowserAgentCaptureError(RuntimeError):
    """Raised when a browser-agent fallback cannot capture sprint data."""


class BrowserCapturedItem(BaseModel):
    """Normalized sprint item returned by a browser-capable agent."""

    model_config = ConfigDict(extra="ignore")

    key: str
    title: str
    type: str = "Issue"
    status: str = "unknown"
    assignee: str | None = None
    story_points: float | None = None
    description: str | None = None
    source_url: str | None = None


class BrowserCapturePayload(BaseModel):
    """Structured browser-agent response for sprint capture."""

    model_config = ConfigDict(extra="ignore")

    sprint_name: str | None = None
    sprint_goal: str | None = None
    error: str | None = None
    notes: list[str] = Field(default_factory=list)
    items: list[BrowserCapturedItem] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class BrowserAgentAvailability:
    key: BrowserAgentKey
    executable: str | None
    command_template: str | None
    available: bool
    reason: str | None = None


def detect_browser_agents() -> list[BrowserAgentAvailability]:
    """Return browser-agent availability in the requested fallback order."""
    out: list[BrowserAgentAvailability] = []
    for key in _AGENT_ORDER:
        env_name = _agent_command_env(key)
        command_template = os.getenv(env_name)
        if command_template:
            executable = _resolve_command(_split_command(command_template)[0])
            out.append(
                BrowserAgentAvailability(
                    key=key,
                    executable=executable,
                    command_template=command_template,
                    available=bool(executable),
                    reason=None if executable else f"{env_name} points to a missing executable",
                )
            )
            continue

        builtin = _builtin_executable(key)
        if builtin:
            out.append(
                BrowserAgentAvailability(
                    key=key,
                    executable=builtin,
                    command_template=None,
                    available=True,
                )
            )
            continue

        reason = (
            f"set {env_name} to enable this browser-agent adapter"
            if key != "codex"
            else "codex executable not found on PATH"
        )
        out.append(
            BrowserAgentAvailability(
                key=key,
                executable=None,
                command_template=None,
                available=False,
                reason=reason,
            )
        )
    return out


def capture_sprint_with_browser_agents(
    *,
    source: Literal["jira", "azuredevops"],
    sprint_url: str,
    identifier: str,
    working_dir: str | Path | None = None,
) -> tuple[BrowserCapturePayload, BrowserAgentKey]:
    """Ask installed browser-capable agents to inspect a sprint URL."""
    attempts: list[str] = []
    cwd = str(Path(working_dir or Path.cwd()).resolve())
    for agent in detect_browser_agents():
        if not agent.available or not agent.executable:
            if agent.reason:
                attempts.append(f"{agent.key}: {agent.reason}")
            continue
        try:
            payload = _run_capture(
                agent,
                source=source,
                sprint_url=sprint_url,
                identifier=identifier,
                cwd=cwd,
            )
        except BrowserAgentCaptureError as exc:
            attempts.append(f"{agent.key}: {exc}")
            continue
        if payload.error:
            attempts.append(f"{agent.key}: {payload.error}")
            continue
        if payload.items:
            return payload, agent.key
        attempts.append(f"{agent.key}: no sprint items returned")
    detail = "; ".join(attempts) if attempts else "no browser-agent adapter available"
    raise BrowserAgentCaptureError(detail)


def _run_capture(
    agent: BrowserAgentAvailability,
    *,
    source: Literal["jira", "azuredevops"],
    sprint_url: str,
    identifier: str,
    cwd: str,
) -> BrowserCapturePayload:
    if agent.command_template:
        return _run_env_command(
            agent,
            source=source,
            sprint_url=sprint_url,
            identifier=identifier,
            cwd=cwd,
        )
    if agent.key == "codex":
        return _run_codex_capture(
            agent.executable or "codex",
            source=source,
            sprint_url=sprint_url,
            identifier=identifier,
            cwd=cwd,
        )
    raise BrowserAgentCaptureError(f"{agent.key} requires {_agent_command_env(agent.key)}")


def _run_codex_capture(
    executable: str,
    *,
    source: Literal["jira", "azuredevops"],
    sprint_url: str,
    identifier: str,
    cwd: str,
) -> BrowserCapturePayload:
    prompt = _capture_prompt(source=source, sprint_url=sprint_url, identifier=identifier)
    with tempfile.TemporaryDirectory(prefix="sendsprint-browser-agent-") as tmp:
        schema_path = Path(tmp) / "browser_capture_schema.json"
        schema_path.write_text(json.dumps(_capture_schema()), encoding="utf-8")
        cmd = [
            executable,
            "exec",
            "--skip-git-repo-check",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--output-schema",
            str(schema_path),
            "-C",
            cwd,
            prompt,
        ]
        result = _subprocess_run(cmd, cwd=cwd)
    return _parse_payload("codex", result.stdout, result.stderr)


def _run_env_command(
    agent: BrowserAgentAvailability,
    *,
    source: Literal["jira", "azuredevops"],
    sprint_url: str,
    identifier: str,
    cwd: str,
) -> BrowserCapturePayload:
    assert agent.command_template is not None  # noqa: S101 - internal contract
    prompt = _capture_prompt(source=source, sprint_url=sprint_url, identifier=identifier)
    rendered = agent.command_template.format(
        prompt=prompt,
        sprint_url=sprint_url,
        identifier=identifier,
        source=source,
        cwd=cwd,
    )
    result = _subprocess_run(_split_command(rendered), cwd=cwd)
    return _parse_payload(agent.key, result.stdout, result.stderr)


def _parse_payload(agent_key: str, stdout: str, stderr: str) -> BrowserCapturePayload:
    raw = stdout.strip()
    if not raw:
        raise BrowserAgentCaptureError(stderr.strip() or "empty output")
    try:
        return BrowserCapturePayload.model_validate_json(raw)
    except ValidationError:
        extracted = _extract_json_object(raw)
        if extracted is None:
            raise BrowserAgentCaptureError(
                stderr.strip() or f"{agent_key} did not return valid JSON"
            ) from None
        return BrowserCapturePayload.model_validate(extracted)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _capture_prompt(
    *,
    source: Literal["jira", "azuredevops"],
    sprint_url: str,
    identifier: str,
) -> str:
    return (
        "Open the sprint URL in an authenticated browser or browser tool if available. "
        "Capture the sprint name and every visible sprint item. "
        "Return only JSON that matches the provided schema. "
        "If browser access or auth is blocked, set the error field and keep items empty. "
        f"Provider: {source}. Identifier: {identifier}. Sprint URL: {sprint_url}"
    )


def _capture_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": True,
        "properties": {
            "sprint_name": {"type": ["string", "null"]},
            "sprint_goal": {"type": ["string", "null"]},
            "error": {"type": ["string", "null"]},
            "notes": {"type": "array", "items": {"type": "string"}},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": True,
                    "properties": {
                        "key": {"type": "string"},
                        "title": {"type": "string"},
                        "type": {"type": "string"},
                        "status": {"type": "string"},
                        "assignee": {"type": ["string", "null"]},
                        "story_points": {"type": ["number", "null"]},
                        "description": {"type": ["string", "null"]},
                        "source_url": {"type": ["string", "null"]},
                    },
                    "required": ["key", "title"],
                },
            },
        },
        "required": ["items"],
    }


def _subprocess_run(cmd: list[str], *, cwd: str) -> subprocess.CompletedProcess[str]:
    logger.info("running browser-agent fallback: %s", cmd[0])
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BrowserAgentCaptureError(str(exc)) from exc
    except subprocess.TimeoutExpired as exc:
        raise BrowserAgentCaptureError(f"timed out after {exc.timeout}s") from exc
    if result.returncode != 0:
        raise BrowserAgentCaptureError(result.stderr.strip() or f"exit code {result.returncode}")
    return result


def _agent_command_env(key: BrowserAgentKey) -> str:
    return f"SENDSPRINT_BROWSER_AGENT_{key.upper()}_COMMAND"


def _builtin_executable(key: BrowserAgentKey) -> str | None:
    if key != "codex":
        return None
    return _resolve_command("codex")


def _resolve_command(command: str) -> str | None:
    return shutil.which(command) or shutil.which(f"{command}.cmd")


def _split_command(command: str) -> list[str]:
    return shlex.split(command, posix=not is_windows())
