"""Sprints endpoints: list active sprints + fetch a sprint's items."""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from sendsprint import credentials
from sendsprint import profile as profile_mod
from sendsprint.api.schemas import (
    ImportSprintsRequest,
    ImportSprintsResponse,
    Provider,
    SprintDetail,
    SprintItemSummary,
    SprintSummary,
)
from sendsprint.operators import AzureDevopsOperator, JiraOperator

router = APIRouter(prefix="/sprints", tags=["sprints"])

# Background imports: job_id → state
_imports: dict[str, dict[str, Any]] = {}


@router.get("", response_model=list[SprintSummary])
def list_sprints(
    provider: Provider = Query(...),  # noqa: B008 — FastAPI dependency idiom
    board_id: str | None = Query(None, description="Jira board id"),  # noqa: B008
    team_path: str | None = Query(None, description="ADO team iteration path"),  # noqa: B008
) -> list[SprintSummary]:
    if provider == "jira":
        return _list_jira_active(board_id)
    return _list_ado_active(team_path)


@router.get("/{sprint_id}", response_model=SprintDetail)
def get_sprint(
    sprint_id: str,
    provider: Provider = Query(...),  # noqa: B008 — FastAPI dependency idiom
    scope: str | None = Query(None, description="'mine' filters to current user"),  # noqa: B008
) -> SprintDetail:
    op: Any
    if provider == "jira":
        op = JiraOperator(transport="auto")
    else:
        op = AzureDevopsOperator(transport="auto")
    try:
        if provider == "jira":
            sprint = op.read_sprint(sprint_id=sprint_id)
        else:
            sprint = op.read_sprint(iteration_path=sprint_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"failed to read sprint: {exc}") from exc

    items = sprint.items
    if scope == "mine":
        from sendsprint.scope import build_scope

        s = build_scope(mode="mine")
        if s is not None:
            items = [i for i in items if s.matches(i)]

    return SprintDetail(
        sprint=SprintSummary(
            id=sprint.id,
            name=sprint.name,
            state=sprint.state,
            provider=provider,
            start_date=sprint.start_date.isoformat() if sprint.start_date else None,
            end_date=sprint.end_date.isoformat() if sprint.end_date else None,
            item_count=len(items),
            goal=sprint.goal,
        ),
        items=[
            SprintItemSummary(
                id=i.id,
                key=i.key,
                type=i.type,
                title=i.title,
                status=i.status,
                assignee=i.assignee,
                assignee_email=i.assignee_email,
                story_points=i.story_points,
            )
            for i in items
        ],
    )


@router.post("/import", response_model=ImportSprintsResponse)
def import_sprints(req: ImportSprintsRequest, bg: BackgroundTasks) -> ImportSprintsResponse:
    """Kick off a background import of every sprint item (cached locally)."""
    job_id = uuid.uuid4().hex[:10]
    _imports[job_id] = {"state": "running", "fetched": 0, "total": None}
    bg.add_task(_import_worker, job_id, req)
    return ImportSprintsResponse(job_id=job_id)


@router.get("/import/{job_id}", response_model=dict)
def import_status(job_id: str) -> dict:
    job = _imports.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job


def _import_worker(job_id: str, req: ImportSprintsRequest) -> None:
    try:
        sprints = (
            _list_jira_active(req.board_id)
            if req.provider == "jira"
            else _list_ado_active(req.team_path)
        )
        _imports[job_id]["total"] = len(sprints)
        op: Any = (
            JiraOperator(transport="auto")
            if req.provider == "jira"
            else AzureDevopsOperator(transport="auto")
        )
        for s in sprints:
            try:
                if req.provider == "jira":
                    op.read_sprint(sprint_id=s.id)
                else:
                    op.read_sprint(iteration_path=s.id)
                _imports[job_id]["fetched"] += 1
            except Exception:
                continue
        _imports[job_id]["state"] = "done"
    except Exception as exc:
        _imports[job_id]["state"] = "failed"
        _imports[job_id]["error"] = str(exc)


# ---------- internal helpers ----------


def _list_jira_active(board_id: str | None) -> list[SprintSummary]:
    base = os.getenv("JIRA_BASE_URL", "").rstrip("/")
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    if not (base and email and token):
        return _demo_sprints("jira")
    if not board_id:
        raise HTTPException(status_code=400, detail="board_id is required for jira")
    url = f"{base}/rest/agile/1.0/board/{board_id}/sprint?state=active"
    try:
        with httpx.Client(timeout=15.0, auth=(email, token)) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return _demo_sprints("jira")

    out: list[SprintSummary] = []
    for s in data.get("values", []):
        out.append(
            SprintSummary(
                id=str(s.get("id")),
                name=s.get("name", ""),
                state=s.get("state", "active"),
                provider="jira",
                start_date=s.get("startDate"),
                end_date=s.get("endDate"),
                goal=s.get("goal"),
            )
        )
    return out


def _list_ado_active(team_path: str | None) -> list[SprintSummary]:
    org, project, pat, resolved_team_path = _resolve_ado_context(team_path)
    if not (org and project and pat):
        return _demo_sprints("azuredevops")
    base = resolved_team_path or f"{org}/{project}"
    url = (
        f"https://dev.azure.com/{base}/_apis/work/teamsettings/iterations"
        "?$timeframe=current&api-version=7.1"
    )
    try:
        with httpx.Client(timeout=15.0, auth=("", pat)) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError:
        return _demo_sprints("azuredevops")

    out: list[SprintSummary] = []
    for s in data.get("value", []):
        attrs = s.get("attributes", {})
        sprint_id = s.get("path") or _infer_iteration_path(
            project, resolved_team_path, s.get("name")
        )
        out.append(
            SprintSummary(
                id=sprint_id or s.get("id", ""),
                name=s.get("name", ""),
                state="active",
                provider="azuredevops",
                start_date=attrs.get("startDate"),
                end_date=attrs.get("finishDate"),
            )
        )
    return out


def _resolve_ado_context(team_path: str | None) -> tuple[str, str, str, str | None]:
    profile = profile_mod.load()
    org = os.getenv("AZURE_DEVOPS_ORG", "") or (profile.azuredevops.organization or "")
    project = os.getenv("AZURE_DEVOPS_PROJECT", "") or (profile.azuredevops.project or "")
    pat = os.getenv("AZURE_DEVOPS_PAT", "")
    if not pat and org:
        pat = credentials.get_secret("azuredevops", org) or ""
    resolved_team_path = team_path
    if not resolved_team_path and profile.azuredevops.team:
        resolved_team_path = f"{org}/{project}/{profile.azuredevops.team}"
    elif not resolved_team_path and org and project:
        resolved_team_path = f"{org}/{project}"
    return org, project, pat, resolved_team_path


def _infer_iteration_path(
    project: str, team_path: str | None, sprint_name: str | None
) -> str | None:
    if not sprint_name:
        return None
    team = team_path.split("/")[-1] if team_path and "/" in team_path else None
    return "\\".join(part for part in (project, team, sprint_name) if part)


def _demo_sprints(provider: Provider) -> list[SprintSummary]:
    """Stub data so the web flow is always demoable, even without creds."""
    return [
        SprintSummary(
            id="42",
            name="Sprint 42 — Onboarding rework",
            state="active",
            provider=provider,
            start_date="2026-05-01T00:00:00Z",
            end_date="2026-05-15T00:00:00Z",
            item_count=12,
            goal="Reduzir fricção no signup",
        ),
        SprintSummary(
            id="43",
            name="Sprint 43 — Push notifications",
            state="active",
            provider=provider,
            start_date="2026-05-08T00:00:00Z",
            end_date="2026-05-22T00:00:00Z",
            item_count=8,
            goal="Lançar push notifications",
        ),
    ]
