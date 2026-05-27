"""Tests for the host-injected MCP transport seam and operator MCP reads."""

from __future__ import annotations

import pytest

from sendsprint.operators import _mcp_bridge
from sendsprint.operators.azure_devops_operator import AzureDevopsOperator
from sendsprint.operators.base import TransportUnavailable
from sendsprint.operators.github_issues_operator import GitHubIssuesOperator
from sendsprint.operators.jira_operator import JiraOperator


@pytest.fixture(autouse=True)
def _clear_providers():
    _mcp_bridge.clear_providers()
    yield
    _mcp_bridge.clear_providers()


def test_fetch_raises_without_provider():
    with pytest.raises(_mcp_bridge.MCPProviderUnavailable):
        _mcp_bridge.fetch("jira", sprint_id="42")


def test_register_unregister_has_provider():
    assert not _mcp_bridge.has_provider("jira")
    _mcp_bridge.register_provider("jira", lambda **q: {"sprint": {}, "issues": []})
    assert _mcp_bridge.has_provider("jira")
    _mcp_bridge.unregister_provider("jira")
    assert not _mcp_bridge.has_provider("jira")


def test_fetch_rejects_non_dict_payload():
    _mcp_bridge.register_provider("jira", lambda **q: ["not", "a", "dict"])
    with pytest.raises(_mcp_bridge.MCPProviderUnavailable):
        _mcp_bridge.fetch("jira", sprint_id="42")


def test_mcp_available_reflects_registration():
    op = JiraOperator(base_url="https://x", email="m@x.com", api_token="t")
    assert op._mcp_available() is False
    _mcp_bridge.register_provider("jira", lambda **q: {})
    assert op._mcp_available() is True


def test_jira_reads_via_mcp():
    payload = {
        "sprint": {"id": "42", "name": "Sprint 42", "state": "active"},
        "issues": [
            {
                "id": "1001",
                "key": "ABC-1",
                "fields": {
                    "summary": "Do the thing",
                    "issuetype": {"name": "Task"},
                    "status": {"name": "To Do"},
                },
            }
        ],
    }
    _mcp_bridge.register_provider("jira", lambda **q: payload)
    op = JiraOperator(base_url="https://x.atlassian.net", email="me@x.com", api_token="t")
    sprint = op.read_sprint(sprint_id="42")
    assert sprint.transport == "mcp"
    assert sprint.name == "Sprint 42"
    assert [i.key for i in sprint.items] == ["ABC-1"]
    assert sprint.items[0].title == "Do the thing"


def test_ado_reads_via_mcp():
    payload = {
        "work_items": [
            {
                "id": 55,
                "fields": {
                    "System.Title": "Fix bug",
                    "System.WorkItemType": "Bug",
                    "System.State": "Active",
                },
            }
        ]
    }
    _mcp_bridge.register_provider("azuredevops", lambda **q: payload)
    op = AzureDevopsOperator(organization="org", project="proj", pat="p")
    sprint = op.read_sprint(iteration_path="Team\\Sprint 1")
    assert sprint.transport == "mcp"
    assert sprint.items[0].title == "Fix bug"
    assert sprint.items[0].type == "Bug"


def test_github_reads_via_mcp_and_drops_prs():
    payload = {
        "issues": [
            {"id": 1, "number": 7, "title": "real", "state": "open", "assignee": None},
            {"id": 2, "number": 8, "title": "a pr", "state": "open", "pull_request": {"url": "x"}},
        ]
    }
    _mcp_bridge.register_provider("github", lambda **q: payload)
    op = GitHubIssuesOperator(repo="o/r")
    sprint = op.read_sprint(sprint_id="*")
    assert sprint.transport == "mcp"
    assert [i.key for i in sprint.items] == ["7"]


def test_jira_falls_back_to_api_when_no_provider():
    """With no MCP provider, auto transport skips MCP and reaches the REST path."""
    op = JiraOperator(base_url="", email="", api_token="")  # api unavailable too
    assert op._mcp_available() is False
    with pytest.raises(TransportUnavailable):
        op.read_sprint(sprint_id="42")
