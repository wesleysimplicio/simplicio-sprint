"""GitHub Issues tracker boundary backed by the GitHub CLI."""

from __future__ import annotations

import json
import subprocess
import time
from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

IssueState = Literal["open", "closed", "all"]
Runner = Callable[..., subprocess.CompletedProcess[str]]


class GitHubIssue(BaseModel):
    """Normalized GitHub Issue data."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    number: int
    title: str
    state: str = "open"
    labels: list[str] = Field(default_factory=list)
    assignees: list[str] = Field(default_factory=list)
    milestone: str | None = None
    url: str | None = None
    body: str | None = None
    linked_prs: list[str] = Field(default_factory=list)


class GitHubIssuesTracker:
    """Safe, mockable GitHub Issues integration."""

    def __init__(
        self,
        repo: str,
        *,
        runner: Runner = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
        rate_limit_seconds: float = 0.0,
    ) -> None:
        self.repo = repo
        self.runner = runner
        self.sleep = sleep
        self.rate_limit_seconds = rate_limit_seconds

    def list_issues(self, *, state: IssueState = "open", limit: int = 100) -> list[GitHubIssue]:
        """Read issues with labels, assignees, milestone, URL, and linked PRs."""
        data = self._run_json(
            [
                "gh",
                "issue",
                "list",
                "--repo",
                self.repo,
                "--state",
                state,
                "--limit",
                str(limit),
                "--json",
                "number,title,state,labels,assignees,milestone,url,body,closedByPullRequestsReferences",
            ]
        )
        return [_issue_from_gh(item) for item in data]

    def comment(self, number: int, body: str) -> None:
        """Comment on an issue with evidence or blocker details."""
        self._run(["gh", "issue", "comment", str(number), "--repo", self.repo, "--body", body])

    def close(self, number: int, *, comment: str | None = None) -> None:
        """Close an issue, optionally with a final evidence comment."""
        cmd = ["gh", "issue", "close", str(number), "--repo", self.repo]
        if comment:
            cmd.extend(["--comment", comment])
        self._run(cmd)

    def create(self, title: str, body: str, *, labels: list[str] | None = None) -> str:
        """Create a GitHub Issue and return the created URL/stdout."""
        cmd = ["gh", "issue", "create", "--repo", self.repo, "--title", title, "--body", body]
        for label in labels or []:
            cmd.extend(["--label", label])
        result = self._run(cmd)
        return result.stdout.strip()

    def _run_json(self, cmd: list[str]) -> list[dict]:
        result = self._run(cmd)
        try:
            data = json.loads(result.stdout or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"GitHub CLI returned invalid JSON for {' '.join(cmd)}") from exc
        if not isinstance(data, list):
            raise RuntimeError(f"GitHub CLI returned non-list JSON for {' '.join(cmd)}")
        return data

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        result = self.runner(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        if self.rate_limit_seconds:
            self.sleep(self.rate_limit_seconds)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"GitHub CLI failed: {' '.join(cmd)}")
        return result


def _issue_from_gh(data: dict) -> GitHubIssue:
    labels = [item.get("name", "") for item in data.get("labels") or [] if item.get("name")]
    assignees = [
        item.get("login") or item.get("name") or ""
        for item in data.get("assignees") or []
        if item.get("login") or item.get("name")
    ]
    milestone = data.get("milestone") or {}
    linked = [
        item.get("url", "")
        for item in data.get("closedByPullRequestsReferences") or []
        if item.get("url")
    ]
    return GitHubIssue(
        number=int(data["number"]),
        title=data.get("title", ""),
        state=data.get("state", "open").lower(),
        labels=labels,
        assignees=assignees,
        milestone=milestone.get("title") if isinstance(milestone, dict) else None,
        url=data.get("url"),
        body=data.get("body"),
        linked_prs=linked,
    )
