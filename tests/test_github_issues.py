"""Tests for GitHub Issues tracker boundary."""

from __future__ import annotations

import json
import subprocess

from sendsprint.trackers import GitHubIssuesTracker


def test_list_issues_normalizes_cli_json() -> None:
    payload = [
        {
            "number": 7,
            "title": "Add doctor",
            "state": "OPEN",
            "labels": [{"name": "enhancement"}],
            "assignees": [{"login": "wesley"}],
            "milestone": {"title": "Sprint"},
            "url": "https://github.com/o/r/issues/7",
            "closedByPullRequestsReferences": [{"url": "https://github.com/o/r/pull/9"}],
        }
    ]

    def fake_run(cmd, **kwargs):
        assert cmd[:3] == ["gh", "issue", "list"]
        return subprocess.CompletedProcess(cmd, 0, json.dumps(payload), "")

    issues = GitHubIssuesTracker("o/r", runner=fake_run).list_issues()
    assert issues[0].number == 7
    assert issues[0].labels == ["enhancement"]
    assert issues[0].linked_prs == ["https://github.com/o/r/pull/9"]


def test_comment_uses_issue_comment_command() -> None:
    captured: list[str] = []

    def fake_run(cmd, **kwargs):
        captured.extend(cmd)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    GitHubIssuesTracker("o/r", runner=fake_run).comment(3, "evidence")
    assert captured[:4] == ["gh", "issue", "comment", "3"]
    assert "--body" in captured
