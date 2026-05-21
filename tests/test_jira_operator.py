"""Unit tests for JiraOperator (transport selection + issue parsing)."""

from __future__ import annotations

import sys
import types

import httpx
import pytest

from sendsprint.browser_agents import BrowserCapturePayload
from sendsprint.operators.base import TransportUnavailable
from sendsprint.operators.jira_operator import (
    JIRA_TYPE_MAP,
    JiraOperator,
    _extract_text,
    _parse_dt,
)


def test_api_unavailable_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    op = JiraOperator(transport="api")
    assert op._api_available() is False
    with pytest.raises(TransportUnavailable):
        op._read_via_api(sprint_id=1)


def test_api_available_with_credentials() -> None:
    op = JiraOperator(
        base_url="https://example.atlassian.net",
        email="x@y.com",
        api_token="secret",
        transport="api",
    )
    assert op._api_available() is True
    assert op.base_url == "https://example.atlassian.net"


def test_resolve_transport_auto_picks_api_when_credentials_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_JIRA_AVAILABLE", raising=False)
    op = JiraOperator(
        base_url="https://example.atlassian.net",
        email="x@y.com",
        api_token="secret",
        transport="auto",
    )
    assert op._resolve_transport() == "api"


def test_resolve_transport_auto_falls_back_to_playwright(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MCP_JIRA_AVAILABLE", raising=False)
    monkeypatch.delenv("JIRA_BASE_URL", raising=False)
    monkeypatch.delenv("JIRA_EMAIL", raising=False)
    monkeypatch.delenv("JIRA_API_TOKEN", raising=False)
    op = JiraOperator(transport="auto")
    assert op._resolve_transport() == "playwright"


def test_issue_to_item_maps_all_fields() -> None:
    op = JiraOperator(base_url="https://example.atlassian.net", email="x@y.com", api_token="t")
    issue = {
        "id": "10001",
        "key": "PROJ-1",
        "fields": {
            "summary": "Implement login",
            "issuetype": {"name": "Story"},
            "status": {"name": "In Progress"},
            "assignee": {"displayName": "Alice"},
            "parent": {"key": "PROJ-100"},
            "labels": ["auth", "frontend"],
            "customfield_10016": 3.0,
            "customfield_10100": {
                "type": "doc",
                "content": [{"type": "text", "text": "User can log in"}],
            },
            "description": "Login flow",
            "created": "2026-05-07T10:00:00.000+0000",
            "updated": "2026-05-08T11:30:00.000+0000",
            "comment": {"comments": []},
            "issuelinks": [
                {
                    "type": {"name": "blocks"},
                    "outwardIssue": {"key": "PROJ-2"},
                }
            ],
        },
    }
    item = op._issue_to_item(issue)
    assert item.id == "10001"
    assert item.key == "PROJ-1"
    assert item.type == "Story"
    assert item.title == "Implement login"
    assert item.status == "In Progress"
    assert item.assignee == "Alice"
    assert item.parent_key == "PROJ-100"
    assert item.story_points == 3.0
    assert item.labels == ["auth", "frontend"]
    assert item.acceptance_criteria == "User can log in"
    assert item.source_url == "https://example.atlassian.net/browse/PROJ-1"
    assert len(item.links) == 1
    assert item.links[0].target_key == "PROJ-2"


def test_issue_type_map_defaults_to_issue_for_unknown() -> None:
    assert JIRA_TYPE_MAP.get("xyz", "Issue") == "Issue"
    assert JIRA_TYPE_MAP["story"] == "Story"
    assert JIRA_TYPE_MAP["sub-task"] == "Subtask"


def test_extract_text_handles_adf_doc_and_strings() -> None:
    assert _extract_text("plain") == "plain"
    assert _extract_text(None) is None
    adf = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "Hello"}]},
            {"type": "paragraph", "content": [{"type": "text", "text": "World"}]},
        ],
    }
    text = _extract_text(adf)
    assert text is not None
    assert "Hello" in text and "World" in text


def test_parse_dt_handles_iso_and_z_suffix() -> None:
    dt = _parse_dt("2026-05-07T10:00:00.000+0000")
    assert dt is not None
    assert dt.year == 2026
    assert _parse_dt(None) is None
    assert _parse_dt("not a date") is None


def test_sprint_from_jira_issues_aggregates_by_type() -> None:
    op = JiraOperator(base_url="https://example.atlassian.net", email="x@y.com", api_token="t")
    sprint_data = {
        "id": 42,
        "name": "Sprint 42",
        "state": "active",
        "startDate": "2026-05-01T00:00:00.000+0000",
        "endDate": "2026-05-15T00:00:00.000+0000",
    }
    issues = [
        {
            "id": "1",
            "key": "P-1",
            "fields": {"summary": "S1", "issuetype": {"name": "Story"}, "status": {"name": "Done"}},
        },
        {
            "id": "2",
            "key": "P-2",
            "fields": {"summary": "T1", "issuetype": {"name": "Task"}, "status": {"name": "Doing"}},
        },
        {
            "id": "3",
            "key": "P-3",
            "fields": {"summary": "B1", "issuetype": {"name": "Bug"}, "status": {"name": "Open"}},
        },
    ]
    sprint = op._sprint_from_jira_issues(sprint_data, issues, transport="api")
    assert sprint.id == "42"
    assert sprint.name == "Sprint 42"
    assert sprint.transport == "api"
    assert len(sprint.stories) == 1
    assert len(sprint.tasks) == 1
    assert len(sprint.bugs) == 1


def test_update_status_posts_comment_and_transition(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[tuple[str, str]] = []
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url)))
        if request.method == "GET":
            return httpx.Response(200, json={"transitions": [{"id": "31", "name": "Deployed"}]})
        return httpx.Response(204)

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self._client = real_client(transport=httpx.MockTransport(handler))

        def __enter__(self):
            return self._client

        def __exit__(self, exc_type, exc, tb) -> None:
            self._client.close()

    monkeypatch.setattr("sendsprint.operators.jira_operator.httpx.Client", FakeClient)
    op = JiraOperator(
        base_url="https://example.atlassian.net",
        email="x@y.com",
        api_token="secret",
        transport="api",
    )
    op.update_status("PROJ-1", "Deployed", "done")
    assert requests == [
        ("POST", "https://example.atlassian.net/rest/api/3/issue/PROJ-1/comment"),
        ("GET", "https://example.atlassian.net/rest/api/3/issue/PROJ-1/transitions"),
        ("POST", "https://example.atlassian.net/rest/api/3/issue/PROJ-1/transitions"),
    ]


def test_playwright_uses_native_capture_before_browser_agent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = types.ModuleType("playwright.sync_api")
    module.sync_playwright = object()
    package = types.ModuleType("playwright")
    package.sync_api = module
    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", module)
    monkeypatch.setattr(
        "sendsprint.operators.jira_operator.JiraOperator._scrape_items_via_playwright",
        lambda self, sync_playwright, sprint_url: [
            self._browser_item_to_sprint_item(
                BrowserCapturePayload.model_validate(
                    {"items": [{"key": "APP-9", "title": "Native capture", "type": "Story"}]}
                ).items[0]
            )
        ],
    )
    monkeypatch.setattr(
        "sendsprint.operators.jira_operator.capture_sprint_with_browser_agents",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("browser agent should not run")),
    )
    op = JiraOperator(
        base_url="https://example.atlassian.net",
        email="x@y.com",
        api_token="secret",
        transport="playwright",
    )

    sprint = op._read_via_playwright(sprint_id=9)

    assert sprint.items[0].key == "APP-9"
    assert sprint.transport == "playwright"


def test_playwright_falls_back_to_browser_agent_when_native_capture_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = types.ModuleType("playwright.sync_api")
    module.sync_playwright = object()
    package = types.ModuleType("playwright")
    package.sync_api = module
    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", module)
    monkeypatch.setattr(
        "sendsprint.operators.jira_operator.JiraOperator._scrape_items_via_playwright",
        lambda self, sync_playwright, sprint_url: (_ for _ in ()).throw(
            RuntimeError(f"playwright failed for {sprint_url}")
        ),
    )
    monkeypatch.setattr(
        "sendsprint.operators.jira_operator.capture_sprint_with_browser_agents",
        lambda **kwargs: (
            BrowserCapturePayload.model_validate(
                {
                    "sprint_name": "Sprint 9",
                    "items": [{"key": "APP-10", "title": "Fallback item", "type": "Task"}],
                }
            ),
            "codex",
        ),
    )
    op = JiraOperator(
        base_url="https://example.atlassian.net",
        email="x@y.com",
        api_token="secret",
        transport="playwright",
    )

    sprint = op._read_via_playwright(sprint_id=9)

    assert sprint.name == "Sprint 9"
    assert sprint.items[0].key == "APP-10"
    assert sprint.items[0].type == "Task"
