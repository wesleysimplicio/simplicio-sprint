"""GitHubIssuesOperator - reads issues from a GitHub repo as a Sprint.

GitHub has no native "sprint"; a milestone is the closest equivalent, so this
operator treats ``sprint_id`` as a milestone (number or title). Issues in that
milestone become :class:`SprintItem` rows. With no milestone it reads open
issues directly, which pairs with ``--scope mine`` to "finish my cards".

Transport is REST API only (the GitHub MCP server, when present, is consumed by
the host assistant, not this operator).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx

from sendsprint.models import Comment, Sprint, SprintItem
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)

API_BASE = "https://api.github.com"


class GitHubIssuesOperator(BaseOperator):
    """Reads GitHub issues (optionally scoped to a milestone) as a Sprint."""

    source = "github"

    def __init__(
        self,
        repo: str | None = None,
        token: str | None = None,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.repo: str = (repo or os.getenv("GITHUB_REPO") or "").strip()
        self.token: str = (token or os.getenv("GITHUB_TOKEN") or "").strip()

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _api_available(self) -> bool:
        return bool(self.repo)

    def current_user(self) -> dict[str, str | None]:
        """Resolve the authenticated GitHub user via /user."""
        fallback: dict[str, str | None] = {"login": None, "email": None, "name": None}
        if not self.token:
            return fallback
        try:
            with httpx.Client(timeout=15.0, headers=self._headers()) as client:
                resp = client.get(f"{API_BASE}/user")
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError):
            return fallback
        return {
            "login": data.get("login"),
            "email": data.get("email"),
            "name": data.get("name"),
        }

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        from importlib import import_module

        bridge = import_module("sendsprint.operators._mcp_bridge")
        sprint_id = kwargs.get("sprint_id")
        payload = bridge.fetch("github", sprint_id=sprint_id, assignee=kwargs.get("assignee"))
        issues = [i for i in payload.get("issues", []) if "pull_request" not in i]
        return self._sprint_from_issues(sprint_id, issues, transport="mcp")

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable("GitHub repo missing (set GITHUB_REPO=owner/repo)")
        sprint_id = kwargs.get("sprint_id")
        assignee = kwargs.get("assignee")
        params: dict[str, Any] = {"state": "open", "per_page": 100}
        if sprint_id not in (None, "", "*"):
            params["milestone"] = str(sprint_id)
        if assignee:
            params["assignee"] = str(assignee)

        issues: list[dict[str, Any]] = []
        url: str | None = f"{API_BASE}/repos/{self.repo}/issues"
        with httpx.Client(timeout=30.0, headers=self._headers()) as client:
            while url:
                resp = client.get(url, params=params if url.endswith("/issues") else None)
                resp.raise_for_status()
                page = resp.json()
                # Pull requests come back from the issues endpoint too — drop them.
                issues.extend(i for i in page if "pull_request" not in i)
                url = _next_link(resp.headers.get("link"))
                params = {}

        return self._sprint_from_issues(sprint_id, issues, transport="api")

    def _sprint_from_issues(
        self, sprint_id: Any, issues: list[dict[str, Any]], *, transport: str
    ) -> Sprint:
        items = [self._issue_to_item(i) for i in issues]
        name = f"milestone {sprint_id}" if sprint_id not in (None, "", "*") else "open issues"
        return Sprint(
            id=str(sprint_id) if sprint_id not in (None, "") else self.repo,
            name=f"{self.repo} — {name}",
            state="active",
            items=items,
            source="github",  # type: ignore[arg-type]
            transport=transport,  # type: ignore[arg-type]
        )

    def update_status(self, item_key: str, status: str, comment: str | None = None) -> None:
        """Post a status comment and apply a label (issues have no native state)."""
        if not self._api_available():
            raise TransportUnavailable("GitHub repo missing (set GITHUB_REPO=owner/repo)")
        with httpx.Client(timeout=30.0, headers=self._headers()) as client:
            if comment:
                resp = client.post(
                    f"{API_BASE}/repos/{self.repo}/issues/{item_key}/comments",
                    json={"body": comment},
                )
                resp.raise_for_status()
            label_resp = client.post(
                f"{API_BASE}/repos/{self.repo}/issues/{item_key}/labels",
                json={"labels": [status]},
            )
            label_resp.raise_for_status()

    def _issue_to_item(self, issue: dict[str, Any]) -> SprintItem:
        assignee_obj = issue.get("assignee") or {}
        labels = [
            label_label
            for label in issue.get("labels", [])
            if (label_label := label.get("name") if isinstance(label, dict) else str(label))
        ]
        return SprintItem(
            id=str(issue.get("id", "")),
            key=str(issue.get("number", "")),
            type="Issue",
            title=issue.get("title", ""),
            description=issue.get("body"),
            status="open" if issue.get("state") == "open" else "closed",
            assignee=assignee_obj.get("login"),
            assignee_email=assignee_obj.get("email"),
            labels=labels,
            comments=_comments(issue),
            created_at=_parse_dt(issue.get("created_at")),
            updated_at=_parse_dt(issue.get("updated_at")),
            source_url=issue.get("html_url"),
        )


def _comments(issue: dict[str, Any]) -> list[Comment]:
    # The list endpoint does not embed comment bodies; left empty by design.
    return []


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _next_link(link_header: str | None) -> str | None:
    """Parse the RFC-5988 ``Link`` header for the ``rel="next"`` URL."""
    if not link_header:
        return None
    for part in link_header.split(","):
        section = part.split(";")
        if len(section) < 2:
            continue
        url = section[0].strip().strip("<>")
        if any('rel="next"' in s.strip() for s in section[1:]):
            return url
    return None
