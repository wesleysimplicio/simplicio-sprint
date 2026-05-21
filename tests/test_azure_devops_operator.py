"""Unit tests for AzureDevopsOperator (transport selection + workitem parsing)."""

from __future__ import annotations

import sys
import types

import httpx
import pytest

from sendsprint.browser_agents import BrowserCapturePayload
from sendsprint.operators.azure_devops_operator import (
    ADO_TYPE_MAP,
    AzureDevopsOperator,
    _chunked,
    _parse_dt,
    _strip_html,
)
from sendsprint.operators.base import TransportUnavailable
from sendsprint.profile import Profile


def test_api_unavailable_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AZURE_DEVOPS_ORG", raising=False)
    monkeypatch.delenv("AZURE_DEVOPS_PROJECT", raising=False)
    monkeypatch.delenv("AZURE_DEVOPS_PAT", raising=False)
    monkeypatch.setattr("sendsprint.profile.load", lambda: Profile())
    monkeypatch.setattr("sendsprint.credentials.get_secret", lambda provider, account: "")
    op = AzureDevopsOperator(transport="api")
    assert op._api_available() is False
    with pytest.raises(TransportUnavailable):
        op._read_via_api(iteration_path="Team\\Sprint 1")


def test_api_available_with_credentials() -> None:
    op = AzureDevopsOperator(
        organization="myorg",
        project="myproj",
        pat="secret",
        transport="api",
    )
    assert op._api_available() is True


def test_resolve_transport_auto_picks_api(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MCP_AZUREDEVOPS_AVAILABLE", raising=False)
    op = AzureDevopsOperator(
        organization="myorg",
        project="myproj",
        pat="secret",
        transport="auto",
    )
    assert op._resolve_transport() == "api"


def test_workitem_to_item_maps_all_fields() -> None:
    op = AzureDevopsOperator(organization="myorg", project="myproj", pat="t")
    wi = {
        "id": 1234,
        "fields": {
            "System.Title": "Add OAuth login",
            "System.WorkItemType": "User Story",
            "System.State": "Active",
            "System.AssignedTo": {"displayName": "Bob"},
            "System.Parent": 100,
            "System.Tags": "auth; backend",
            "System.Description": "<p>Implement <b>OAuth</b> login flow</p>",
            "System.CreatedDate": "2026-05-07T10:00:00Z",
            "System.ChangedDate": "2026-05-08T11:30:00Z",
            "Microsoft.VSTS.Scheduling.StoryPoints": 5,
            "Microsoft.VSTS.Common.AcceptanceCriteria": "<div>User logs in via OAuth</div>",
        },
    }
    base = "https://dev.azure.com/myorg/myproj"
    item = op._workitem_to_item(wi, base)
    assert item.id == "1234"
    assert item.key == "1234"
    assert item.type == "Story"
    assert item.title == "Add OAuth login"
    assert item.status == "Active"
    assert item.assignee == "Bob"
    assert item.parent_key == "100"
    assert item.story_points == 5
    assert item.labels == ["auth", "backend"]
    assert item.description is not None and "OAuth" in item.description
    assert item.acceptance_criteria == "User logs in via OAuth"
    assert item.source_url == "https://dev.azure.com/myorg/myproj/_workitems/edit/1234"


def test_ado_type_map_normalises_known_types() -> None:
    assert ADO_TYPE_MAP["user story"] == "Story"
    assert ADO_TYPE_MAP["product backlog item"] == "Story"
    assert ADO_TYPE_MAP["task"] == "Task"
    assert ADO_TYPE_MAP["bug"] == "Bug"
    assert ADO_TYPE_MAP.get("unknown", "Issue") == "Issue"


def test_strip_html_removes_tags_and_collapses_whitespace() -> None:
    assert _strip_html("<p>Hello   <b>World</b></p>") == "Hello World"
    assert _strip_html(None) is None
    assert _strip_html("") is None


def test_parse_dt_handles_z_suffix() -> None:
    dt = _parse_dt("2026-05-07T10:00:00Z")
    assert dt is not None
    assert dt.year == 2026
    assert _parse_dt(None) is None
    assert _parse_dt("garbage") is None


def test_chunked_splits_list() -> None:
    assert _chunked([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]
    assert _chunked([], 3) == []
    assert _chunked([1], 200) == [[1]]


def test_update_status_patches_work_item(monkeypatch: pytest.MonkeyPatch) -> None:
    requests: list[tuple[str, str]] = []
    real_client = httpx.Client

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url)))
        return httpx.Response(200, json={})

    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            self._client = real_client(transport=httpx.MockTransport(handler))

        def __enter__(self):
            return self._client

        def __exit__(self, exc_type, exc, tb) -> None:
            self._client.close()

    monkeypatch.setattr("sendsprint.operators.azure_devops_operator.httpx.Client", FakeClient)
    op = AzureDevopsOperator(
        organization="myorg",
        project="myproj",
        pat="secret",
        transport="api",
    )
    op.update_status("123", "Deployed", "done")
    assert requests == [
        (
            "PATCH",
            "https://dev.azure.com/myorg/myproj/_apis/wit/workitems/123?api-version=7.1",
        )
    ]


def test_playwright_capture_falls_back_to_browser_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    module = types.ModuleType("playwright.sync_api")
    module.sync_playwright = object()
    package = types.ModuleType("playwright")
    package.sync_api = module
    monkeypatch.setitem(sys.modules, "playwright", package)
    monkeypatch.setitem(sys.modules, "playwright.sync_api", module)
    monkeypatch.setattr(
        "sendsprint.operators.azure_devops_operator.AzureDevopsOperator._scrape_items_via_playwright",
        lambda self, sync_playwright, sprint_url: (_ for _ in ()).throw(
            RuntimeError(f"playwright blocked for {sprint_url}")
        ),
    )
    monkeypatch.setattr(
        "sendsprint.operators.azure_devops_operator.capture_sprint_with_browser_agents",
        lambda **kwargs: (
            BrowserCapturePayload.model_validate(
                {
                    "sprint_name": "Sprint 98",
                    "items": [
                        {
                            "key": "5678",
                            "title": "Atualizar autenticacao",
                            "type": "Task",
                            "status": "New",
                        }
                    ],
                }
            ),
            "codex",
        ),
    )
    op = AzureDevopsOperator(
        organization="myorg",
        project="myproj",
        team="MyTeam",
        transport="playwright",
    )

    sprint = op._read_via_playwright(iteration_path="myproj\\MyTeam\\Sprint 98")

    assert sprint.name == "Sprint 98"
    assert sprint.transport == "playwright"
    assert sprint.items[0].key == "5678"
    assert sprint.items[0].type == "Task"
