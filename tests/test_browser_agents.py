"""Tests for browser-agent sprint capture fallbacks."""

from __future__ import annotations

import pytest

from sendsprint.browser_agents import (
    BrowserAgentAvailability,
    BrowserAgentCaptureError,
    BrowserCapturePayload,
    capture_sprint_with_browser_agents,
    detect_browser_agents,
)


def test_detect_browser_agents_reports_builtin_and_env_adapters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "SENDSPRINT_BROWSER_AGENT_CLAUDE_COMMAND",
        "claude-browser --url {sprint_url}",
    )

    def fake_which(command: str) -> str | None:
        mapping = {
            "claude-browser": "/opt/claude-browser",
            "codex": "/opt/codex",
        }
        return mapping.get(command)

    monkeypatch.setattr("sendsprint.browser_agents.shutil.which", fake_which)

    agents = detect_browser_agents()

    assert [agent.key for agent in agents] == ["claude", "codex", "hermes", "openclaw"]
    assert agents[0].available is True
    assert agents[0].command_template == "claude-browser --url {sprint_url}"
    assert agents[1].available is True
    assert agents[1].executable == "/opt/codex"
    assert agents[2].available is False
    assert "SENDSPRINT_BROWSER_AGENT_HERMES_COMMAND" in (agents[2].reason or "")


def test_capture_sprint_with_browser_agents_skips_unavailable_then_uses_codex(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    agents = [
        BrowserAgentAvailability(
            key="claude",
            executable=None,
            command_template=None,
            available=False,
            reason="not installed",
        ),
        BrowserAgentAvailability(
            key="codex",
            executable="/opt/codex",
            command_template=None,
            available=True,
        ),
    ]
    monkeypatch.setattr("sendsprint.browser_agents.detect_browser_agents", lambda: agents)
    monkeypatch.setattr(
        "sendsprint.browser_agents._run_capture",
        lambda *args, **kwargs: BrowserCapturePayload.model_validate(
            {
                "sprint_name": "Sprint 98",
                "items": [{"key": "APP-1", "title": "Login page", "type": "Story"}],
            }
        ),
    )

    payload, adapter = capture_sprint_with_browser_agents(
        source="jira",
        sprint_url="https://example.atlassian.net/sprint/98",
        identifier="98",
        working_dir=tmp_path,
    )

    assert adapter == "codex"
    assert payload.sprint_name == "Sprint 98"
    assert payload.items[0].key == "APP-1"


def test_capture_sprint_with_browser_agents_raises_when_every_adapter_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    agents = [
        BrowserAgentAvailability(
            key="claude",
            executable="/opt/claude",
            command_template="claude {prompt}",
            available=True,
        )
    ]
    monkeypatch.setattr("sendsprint.browser_agents.detect_browser_agents", lambda: agents)

    def fail(*args, **kwargs):
        raise BrowserAgentCaptureError("auth blocked")

    monkeypatch.setattr("sendsprint.browser_agents._run_capture", fail)

    with pytest.raises(BrowserAgentCaptureError) as exc:
        capture_sprint_with_browser_agents(
            source="azuredevops",
            sprint_url="https://dev.azure.com/org/project/_sprints/taskboard/team/sprint",
            identifier="project\\team\\sprint",
            working_dir=tmp_path,
        )

    assert "claude: auth blocked" in str(exc.value)


def test_parse_payload_extracts_json_from_mixed_stdout() -> None:
    from sendsprint.browser_agents import _parse_payload

    payload = _parse_payload(
        "codex",
        "thinking...\n{\"items\":[{\"key\":\"APP-7\",\"title\":\"Fix auth\"}]}",
        "",
    )

    assert payload.items[0].key == "APP-7"


def test_subprocess_run_surfaces_nonzero_exit() -> None:
    from sendsprint.browser_agents import _subprocess_run

    with pytest.raises(BrowserAgentCaptureError):
        _subprocess_run(
            ["python", "-c", "import sys; sys.exit(2)"],
            cwd=".",
        )
