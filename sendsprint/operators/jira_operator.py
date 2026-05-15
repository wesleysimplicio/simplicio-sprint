"""JiraOperator - reads a sprint from Jira via MCP, REST API, or Playwright."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from importlib import import_module
from typing import Any

import httpx

from sendsprint.models import Comment, Link, Sprint, SprintItem
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)

JIRA_TYPE_MAP = {
    "story": "Story",
    "task": "Task",
    "sub-task": "Subtask",
    "subtask": "Subtask",
    "bug": "Bug",
    "epic": "Epic",
    "feature": "Feature",
    "issue": "Issue",
}


class JiraOperator(BaseOperator):
    """Reads a Jira sprint and returns a Sprint with all its items.

    Transports:
      - mcp: uses the Atlassian MCP server (when MCP_JIRA_AVAILABLE=1).
      - api: Jira Cloud REST API v3 + Agile API (default for credentials in env).
      - playwright: connects to an existing Chrome over CDP and scrapes the sprint board.
    """

    source = "jira"

    def __init__(
        self,
        base_url: str | None = None,
        email: str | None = None,
        api_token: str | None = None,
        transport: Transport = "auto",
        cdp_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        resolved_base = (base_url or os.getenv("JIRA_BASE_URL") or "").rstrip("/")
        resolved_email = email or os.getenv("JIRA_EMAIL") or ""
        resolved_token = api_token or os.getenv("JIRA_API_TOKEN") or ""
        if not resolved_base or not resolved_email:
            try:
                from sendsprint import profile as _profile_mod

                _p = _profile_mod.load()
                resolved_base = resolved_base or (_p.jira.base_url or "").rstrip("/")
                resolved_email = resolved_email or (_p.jira.email or "")
            except Exception:  # pragma: no cover — defensive: no profile, no yaml
                pass
        if not resolved_token and resolved_email:
            try:
                from sendsprint import credentials as _credentials

                resolved_token = _credentials.get_secret("jira", resolved_email) or ""
            except Exception:  # pragma: no cover — keyring unavailable
                pass
        self.base_url: str = resolved_base or ""
        self.email: str = resolved_email or ""
        self.api_token: str = resolved_token or ""
        self.cdp_url: str = cdp_url or os.getenv("PLAYWRIGHT_CDP_URL") or "http://127.0.0.1:9222"

    def _api_available(self) -> bool:
        return bool(self.base_url and self.email and self.api_token)

    def current_user(self) -> dict[str, str | None]:
        """Resolve the current Jira user via /rest/api/3/myself.

        Returns ``{accountId, emailAddress, displayName}`` (any may be None).
        Falls back to env defaults when the API is unreachable.
        """
        fallback = {
            "accountId": None,
            "emailAddress": self.email or None,
            "displayName": None,
        }
        if not self._api_available():
            return fallback
        try:
            with httpx.Client(timeout=15.0, auth=(self.email, self.api_token)) as client:
                resp = client.get(f"{self.base_url}/rest/api/3/myself")
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError):
            return fallback
        return {
            "accountId": data.get("accountId"),
            "emailAddress": data.get("emailAddress") or self.email or None,
            "displayName": data.get("displayName"),
        }

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        sprint_id = kwargs.get("sprint_id")
        if sprint_id is None:
            raise ValueError("sprint_id is required")
        try:
            bridge = import_module("sendsprint.operators._mcp_bridge")
        except ImportError as exc:
            raise TransportUnavailable("MCP bridge module missing") from exc
        return bridge.call_jira_mcp(sprint_id=sprint_id)

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        sprint_id = kwargs.get("sprint_id")
        if sprint_id is None:
            raise ValueError("sprint_id is required")
        if not self._api_available():
            raise TransportUnavailable(
                "Jira API credentials missing (JIRA_BASE_URL/EMAIL/API_TOKEN)"
            )
        auth = (self.email, self.api_token)
        sprint_url = f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}"
        with httpx.Client(timeout=30.0, auth=auth) as client:
            sprint_resp = client.get(sprint_url)
            sprint_resp.raise_for_status()
            sprint_data = sprint_resp.json()
            issues: list[dict[str, Any]] = []
            start_at = 0
            while True:
                page = client.get(
                    f"{self.base_url}/rest/agile/1.0/sprint/{sprint_id}/issue",
                    params={
                        "startAt": start_at,
                        "maxResults": 50,
                        "fields": "*all",
                        "expand": "renderedFields",
                    },
                )
                page.raise_for_status()
                payload = page.json()
                batch = payload.get("issues", [])
                issues.extend(batch)
                if start_at + len(batch) >= payload.get("total", 0) or not batch:
                    break
                start_at += len(batch)
        return self._sprint_from_jira_issues(sprint_data, issues, transport="api")

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        sprint_id = kwargs.get("sprint_id")
        if sprint_id is None:
            raise ValueError("sprint_id is required")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise TransportUnavailable(
                "playwright not installed: pip install playwright && playwright install chromium"
            ) from exc
        if not self.base_url:
            raise TransportUnavailable("JIRA_BASE_URL required for Playwright transport")
        items: list[SprintItem] = []
        sprint_name = f"Sprint {sprint_id}"
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(self.cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            page.goto(f"{self.base_url}/jira/software/projects/_/boards/_?sprint={sprint_id}")
            page.wait_for_load_state("networkidle", timeout=20000)
            cards = page.locator("[data-testid='platform-board-kit.ui.card.card']").all()
            for card in cards:
                key_el = card.locator("[data-testid='platform-card.common.ui.key.key']").first
                title_el = card.locator(
                    "[data-testid='platform-card.ui.card.focus-container']"
                ).first
                key = key_el.text_content() if key_el else ""
                title = title_el.text_content() if title_el else ""
                if not key:
                    continue
                items.append(
                    SprintItem(
                        id=key,
                        key=key,
                        type="Story",
                        title=(title or key).strip(),
                        status="unknown",
                        source_url=f"{self.base_url}/browse/{key}",
                    )
                )
            page.close()
        return Sprint(
            id=str(sprint_id),
            name=sprint_name,
            state="active",
            items=items,
            source="jira",
            transport="playwright",
        )

    def _sprint_from_jira_issues(
        self,
        sprint_data: dict[str, Any],
        issues: list[dict[str, Any]],
        transport: str,
    ) -> Sprint:
        items = [self._issue_to_item(i) for i in issues]
        return Sprint(
            id=str(sprint_data.get("id", "")),
            name=sprint_data.get("name", ""),
            state=sprint_data.get("state", "active"),
            goal=sprint_data.get("goal"),
            start_date=_parse_dt(sprint_data.get("startDate")),
            end_date=_parse_dt(sprint_data.get("endDate")),
            items=items,
            source="jira",
            transport=transport,  # type: ignore[arg-type]
        )

    def _issue_to_item(self, issue: dict[str, Any]) -> SprintItem:
        fields = issue.get("fields", {})
        issue_type_raw = (fields.get("issuetype") or {}).get("name", "Issue").lower()
        item_type = JIRA_TYPE_MAP.get(issue_type_raw, "Issue")
        assignee_obj = fields.get("assignee") or {}
        assignee = assignee_obj.get("displayName")
        assignee_email = assignee_obj.get("emailAddress")
        assignee_account_id = assignee_obj.get("accountId")
        parent = (fields.get("parent") or {}).get("key")
        story_points = fields.get("customfield_10016") or fields.get("customfield_10026")
        labels = fields.get("labels") or []
        comments = []
        for c in (fields.get("comment") or {}).get("comments", []):
            comments.append(
                Comment(
                    author=(c.get("author") or {}).get("displayName", "unknown"),
                    body=_extract_text(c.get("body")) or "",
                    created_at=_parse_dt(c.get("created")) or datetime.utcnow(),
                )
            )
        links: list[Link] = []
        for il in fields.get("issuelinks", []) or []:
            link_type = (il.get("type") or {}).get("name", "relates to")
            target = il.get("outwardIssue") or il.get("inwardIssue") or {}
            if target.get("key"):
                links.append(Link(type=link_type, target_key=target["key"]))
        return SprintItem(
            id=issue.get("id", ""),
            key=issue.get("key", ""),
            type=item_type,  # type: ignore[arg-type]
            title=fields.get("summary", ""),
            description=_extract_text(fields.get("description")),
            status=(fields.get("status") or {}).get("name", "unknown"),
            assignee=assignee,
            assignee_email=assignee_email,
            assignee_account_id=assignee_account_id,
            story_points=float(story_points) if story_points is not None else None,
            parent_key=parent,
            labels=list(labels),
            links=links,
            comments=comments,
            acceptance_criteria=_extract_text(fields.get("customfield_10100")),
            created_at=_parse_dt(fields.get("created")),
            updated_at=_parse_dt(fields.get("updated")),
            source_url=f"{self.base_url}/browse/{issue.get('key')}" if self.base_url else None,
        )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        if isinstance(value, datetime):
            return value
        text = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None


def _extract_text(value: Any) -> str | None:
    """Flattens Atlassian Document Format into plain text."""
    if value is None:
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        if "content" in value:
            return "\n".join(_extract_text(c) or "" for c in value["content"]).strip() or None
        if value.get("type") == "text":
            return value.get("text") or None
    if isinstance(value, list):
        return "\n".join(_extract_text(c) or "" for c in value).strip() or None
    return None
