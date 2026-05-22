"""GitHubOperator — reads a sprint (milestone) from GitHub Issues.

This is the only fully-wired operator in the new batch; it backs the
``--source=github`` flow end-to-end (REST v3 against the issues API). MCP
and Playwright transports stay scaffolded for parity with the other
operators (handled by their respective sub-issues).

A "sprint" here is a GitHub milestone. The operator lists every non-PR issue
inside the milestone, paginates through them, and maps each one to a
:class:`~sendsprint.models.SprintItem`. ``update_status`` flips the issue
``open``/``closed`` state and optionally posts a comment.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

import httpx

from sendsprint.models import ItemType, Sprint, SprintItem
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)

# Map a GitHub label (lowercase) onto the SprintItem type enum.
GITHUB_TYPE_MAP: dict[str, ItemType] = {
    "bug": "Bug",
    "task": "Task",
    "story": "Story",
    "user-story": "Story",
    "feature": "Feature",
    "enhancement": "Feature",
    "epic": "Epic",
    "subtask": "Subtask",
    "sub-task": "Subtask",
}

# Map a GitHub state onto a human-readable status string.
STATE_LABELS = {
    "open": "Open",
    "closed": "Closed",
}


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        logger.debug("github: unparseable datetime %r", value)
        return None


def _classify(labels: list[dict[str, Any]]) -> ItemType:
    for label in labels:
        name = (label.get("name") or "").strip().lower()
        if name in GITHUB_TYPE_MAP:
            return GITHUB_TYPE_MAP[name]
    return "Issue"


class GitHubOperator(BaseOperator):
    """Reads a GitHub milestone and returns a :class:`Sprint` of its issues.

    Transports:
      - mcp: GitHub MCP server (when ``MCP_GITHUB_AVAILABLE=1``).
      - api: GitHub REST v3 against ``GITHUB_BASE_URL`` (defaults to
        ``https://api.github.com``) with ``GITHUB_TOKEN``, ``GITHUB_OWNER``,
        and ``GITHUB_REPO``.
      - playwright: scrapes the milestone issue list via the shared CDP
        browser (not yet wired; tracked under GITHUB-INGEST).
    """

    source = "github"

    def __init__(
        self,
        token: str | None = None,
        owner: str | None = None,
        repo: str | None = None,
        milestone: int | str | None = None,
        base_url: str | None = None,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.token: str = token or os.getenv("GITHUB_TOKEN") or ""
        self.owner: str = owner or os.getenv("GITHUB_OWNER") or ""
        self.repo: str = repo or os.getenv("GITHUB_REPO") or ""
        ms = milestone if milestone is not None else os.getenv("GITHUB_MILESTONE")
        self.milestone: int | str | None = ms
        self.base_url: str = (
            base_url or os.getenv("GITHUB_BASE_URL") or "https://api.github.com"
        ).rstrip("/")

    def _api_available(self) -> bool:
        return bool(self.token and self.owner and self.repo)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SendSprint/0.22 (+https://github.com/wesleysimplicio/SendSprint)",
        }

    def _resolve_milestone_number(self, client: httpx.Client) -> int:
        """Return the numeric milestone id, resolving by title when needed."""
        ms = self.milestone
        if ms is None:
            raise TransportUnavailable(
                "github operator requires a milestone (number or title); "
                "set GITHUB_MILESTONE or pass milestone=..."
            )
        if isinstance(ms, int):
            return ms
        text = str(ms).strip()
        if text.isdigit():
            return int(text)
        # Title lookup: list milestones (open + closed) and match by name.
        for state in ("open", "closed"):
            resp = client.get(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/milestones",
                params={"state": state, "per_page": 100},
            )
            resp.raise_for_status()
            for entry in resp.json():
                if entry.get("title") == text:
                    return int(entry["number"])
        raise TransportUnavailable(f"github: milestone titled {text!r} not found")

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable(
                "GITHUB_TOKEN, GITHUB_OWNER, and GITHUB_REPO are required for the API transport"
            )
        with httpx.Client(timeout=30.0, headers=self._headers()) as client:
            milestone_number = self._resolve_milestone_number(client)
            milestone_resp = client.get(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/milestones/{milestone_number}"
            )
            milestone_resp.raise_for_status()
            milestone = milestone_resp.json()

            items: list[SprintItem] = []
            page = 1
            while True:
                resp = client.get(
                    f"{self.base_url}/repos/{self.owner}/{self.repo}/issues",
                    params={
                        "milestone": milestone_number,
                        "state": "all",
                        "per_page": 100,
                        "page": page,
                    },
                )
                resp.raise_for_status()
                batch = resp.json()
                if not batch:
                    break
                for issue in batch:
                    # /issues returns PRs too; skip them via the marker field.
                    if "pull_request" in issue:
                        continue
                    items.append(self._issue_to_item(issue))
                if "next" not in resp.headers.get("Link", ""):
                    break
                page += 1

        return Sprint(
            id=str(milestone.get("number") or milestone_number),
            name=milestone.get("title") or f"Milestone {milestone_number}",
            state="active" if milestone.get("state") == "open" else "closed",
            goal=milestone.get("description") or None,
            start_date=_parse_dt(milestone.get("created_at")),
            end_date=_parse_dt(milestone.get("due_on")),
            items=items,
            source="github",
            transport="api",
        )

    def _issue_to_item(self, issue: dict[str, Any]) -> SprintItem:
        labels = issue.get("labels") or []
        assignee = issue.get("assignee") or {}
        number = issue["number"]
        return SprintItem(
            id=str(issue["id"]),
            key=f"{self.owner}/{self.repo}#{number}",
            type=_classify(labels),
            title=issue.get("title") or f"Issue #{number}",
            description=issue.get("body"),
            status=STATE_LABELS.get(issue.get("state", ""), issue.get("state", "open")),
            assignee=assignee.get("login"),
            assignee_email=assignee.get("email"),
            labels=[label.get("name", "") for label in labels if label.get("name")],
            created_at=_parse_dt(issue.get("created_at")),
            updated_at=_parse_dt(issue.get("updated_at")),
            source_url=issue.get("html_url"),
        )

    def update_status(self, item_key: str, status: str, comment: str | None = None) -> None:
        """Flip the issue state (open/closed) and optionally post a comment.

        ``item_key`` is ``owner/repo#number`` (as emitted by :meth:`_issue_to_item`)
        or just the bare issue number when the operator already knows the repo.
        """
        if not self._api_available():
            raise TransportUnavailable(
                "GITHUB_TOKEN / OWNER / REPO are required for status updates"
            )
        number = self._extract_issue_number(item_key)
        target_state = self._status_to_state(status)
        with httpx.Client(timeout=30.0, headers=self._headers()) as client:
            patch = client.patch(
                f"{self.base_url}/repos/{self.owner}/{self.repo}/issues/{number}",
                json={"state": target_state},
            )
            patch.raise_for_status()
            if comment:
                comment_resp = client.post(
                    f"{self.base_url}/repos/{self.owner}/{self.repo}/issues/{number}/comments",
                    json={"body": comment},
                )
                comment_resp.raise_for_status()

    @staticmethod
    def _extract_issue_number(item_key: str) -> int:
        if "#" in item_key:
            _, _, num = item_key.rpartition("#")
            return int(num)
        return int(item_key)

    @staticmethod
    def _status_to_state(status: str) -> str:
        normalized = status.strip().lower()
        if normalized in {"done", "closed", "complete", "resolved", "merged"}:
            return "closed"
        return "open"

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "github MCP transport is not yet wired (GITHUB-INGEST sub-issue)"
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "github Playwright transport is not yet wired (GITHUB-INGEST sub-issue)"
        )
