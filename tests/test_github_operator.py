"""Tests for :class:`sendsprint.operators.github_operator.GitHubOperator`.

GitHub is the only fully-wired operator in the new batch, so we exercise it
against httpx mocks (milestone resolution + paginated issues read +
update_status flow).
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from sendsprint.operators import TransportUnavailable
from sendsprint.operators.github_operator import GitHubOperator


def _install_fake_client(
    monkeypatch: pytest.MonkeyPatch, handler: Callable[[httpx.Request], httpx.Response]
) -> list[tuple[str, str]]:
    """Replace the operator's httpx.Client with a MockTransport-backed one.

    Returns a list that the handler populates with (method, url) tuples so
    tests can assert the calls afterwards.
    """
    requests: list[tuple[str, str]] = []
    real_client = httpx.Client

    def tracking(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, str(request.url)))
        return handler(request)

    class FakeClient:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            self._client = real_client(transport=httpx.MockTransport(tracking), **kwargs)

        def __enter__(self) -> httpx.Client:
            return self._client

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            self._client.close()

    monkeypatch.setattr("sendsprint.operators.github_operator.httpx.Client", FakeClient)
    return requests


def test_api_unavailable_without_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("GITHUB_OWNER", raising=False)
    monkeypatch.delenv("GITHUB_REPO", raising=False)
    op = GitHubOperator()
    assert op._api_available() is False
    with pytest.raises(TransportUnavailable):
        op._read_via_api()


def test_api_available_with_credentials() -> None:
    op = GitHubOperator(token="ghp_x", owner="o", repo="r", milestone=1)
    assert op._api_available() is True


def test_read_via_api_returns_milestone_issues(monkeypatch: pytest.MonkeyPatch) -> None:
    issues_response = [
        {
            "id": 101,
            "number": 7,
            "title": "Implement login",
            "body": "Wire the SSO flow.",
            "state": "open",
            "html_url": "https://github.com/o/r/issues/7",
            "assignee": {"login": "wesley", "email": None},
            "labels": [{"name": "feature"}, {"name": "priority/high"}],
            "created_at": "2026-05-01T10:00:00Z",
            "updated_at": "2026-05-21T11:00:00Z",
        },
        {
            "id": 102,
            "number": 8,
            "title": "Add unit tests",
            "body": "",
            "state": "closed",
            "html_url": "https://github.com/o/r/issues/8",
            "assignee": None,
            "labels": [{"name": "task"}],
            "created_at": "2026-05-02T10:00:00Z",
            "updated_at": "2026-05-22T11:00:00Z",
            # Skipped (PRs appear in /issues and must be filtered out).
        },
        {
            "id": 103,
            "number": 9,
            "title": "Refactor: skip me",
            "body": "",
            "state": "open",
            "html_url": "https://github.com/o/r/pull/9",
            "assignee": None,
            "labels": [],
            "created_at": "2026-05-02T11:00:00Z",
            "updated_at": "2026-05-02T11:00:00Z",
            "pull_request": {"url": "..."},
        },
    ]
    milestone_response = {
        "number": 3,
        "title": "Sprint 42",
        "state": "open",
        "description": "ship the v2 dispatcher",
        "created_at": "2026-05-01T00:00:00Z",
        "due_on": "2026-05-31T00:00:00Z",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/milestones/3"):
            return httpx.Response(200, json=milestone_response)
        if request.url.path.endswith("/issues"):
            # Single page; no Link header so the loop exits.
            return httpx.Response(200, json=issues_response)
        raise AssertionError(f"unexpected GitHub call: {request.url}")

    _install_fake_client(monkeypatch, handler)
    op = GitHubOperator(token="ghp_x", owner="o", repo="r", milestone=3)
    sprint = op._read_via_api()

    assert sprint.source == "github"
    assert sprint.name == "Sprint 42"
    assert sprint.id == "3"
    # 3 issues in payload, 1 PR filtered out -> 2 items.
    assert len(sprint.items) == 2
    first = sprint.items[0]
    assert first.key == "o/r#7"
    assert first.title == "Implement login"
    assert first.type == "Feature"  # "feature" label takes precedence
    assert first.status == "Open"
    assert first.assignee == "wesley"
    assert "priority/high" in first.labels
    assert sprint.items[1].type == "Task"
    assert sprint.items[1].status == "Closed"


def test_read_via_api_resolves_milestone_by_title(monkeypatch: pytest.MonkeyPatch) -> None:
    milestones_list = [
        {"number": 11, "title": "Old", "state": "open"},
        {"number": 12, "title": "Sprint 42", "state": "open"},
    ]
    milestone_full = {
        "number": 12,
        "title": "Sprint 42",
        "state": "open",
        "description": None,
        "created_at": None,
        "due_on": None,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/milestones") and "milestones/" not in str(request.url):
            return httpx.Response(200, json=milestones_list)
        if request.url.path.endswith("/milestones/12"):
            return httpx.Response(200, json=milestone_full)
        if request.url.path.endswith("/issues"):
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected GitHub call: {request.url}")

    _install_fake_client(monkeypatch, handler)
    op = GitHubOperator(token="ghp_x", owner="o", repo="r", milestone="Sprint 42")
    sprint = op._read_via_api()
    assert sprint.id == "12"
    assert sprint.items == []


def test_read_via_api_raises_when_milestone_title_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/milestones"):
            return httpx.Response(200, json=[])
        raise AssertionError(f"unexpected GitHub call: {request.url}")

    _install_fake_client(monkeypatch, handler)
    op = GitHubOperator(token="ghp_x", owner="o", repo="r", milestone="Ghost")
    with pytest.raises(TransportUnavailable) as excinfo:
        op._read_via_api()
    assert "milestone titled 'Ghost' not found" in str(excinfo.value)


def test_update_status_patches_issue_and_posts_comment(monkeypatch: pytest.MonkeyPatch) -> None:
    bodies: dict[str, dict[str, Any]] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "PATCH":
            bodies["patch"] = json.loads(request.content.decode())
            return httpx.Response(200, json={"state": "closed"})
        if request.method == "POST":
            bodies["comment"] = json.loads(request.content.decode())
            return httpx.Response(201, json={"id": 1})
        raise AssertionError(f"unexpected GitHub call: {request.method} {request.url}")

    requests = _install_fake_client(monkeypatch, handler)
    op = GitHubOperator(token="ghp_x", owner="o", repo="r", milestone=1)
    op.update_status("o/r#7", "done", comment="Deployed to staging")

    assert bodies["patch"] == {"state": "closed"}
    assert bodies["comment"] == {"body": "Deployed to staging"}
    # PATCH /issues/7 then POST /issues/7/comments
    assert [r[0] for r in requests] == ["PATCH", "POST"]
    assert all("/issues/7" in url for _, url in requests)


def test_update_status_handles_bare_issue_number(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"state": "open"})

    _install_fake_client(monkeypatch, handler)
    op = GitHubOperator(token="ghp_x", owner="o", repo="r", milestone=1)
    # Should not raise — accepts either "owner/repo#N" or bare "N".
    op.update_status("42", "in progress")
