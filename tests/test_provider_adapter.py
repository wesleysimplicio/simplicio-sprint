"""Tests for the SendSprint v2 ProviderAdapter contract and built-in adapters."""

from __future__ import annotations

import pytest

from sendsprint.models import SprintItem
from sendsprint.providers import (
    ClaudeAdapter,
    CodexAdapter,
    CopilotAdapter,
    CursorAdapter,
    DispatchTicket,
    KiroAdapter,
    ProviderAdapter,
    ProviderAuthError,
    ProviderCapabilities,
    ProviderError,
    ProviderNoCloudError,
    PRResult,
    RunStatus,
    WindsurfAdapter,
)
from sendsprint.providers.claude import ClaudeAdapter as _ClaudeAdapter  # re-import guard


def _make_item(key: str = "ADO-1") -> SprintItem:
    return SprintItem(
        id=key,
        key=key,
        type="Task",
        title=f"Task {key}",
        status="To Do",
    )


class _MockAdapter(ProviderAdapter):
    """Minimal in-memory adapter that exercises the full contract."""

    name = "mock"

    def __init__(self, cloud: bool = True) -> None:
        self._cloud = cloud
        self._statuses: dict[str, RunStatus] = {}

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(cloud=self._cloud)

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        ticket = DispatchTicket(run_id=f"run-{item.key}", provider=self.name, item_key=item.key)
        self._statuses[ticket.run_id] = "queued"
        return ticket

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        # Advance state: queued -> running -> done on successive polls.
        previous = self._statuses[ticket.run_id]
        nxt: RunStatus = {"queued": "running", "running": "done"}.get(previous, previous)
        self._statuses[ticket.run_id] = nxt
        return nxt

    def collect(self, ticket: DispatchTicket) -> PRResult:
        return PRResult(
            run_id=ticket.run_id,
            provider=self.name,
            item_key=ticket.item_key,
            status="done",
            pr_url=f"https://example.test/{ticket.item_key}",
            branch=f"mock/{ticket.item_key}",
        )


def test_mock_adapter_satisfies_contract() -> None:
    adapter = _MockAdapter()
    item = _make_item()

    ticket = adapter.dispatch(item)
    assert ticket.provider == "mock"
    assert ticket.item_key == "ADO-1"

    assert adapter.poll(ticket) == "running"
    assert adapter.poll(ticket) == "done"

    result = adapter.collect(ticket)
    assert result.status == "done"
    assert result.pr_url == "https://example.test/ADO-1"


def test_claude_adapter_requires_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    adapter = ClaudeAdapter()
    assert adapter.capabilities().cloud is True
    with pytest.raises(ProviderAuthError):
        adapter.dispatch(_make_item())


def test_claude_adapter_with_key_reaches_unwired_dispatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    adapter = ClaudeAdapter()
    with pytest.raises(ProviderError) as excinfo:
        adapter.dispatch(_make_item())
    # Auth passed -> we hit the explicit "not yet wired" guard, NOT the auth one.
    assert not isinstance(excinfo.value, ProviderAuthError)
    assert "not yet wired" in str(excinfo.value)


def test_codex_adapter_requires_openai_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    adapter = CodexAdapter()
    assert adapter.capabilities() == ProviderCapabilities(cloud=True, network=False, mcp=False)
    with pytest.raises(ProviderAuthError):
        adapter.dispatch(_make_item())


def test_copilot_adapter_requires_token_and_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("COPILOT_TARGET_REPO", raising=False)
    adapter = CopilotAdapter()
    with pytest.raises(ProviderAuthError):
        adapter.dispatch(_make_item())

    monkeypatch.setenv("GITHUB_TOKEN", "ghp_test")
    adapter = CopilotAdapter()
    with pytest.raises(ProviderError) as excinfo:
        adapter.dispatch(_make_item())
    assert "COPILOT_TARGET_REPO" in str(excinfo.value)


@pytest.mark.parametrize(
    ("adapter_cls", "expected_fallback"),
    [
        (CursorAdapter, "claude"),
        (WindsurfAdapter, "claude"),
        (KiroAdapter, "codex"),
    ],
)
def test_spike_adapters_declare_no_cloud_with_fallback(
    adapter_cls: type[ProviderAdapter], expected_fallback: str
) -> None:
    adapter = adapter_cls()
    caps = adapter.capabilities()
    assert caps.cloud is False
    assert caps.fallback == expected_fallback
    with pytest.raises(ProviderNoCloudError):
        adapter.dispatch(_make_item())


def test_claude_adapter_re_export_matches() -> None:
    # Defensive: package re-export and module path resolve to the same class.
    assert ClaudeAdapter is _ClaudeAdapter
