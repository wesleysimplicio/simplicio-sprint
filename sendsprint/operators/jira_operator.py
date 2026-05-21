"""JiraOperator - reads a sprint from Jira via MCP, REST API, or Playwright."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from importlib import import_module
from pathlib import Path
from typing import Any

import httpx

from sendsprint.browser_agents import (
    BrowserAgentCaptureError,
    capture_sprint_with_browser_agents,
)
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
        self._work_dir = Path(self._kwargs.get("work_dir") or Path.cwd())
        self._profile_sprint_url = self._load_profile_sprint_url()

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

    def update_status(self, item_key: str, status: str, comment: str | None = None) -> None:
        """Best-effort Jira transition + comment callback for deploy events."""
        if not self._api_available():
            raise TransportUnavailable(
                "Jira API credentials missing (JIRA_BASE_URL/EMAIL/API_TOKEN)"
            )
        with httpx.Client(timeout=30.0, auth=(self.email, self.api_token)) as client:
            if comment:
                comment_resp = client.post(
                    f"{self.base_url}/rest/api/3/issue/{item_key}/comment",
                    json={"body": comment},
                )
                comment_resp.raise_for_status()

            transitions_resp = client.get(
                f"{self.base_url}/rest/api/3/issue/{item_key}/transitions"
            )
            transitions_resp.raise_for_status()
            transitions = transitions_resp.json().get("transitions", [])
            target = status.strip().lower()
            transition_id = None
            for transition in transitions:
                name = str(transition.get("name", "")).strip().lower()
                to_name = str((transition.get("to") or {}).get("name", "")).strip().lower()
                if target in {name, to_name}:
                    transition_id = transition.get("id")
                    break
            if transition_id is None:
                raise RuntimeError(f"jira transition '{status}' not available for {item_key}")

            transition_resp = client.post(
                f"{self.base_url}/rest/api/3/issue/{item_key}/transitions",
                json={"transition": {"id": transition_id}},
            )
            transition_resp.raise_for_status()

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
        sprint_url = self._resolve_sprint_url(kwargs.get("sprint_url"), sprint_id)
        last_error: Exception | None = None
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            last_error = exc
            items = []
        else:
            try:
                if not sprint_url:
                    raise TransportUnavailable(
                        "Jira sprint URL or base URL required for Playwright transport"
                    )
                items = self._scrape_items_via_playwright(sync_playwright, sprint_url)
            except Exception as exc:  # pragma: no cover - fallback is validated below
                last_error = exc
                items = []
        sprint_name = f"Sprint {sprint_id}"
        if not items:
            if not sprint_url:
                detail = str(last_error) if last_error else "no sprint URL available"
                raise TransportUnavailable(detail)
            try:
                payload, _ = capture_sprint_with_browser_agents(
                    source="jira",
                    sprint_url=sprint_url,
                    identifier=str(sprint_id),
                    working_dir=self._work_dir,
                )
            except BrowserAgentCaptureError as exc:
                detail = str(last_error) if last_error else "playwright capture failed"
                raise TransportUnavailable(
                    f"{detail}; browser-agent fallback failed: {exc}"
                ) from exc
            items = [self._browser_item_to_sprint_item(item) for item in payload.items]
            return Sprint(
                id=str(sprint_id),
                name=payload.sprint_name or sprint_name,
                state="active",
                goal=payload.sprint_goal,
                items=items,
                source="jira",
                transport="playwright",
            )
        return Sprint(
            id=str(sprint_id),
            name=sprint_name,
            state="active",
            items=items,
            source="jira",
            transport="playwright",
        )

    def _resolve_sprint_url(self, explicit: Any, sprint_id: Any) -> str | None:
        if explicit:
            return str(explicit).strip()
        if self._profile_sprint_url:
            return self._profile_sprint_url
        if self.base_url:
            return f"{self.base_url}/jira/software/projects/_/boards/_?sprint={sprint_id}"
        return None

    def _load_profile_sprint_url(self) -> str | None:
        try:
            from sendsprint import profile as _profile_mod

            profile = _profile_mod.load()
            return profile.jira.last_sprint_url
        except Exception:
            return None

    def _scrape_items_via_playwright(
        self, sync_playwright: Any, sprint_url: str
    ) -> list[SprintItem]:
        items: list[SprintItem] = []
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(self.cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            page.goto(sprint_url)
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
                        source_url=f"{self.base_url}/browse/{key}" if self.base_url else sprint_url,
                    )
                )
            page.close()
        return items

    def _browser_item_to_sprint_item(self, item: Any) -> SprintItem:
        item_type = (
            item.type
            if item.type in {"Story", "Task", "Subtask", "Bug", "Epic", "Feature", "Issue"}
            else "Issue"
        )
        return SprintItem(
            id=item.key,
            key=item.key,
            type=item_type,
            title=item.title,
            description=item.description,
            status=item.status or "unknown",
            assignee=item.assignee,
            story_points=item.story_points,
            source_url=item.source_url,
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
