"""Tests for sprint-source operators (GitHub Issues + scope filtering)."""

from __future__ import annotations

import httpx

from sendsprint.operators.github_issues_operator import GitHubIssuesOperator, _next_link
from sendsprint.scope import apply_scope, build_scope


def test_next_link_parsing():
    header = '<https://api.github.com/x?page=2>; rel="next", <https://api.github.com/x?page=5>; rel="last"'
    assert _next_link(header) == "https://api.github.com/x?page=2"
    assert _next_link(None) is None
    assert _next_link('<https://x>; rel="last"') is None


def test_issue_to_item_mapping():
    op = GitHubIssuesOperator(repo="o/r")
    issue = {
        "id": 100,
        "number": 42,
        "title": "Fix login",
        "body": "details",
        "state": "open",
        "assignee": {"login": "alice", "email": "alice@example.com"},
        "labels": [{"name": "bug"}, {"name": "frontend"}],
        "html_url": "https://github.com/o/r/issues/42",
        "created_at": "2026-01-01T00:00:00Z",
    }
    item = op._issue_to_item(issue)
    assert item.key == "42"
    assert item.type == "Issue"
    assert item.assignee == "alice"
    assert item.assignee_email == "alice@example.com"
    assert item.labels == ["bug", "frontend"]
    assert item.source_url.endswith("/issues/42")


def test_read_via_api_drops_prs_and_maps(monkeypatch):
    issues_page = [
        {"id": 1, "number": 1, "title": "real issue", "state": "open", "assignee": None},
        {"id": 2, "number": 2, "title": "a PR", "state": "open", "pull_request": {"url": "x"}},
    ]

    class FakeResp:
        status_code = 200
        headers = httpx.Headers({})

        def raise_for_status(self):
            return None

        def json(self):
            return issues_page

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, url, params=None):  # noqa: ANN001
            return FakeResp()

    monkeypatch.setattr(httpx, "Client", FakeClient)
    op = GitHubIssuesOperator(repo="o/r", token="t")
    sprint = op.read_sprint(sprint_id="*")
    assert sprint.source == "github"
    assert len(sprint.items) == 1  # PR filtered out
    assert sprint.items[0].title == "real issue"


def _gh_item(key, assignee_email=None, assignee=None, status="open"):
    from sendsprint.models.sprint import SprintItem

    return SprintItem(
        id=key,
        key=key,
        type="Issue",
        title=f"t{key}",
        status=status,
        assignee=assignee,
        assignee_email=assignee_email,
    )


def test_scope_mine_filters_by_email():
    from sendsprint.models.sprint import Sprint

    sprint = Sprint(
        id="s",
        name="s",
        source="github",
        items=[
            _gh_item("1", assignee_email="me@x.com"),
            _gh_item("2", assignee_email="other@x.com"),
        ],
    )
    scope = build_scope(mode="mine", user_email="me@x.com", allowed_statuses=["open"])
    filtered = apply_scope(sprint, scope)
    assert [i.key for i in filtered.items] == ["1"]
