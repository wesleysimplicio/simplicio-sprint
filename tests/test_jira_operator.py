"""Unit tests for JiraOperator (transport selection + issue parsing)."""

from __future__ import annotations

import pytest

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
