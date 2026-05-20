"""Deeper GitHub integration: duplicate detection, progress comments, CI monitoring, review reading.

All classes accept an injectable ``httpx.Client`` so tests run without network.
Repo is always ``owner/repo`` slug.  Token comes from ``GITHUB_TOKEN`` env var
or the caller can pre-configure the client with auth headers.

See: https://github.com/wesleysimplicio/SendSprint/issues/100
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable

import httpx

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _default_headers(token: str | None = None) -> dict[str, str]:
    tok = token or os.getenv("GITHUB_TOKEN", "")
    headers: dict[str, str] = {"Accept": "application/vnd.github+json"}
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


def _get_json(
    client: httpx.Client,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> Any:
    resp = client.get(url, params=params)
    resp.raise_for_status()
    return resp.json()


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DuplicateResult:
    """Outcome of a duplicate/concurrent-work check."""

    duplicates: list[dict[str, Any]] = field(default_factory=list)
    concurrent_prs: list[dict[str, Any]] = field(default_factory=list)

    @property
    def has_duplicates(self) -> bool:
        return len(self.duplicates) > 0

    @property
    def has_concurrent_work(self) -> bool:
        return len(self.concurrent_prs) > 0


@dataclass(frozen=True)
class CIStatus:
    """Snapshot of CI check status for a ref."""

    state: str  # "success" | "failure" | "pending" | "error"
    checks: list[dict[str, Any]] = field(default_factory=list)
    total: int = 0
    passed: int = 0
    failed: int = 0
    pending: int = 0

    @property
    def is_green(self) -> bool:
        return self.state == "success"

    @property
    def is_red(self) -> bool:
        return self.state in ("failure", "error")


@dataclass(frozen=True)
class ReviewFeedback:
    """A single actionable review comment."""

    reviewer: str
    body: str
    path: str | None = None
    line: int | None = None
    state: str = "COMMENTED"  # APPROVED | CHANGES_REQUESTED | COMMENTED


# ---------------------------------------------------------------------------
# DuplicateDetector
# ---------------------------------------------------------------------------

class DuplicateDetector:
    """Check for duplicate issues, PRs, or concurrent work on the same topic."""

    def __init__(self, repo: str, *, client: httpx.Client | None = None, token: str | None = None) -> None:
        self.repo = repo
        self._client = client
        self._token = token

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(headers=_default_headers(self._token), timeout=15.0)

    def check_duplicate_issues(self, title: str, *, state: str = "open") -> list[dict[str, Any]]:
        """Search for issues with similar titles.  Returns list of matching issue dicts."""
        query = f"repo:{self.repo} is:issue is:{state} {title} in:title"
        client = self._get_client()
        try:
            data = _get_json(client, f"{API_BASE}/search/issues", params={"q": query, "per_page": 10})
            return data.get("items", [])
        finally:
            if self._client is None:
                client.close()

    def check_duplicate_prs(self, title: str, *, state: str = "open") -> list[dict[str, Any]]:
        """Search for PRs with similar titles."""
        query = f"repo:{self.repo} is:pr is:{state} {title} in:title"
        client = self._get_client()
        try:
            data = _get_json(client, f"{API_BASE}/search/issues", params={"q": query, "per_page": 10})
            return data.get("items", [])
        finally:
            if self._client is None:
                client.close()

    def check_concurrent_work(self, branch: str) -> DuplicateResult:
        """Look for open PRs targeting the same branch or with similar names."""
        client = self._get_client()
        try:
            prs = _get_json(client, f"{API_BASE}/repos/{self.repo}/pulls", params={"state": "open", "per_page": 50})
            concurrent = [
                pr for pr in prs
                if pr.get("head", {}).get("ref") == branch
            ]
            return DuplicateResult(concurrent_prs=concurrent)
        finally:
            if self._client is None:
                client.close()


# ---------------------------------------------------------------------------
# ProgressReporter
# ---------------------------------------------------------------------------

class ProgressReporter:
    """Post progress comments with evidence to GitHub issues/PRs."""

    def __init__(self, repo: str, *, client: httpx.Client | None = None, token: str | None = None) -> None:
        self.repo = repo
        self._client = client
        self._token = token

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(headers=_default_headers(self._token), timeout=15.0)

    def post_progress_comment(self, issue_number: int, body: str) -> dict[str, Any]:
        """Post a comment on an issue or PR."""
        client = self._get_client()
        try:
            url = f"{API_BASE}/repos/{self.repo}/issues/{issue_number}/comments"
            resp = client.post(url, json={"body": body})
            resp.raise_for_status()
            return resp.json()
        finally:
            if self._client is None:
                client.close()

    def attach_evidence_summary(
        self,
        issue_number: int,
        *,
        steps_completed: list[str] | None = None,
        artifacts: list[str] | None = None,
        status: str = "in_progress",
    ) -> dict[str, Any]:
        """Post a structured evidence summary as a comment."""
        lines = [f"## SendSprint Progress ({status})", ""]
        if steps_completed:
            lines.append("### Steps completed")
            for step in steps_completed:
                lines.append(f"- [x] {step}")
            lines.append("")
        if artifacts:
            lines.append("### Artifacts")
            for art in artifacts:
                lines.append(f"- {art}")
            lines.append("")
        body = "\n".join(lines)
        return self.post_progress_comment(issue_number, body)


# ---------------------------------------------------------------------------
# CIMonitor
# ---------------------------------------------------------------------------

class CIMonitor:
    """Monitor CI check status for a given ref (branch or SHA)."""

    def __init__(
        self,
        repo: str,
        *,
        client: httpx.Client | None = None,
        token: str | None = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self.repo = repo
        self._client = client
        self._token = token
        self._sleep = sleep_fn

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(headers=_default_headers(self._token), timeout=15.0)

    def check_ci_status(self, ref: str) -> CIStatus:
        """Get the combined CI status for a ref."""
        client = self._get_client()
        try:
            data = _get_json(client, f"{API_BASE}/repos/{self.repo}/commits/{ref}/status")
            statuses = data.get("statuses", [])
            total = len(statuses)
            passed = sum(1 for s in statuses if s.get("state") == "success")
            failed = sum(1 for s in statuses if s.get("state") in ("failure", "error"))
            pending = sum(1 for s in statuses if s.get("state") == "pending")
            return CIStatus(
                state=data.get("state", "pending"),
                checks=statuses,
                total=total,
                passed=passed,
                failed=failed,
                pending=pending,
            )
        finally:
            if self._client is None:
                client.close()

    def wait_for_ci(
        self,
        ref: str,
        *,
        timeout_s: float = 600,
        poll_interval_s: float = 30,
    ) -> CIStatus:
        """Poll CI status until it completes or times out."""
        deadline = time.monotonic() + timeout_s
        while True:
            status = self.check_ci_status(ref)
            if status.state != "pending":
                return status
            if time.monotonic() >= deadline:
                return status
            self._sleep(poll_interval_s)


# ---------------------------------------------------------------------------
# ReviewReader
# ---------------------------------------------------------------------------

class ReviewReader:
    """Read PR review comments and extract actionable feedback."""

    def __init__(self, repo: str, *, client: httpx.Client | None = None, token: str | None = None) -> None:
        self.repo = repo
        self._client = client
        self._token = token

    def _get_client(self) -> httpx.Client:
        if self._client is not None:
            return self._client
        return httpx.Client(headers=_default_headers(self._token), timeout=15.0)

    def read_reviews(self, pr_number: int) -> list[dict[str, Any]]:
        """Fetch all reviews for a PR."""
        client = self._get_client()
        try:
            return _get_json(client, f"{API_BASE}/repos/{self.repo}/pulls/{pr_number}/reviews")
        finally:
            if self._client is None:
                client.close()

    def read_review_comments(self, pr_number: int) -> list[dict[str, Any]]:
        """Fetch all inline review comments for a PR."""
        client = self._get_client()
        try:
            return _get_json(client, f"{API_BASE}/repos/{self.repo}/pulls/{pr_number}/comments")
        finally:
            if self._client is None:
                client.close()

    def extract_actionable_feedback(self, pr_number: int) -> list[ReviewFeedback]:
        """Read reviews + inline comments and return actionable items.

        Actionable = review with CHANGES_REQUESTED or any inline comment body.
        """
        feedback: list[ReviewFeedback] = []

        # Top-level reviews requesting changes
        reviews = self.read_reviews(pr_number)
        for review in reviews:
            state = review.get("state", "")
            body = (review.get("body") or "").strip()
            if state == "CHANGES_REQUESTED" and body:
                feedback.append(
                    ReviewFeedback(
                        reviewer=review.get("user", {}).get("login", "unknown"),
                        body=body,
                        state=state,
                    )
                )

        # Inline comments
        comments = self.read_review_comments(pr_number)
        for comment in comments:
            body = (comment.get("body") or "").strip()
            if body:
                feedback.append(
                    ReviewFeedback(
                        reviewer=comment.get("user", {}).get("login", "unknown"),
                        body=body,
                        path=comment.get("path"),
                        line=comment.get("line") or comment.get("original_line"),
                        state="COMMENTED",
                    )
                )

        return feedback
