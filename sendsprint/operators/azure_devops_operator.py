"""AzureDevopsOperator - reads work items from an Azure DevOps iteration."""

from __future__ import annotations

import base64
import logging
import os
from datetime import datetime
from importlib import import_module
from typing import Any

import httpx

from sendsprint.models import Sprint, SprintItem
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)

ADO_TYPE_MAP = {
    "user story": "Story",
    "product backlog item": "Story",
    "task": "Task",
    "bug": "Bug",
    "feature": "Feature",
    "epic": "Epic",
    "issue": "Issue",
}


class AzureDevopsOperator(BaseOperator):
    """Reads an Azure DevOps iteration (sprint) via MCP, REST API, or Playwright.

    Identifies the iteration by its ``IterationPath`` (e.g. ``MyTeam\\Sprint 12``).
    """

    source = "azuredevops"

    def __init__(
        self,
        organization: str | None = None,
        project: str | None = None,
        team: str | None = None,
        pat: str | None = None,
        transport: Transport = "auto",
        cdp_url: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        resolved_org = organization or os.getenv("AZURE_DEVOPS_ORG") or ""
        resolved_project = project or os.getenv("AZURE_DEVOPS_PROJECT") or ""
        resolved_team = team or os.getenv("AZURE_DEVOPS_TEAM") or ""
        resolved_pat = pat or os.getenv("AZURE_DEVOPS_PAT") or ""
        if not resolved_org or not resolved_project:
            try:
                from sendsprint import profile as _profile_mod

                _p = _profile_mod.load()
                resolved_org = resolved_org or (_p.azuredevops.organization or "")
                resolved_project = resolved_project or (_p.azuredevops.project or "")
            except Exception:  # pragma: no cover — defensive: no profile, no yaml
                pass
        if not resolved_pat and resolved_org:
            try:
                from sendsprint import credentials as _credentials

                resolved_pat = _credentials.get_secret("azuredevops", resolved_org) or ""
            except Exception:  # pragma: no cover — keyring unavailable
                pass
        self.organization: str = resolved_org or ""
        self.project: str = resolved_project or ""
        self.team: str = resolved_team or ""
        self.pat: str = resolved_pat or ""
        self.cdp_url: str = cdp_url or os.getenv("PLAYWRIGHT_CDP_URL") or "http://127.0.0.1:9222"

    def _api_available(self) -> bool:
        return bool(self.organization and self.project and self.pat)

    def current_user(self) -> dict[str, str | None]:
        """Resolve current ADO user via /_apis/connectionData.

        Returns ``{descriptor, emailAddress, displayName}`` (any may be None).
        """
        fallback: dict[str, str | None] = {
            "descriptor": None,
            "emailAddress": None,
            "displayName": None,
        }
        if not self._api_available():
            return fallback
        token = base64.b64encode(f":{self.pat}".encode()).decode()
        headers = {"Authorization": f"Basic {token}"}
        try:
            with httpx.Client(timeout=15.0, headers=headers) as client:
                resp = client.get(f"https://dev.azure.com/{self.organization}/_apis/connectionData")
                resp.raise_for_status()
                data = resp.json()
        except (httpx.HTTPError, ValueError):
            return fallback
        auth_user = data.get("authenticatedUser") or {}
        return {
            "descriptor": auth_user.get("descriptor"),
            "emailAddress": (auth_user.get("properties") or {}).get("Account", {}).get("$value"),
            "displayName": auth_user.get("providerDisplayName"),
        }

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        iteration_path = kwargs.get("iteration_path")
        if iteration_path is None:
            raise ValueError("iteration_path is required")
        try:
            bridge = import_module("sendsprint.operators._mcp_bridge")
        except ImportError as exc:
            raise TransportUnavailable("MCP bridge module missing") from exc
        return bridge.call_ado_mcp(iteration_path=iteration_path)

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        iteration_path = kwargs.get("iteration_path")
        if iteration_path is None:
            raise ValueError("iteration_path is required")
        if not self._api_available():
            raise TransportUnavailable("Azure DevOps credentials missing (ORG/PROJECT/PAT)")
        token = base64.b64encode(f":{self.pat}".encode()).decode()
        headers = {"Authorization": f"Basic {token}", "Content-Type": "application/json"}
        base = f"https://dev.azure.com/{self.organization}/{self.project}"
        wiql = {
            "query": (
                f"SELECT [System.Id] FROM WorkItems "
                f"WHERE [System.IterationPath] = '{iteration_path}' "
                f"AND [System.TeamProject] = '{self.project}'"
            )
        }
        with httpx.Client(timeout=30.0, headers=headers) as client:
            wiql_resp = client.post(
                f"{base}/_apis/wit/wiql?api-version=7.1",
                json=wiql,
            )
            wiql_resp.raise_for_status()
            ids = [w["id"] for w in wiql_resp.json().get("workItems", [])]
            items: list[SprintItem] = []
            for chunk in _chunked(ids, 200):
                if not chunk:
                    continue
                ids_param = ",".join(str(i) for i in chunk)
                detail = client.get(
                    f"{base}/_apis/wit/workitems",
                    params={
                        "ids": ids_param,
                        "$expand": "all",
                        "api-version": "7.1",
                    },
                )
                detail.raise_for_status()
                for wi in detail.json().get("value", []):
                    items.append(self._workitem_to_item(wi, base))
        return Sprint(
            id=iteration_path,
            name=iteration_path.split("\\")[-1],
            state="active",
            items=items,
            source="azuredevops",
            transport="api",
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        iteration_path = kwargs.get("iteration_path")
        if iteration_path is None:
            raise ValueError("iteration_path is required")
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise TransportUnavailable("playwright not installed") from exc
        if not (self.organization and self.project):
            raise TransportUnavailable("ORG and PROJECT required for Playwright transport")
        url = (
            f"https://dev.azure.com/{self.organization}/{self.project}/_sprints/backlog/"
            f"{self.team or self.project}"
        )
        items: list[SprintItem] = []
        with sync_playwright() as pw:
            browser = pw.chromium.connect_over_cdp(self.cdp_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context()
            page = context.new_page()
            page.goto(url)
            page.wait_for_load_state("networkidle", timeout=20000)
            rows = page.locator("[role='row']").all()
            for row in rows:
                title = row.locator("[class*='title']").first
                if not title:
                    continue
                text = title.text_content() or ""
                if not text.strip():
                    continue
                items.append(
                    SprintItem(
                        id=text.strip(),
                        key=text.strip(),
                        type="Story",
                        title=text.strip(),
                        status="unknown",
                    )
                )
            page.close()
        return Sprint(
            id=iteration_path,
            name=iteration_path.split("\\")[-1],
            state="active",
            items=items,
            source="azuredevops",
            transport="playwright",
        )

    def _workitem_to_item(self, wi: dict[str, Any], base: str) -> SprintItem:
        fields = wi.get("fields", {})
        wi_type = fields.get("System.WorkItemType", "Issue").lower()
        item_type = ADO_TYPE_MAP.get(wi_type, "Issue")
        assigned_raw = fields.get("System.AssignedTo")
        if isinstance(assigned_raw, dict):
            assignee = assigned_raw.get("displayName")
            assignee_email = assigned_raw.get("uniqueName")
            assignee_descriptor = assigned_raw.get("descriptor")
        else:
            assignee = assigned_raw
            assignee_email = None
            assignee_descriptor = None
        return SprintItem(
            id=str(wi.get("id", "")),
            key=str(wi.get("id", "")),
            type=item_type,  # type: ignore[arg-type]
            title=fields.get("System.Title", ""),
            description=_strip_html(fields.get("System.Description")),
            status=fields.get("System.State", "unknown"),
            assignee=assignee,
            assignee_email=assignee_email,
            assignee_descriptor=assignee_descriptor,
            story_points=fields.get("Microsoft.VSTS.Scheduling.StoryPoints"),
            parent_key=str(fields.get("System.Parent")) if fields.get("System.Parent") else None,
            labels=(
                (fields.get("System.Tags", "") or "").split("; ")
                if fields.get("System.Tags")
                else []
            ),
            acceptance_criteria=_strip_html(fields.get("Microsoft.VSTS.Common.AcceptanceCriteria")),
            created_at=_parse_dt(fields.get("System.CreatedDate")),
            updated_at=_parse_dt(fields.get("System.ChangedDate")),
            source_url=f"{base}/_workitems/edit/{wi.get('id')}",
        )


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _strip_html(value: Any) -> str | None:
    if not value:
        return None
    import re

    text = re.sub(r"<[^>]+>", " ", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _chunked(seq: list[Any], n: int) -> list[list[Any]]:
    return [seq[i : i + n] for i in range(0, len(seq), n)]
