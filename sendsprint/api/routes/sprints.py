"""Sprints endpoints: list active sprints + fetch backlog-enriched sprint items."""

from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from sendsprint import credentials
from sendsprint import profile as profile_mod
from sendsprint.api.backlog_state import BacklogCardState, BacklogStateStore
from sendsprint.api.schemas import (
    ArchiveSprintItemRequest,
    ImportSprintsRequest,
    ImportSprintsResponse,
    MoveSprintItemRequest,
    Provider,
    SprintDetail,
    SprintItemSummary,
    SprintSummary,
)
from sendsprint.operators import AzureDevopsOperator, JiraOperator
from sendsprint.scope import build_scope

router = APIRouter(prefix="/sprints", tags=["sprints"])
_backlog_store = BacklogStateStore()
_BOARD_STATUS_LABELS = {
    "backlog": "Backlog",
    "planning": "Planning",
    "programming": "Programming",
    "testing": "Testing",
    "review": "Review Humana",
    "awaiting_deploy": "Awaiting Deploy",
    "blocked": "Blocked",
}

# Background imports: job_id -> state
_imports: dict[str, dict[str, Any]] = {}


@router.get("", response_model=list[SprintSummary])
def list_sprints(
    provider: Provider = Query(...),  # noqa: B008
    board_id: str | None = Query(None, description="Jira board id"),  # noqa: B008
    team_path: str | None = Query(None, description="ADO team iteration path"),  # noqa: B008
) -> list[SprintSummary]:
    if provider == "jira":
        return _list_jira_active(board_id)
    return _list_ado_active(team_path)


@router.get("/{sprint_id}", response_model=SprintDetail)
def get_sprint(
    sprint_id: str,
    provider: Provider = Query(...),  # noqa: B008
    scope: str | None = Query(None, description="'mine' filters to current user"),  # noqa: B008
    user_email: str | None = Query(None, description="Optional app user email filter"),  # noqa: B008
    include_archived: bool = Query(False, description="Include archived cards"),  # noqa: B008
) -> SprintDetail:
    sprint = _read_sprint(provider, sprint_id)
    items = _dedupe_sprint_items(list(sprint.items))

    if scope == "mine":
        scope_email = (user_email or _default_scope_email(provider)).strip().lower()
        if scope_email:
            identity_scope = build_scope(mode="mine", user_email=scope_email, allowed_statuses=[])
            items = [item for item in items if identity_scope.matches(item)]

    sprint_state = _backlog_store.get_sprint_state(provider, sprint_id)
    archived_count = 0
    serialized_items: list[SprintItemSummary] = []
    for item in items:
        card_state = sprint_state.items.get(item.key)
        if card_state and card_state.archived:
            archived_count += 1
            if not include_archived:
                continue
        serialized_items.append(_serialize_item(item, card_state))

    return SprintDetail(
        sprint=SprintSummary(
            id=sprint.id,
            name=sprint.name,
            state=sprint.state,
            provider=provider,
            start_date=sprint.start_date.isoformat() if sprint.start_date else None,
            end_date=sprint.end_date.isoformat() if sprint.end_date else None,
            item_count=len(serialized_items),
            goal=sprint.goal,
        ),
        items=serialized_items,
        archived_count=archived_count,
    )


@router.post("/{sprint_id}/items/{item_key}/move", response_model=SprintItemSummary)
def move_sprint_item(
    sprint_id: str,
    item_key: str,
    req: MoveSprintItemRequest,
) -> SprintItemSummary:
    sprint = _read_sprint(req.provider, sprint_id)
    item = _find_item(sprint.items, item_key)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"card {item_key!r} not found in sprint {sprint_id!r}",
        )
    actor_email = _require_actor_email(req.actor_email, req.provider)
    card_state = _backlog_store.record_move(
        req.provider,
        sprint_id,
        item.key,
        target_column=req.target_column,
        actor_email=actor_email,
        note=req.note,
    )
    return _serialize_item(item, card_state)


@router.post("/{sprint_id}/items/{item_key}/archive", response_model=SprintItemSummary)
def archive_sprint_item(
    sprint_id: str,
    item_key: str,
    req: ArchiveSprintItemRequest,
) -> SprintItemSummary:
    sprint = _read_sprint(req.provider, sprint_id)
    item = _find_item(sprint.items, item_key)
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=f"card {item_key!r} not found in sprint {sprint_id!r}",
        )
    actor_email = _require_actor_email(req.actor_email, req.provider)
    card_state = _backlog_store.record_archive(
        req.provider,
        sprint_id,
        item.key,
        archived=req.archived,
        actor_email=actor_email,
        note=req.note,
    )
    return _serialize_item(item, card_state)


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
        for sprint in sprints:
            try:
                if req.provider == "jira":
                    op.read_sprint(sprint_id=sprint.id)
                else:
                    op.read_sprint(iteration_path=sprint.id)
                _imports[job_id]["fetched"] += 1
            except Exception:
                continue
        _imports[job_id]["state"] = "done"
    except Exception as exc:
        _imports[job_id]["state"] = "failed"
        _imports[job_id]["error"] = str(exc)


def _read_sprint(provider: Provider, sprint_id: str) -> Any:
    op: Any = (
        JiraOperator(transport="auto")
        if provider == "jira"
        else AzureDevopsOperator(transport="auto")
    )
    try:
        if provider == "jira":
            return op.read_sprint(sprint_id=sprint_id)
        return op.read_sprint(iteration_path=sprint_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"failed to read sprint: {exc}") from exc


def _find_item(items: list[Any], item_key: str) -> Any | None:
    target = item_key.strip().lower()
    for item in items:
        if item.key.strip().lower() == target or item.id.strip().lower() == target:
            return item
    return None


def _dedupe_sprint_items(items: list[Any]) -> list[Any]:
    deduped: dict[str, Any] = {}
    order: list[str] = []
    for item in items:
        identity = _item_identity(item)
        if not identity:
            identity = f"__anon__:{len(order)}"
        if identity not in deduped:
            deduped[identity] = item
            order.append(identity)
            continue
        deduped[identity] = _prefer_richer_item(deduped[identity], item)
    return [deduped[key] for key in order]


def _item_identity(item: Any) -> str:
    key = str(getattr(item, "key", "") or "").strip().lower()
    if key:
        return key
    return str(getattr(item, "id", "") or "").strip().lower()


def _prefer_richer_item(current: Any, candidate: Any) -> Any:
    current_score = _item_score(current)
    candidate_score = _item_score(candidate)
    winner = candidate if candidate_score > current_score else current
    loser = current if winner is candidate else candidate
    updates: dict[str, Any] = {}
    for field in (
        "description",
        "assignee",
        "assignee_email",
        "assignee_account_id",
        "assignee_descriptor",
        "story_points",
        "parent_key",
        "acceptance_criteria",
        "created_at",
        "updated_at",
        "source_url",
    ):
        if getattr(winner, field, None) in (None, "", []):
            fallback = getattr(loser, field, None)
            if fallback not in (None, "", []):
                updates[field] = fallback
    for field in ("labels", "links", "comments", "attachments"):
        updates[field] = _merge_unique_sequence(
            getattr(current, field, []) or [],
            getattr(candidate, field, []) or [],
        )
    if not updates:
        return winner
    if hasattr(winner, "model_copy"):
        return winner.model_copy(update=updates)
    for field, value in updates.items():
        setattr(winner, field, value)
    return winner


def _item_score(item: Any) -> tuple[float, int, int, int]:
    revision = _revision_score(getattr(item, "revision", None))
    updated = getattr(item, "updated_at", None)
    updated_score = int(updated.timestamp()) if updated else 0
    text_score = sum(
        1
        for field in (
            "description",
            "assignee",
            "assignee_email",
            "parent_key",
            "acceptance_criteria",
            "source_url",
        )
        if getattr(item, field, None)
    )
    relation_score = sum(
        len(getattr(item, field, []) or [])
        for field in ("labels", "links", "comments", "attachments")
    )
    return (revision, updated_score, text_score, relation_score)


def _revision_score(value: Any) -> float:
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _merge_unique_sequence(left: list[Any], right: list[Any]) -> list[Any]:
    seen: set[str] = set()
    merged: list[Any] = []
    for item in [*left, *right]:
        marker = repr(item)
        if marker in seen:
            continue
        seen.add(marker)
        merged.append(item)
    return merged


def _default_scope_email(provider: Provider) -> str:
    profile = profile_mod.load()
    if provider == "jira":
        return profile.jira.email or ""
    return profile.azuredevops.user_email or ""


def _require_actor_email(actor_email: str | None, provider: Provider) -> str:
    email = (actor_email or _default_scope_email(provider)).strip().lower()
    if not email:
        raise HTTPException(status_code=400, detail="actor_email is required for backlog mutations")
    return email


def _serialize_item(item: Any, card_state: BacklogCardState | None) -> SprintItemSummary:
    return SprintItemSummary(
        id=item.id,
        key=item.key,
        type=item.type,
        title=item.title,
        status=item.status,
        description=item.description,
        revision=item.revision,
        assignee=item.assignee,
        assignee_email=item.assignee_email,
        story_points=item.story_points,
        parent_key=item.parent_key,
        labels=list(item.labels or []),
        links=[
            {
                "type": link.type,
                "target_key": link.target_key,
                "target_url": link.target_url,
            }
            for link in item.links
        ],
        comments=[
            {
                "author": comment.author,
                "body": comment.body,
                "created_at": comment.created_at.isoformat(),
            }
            for comment in item.comments
        ],
        attachments=[
            {
                "filename": attachment.filename,
                "url": attachment.url,
                "mime_type": attachment.mime_type,
                "size_bytes": attachment.size_bytes,
            }
            for attachment in item.attachments
        ],
        acceptance_criteria=item.acceptance_criteria,
        created_at=item.created_at.isoformat() if item.created_at else None,
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
        source_url=item.source_url,
        board_column=card_state.board_column if card_state else None,
        board_status=_BOARD_STATUS_LABELS.get(card_state.board_column) if card_state else None,
        board_updated_at=card_state.updated_at.isoformat() if card_state else None,
        board_updated_by=card_state.updated_by if card_state else None,
        archived=card_state.archived if card_state else False,
        history=[
            {
                "action": entry.action,
                "actor_email": entry.actor_email,
                "observed_at": entry.observed_at.isoformat(),
                "from_column": entry.from_column,
                "to_column": entry.to_column,
                "archived": entry.archived,
                "note": entry.note,
            }
            for entry in (card_state.history if card_state else [])
        ],
    )


def _list_jira_active(board_id: str | None) -> list[SprintSummary]:
    profile = profile_mod.load()
    base = (os.getenv("JIRA_BASE_URL", "") or (profile.jira.base_url or "")).rstrip("/")
    email = os.getenv("JIRA_EMAIL", "") or (profile.jira.email or "")
    token = os.getenv("JIRA_API_TOKEN", "")
    if not token and email:
        try:
            token = credentials.get_secret("jira", email) or ""
        except credentials.CredentialError:
            token = ""
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
    for sprint in data.get("values", []):
        out.append(
            SprintSummary(
                id=str(sprint.get("id")),
                name=sprint.get("name", ""),
                state=sprint.get("state", "active"),
                provider="jira",
                start_date=sprint.get("startDate"),
                end_date=sprint.get("endDate"),
                goal=sprint.get("goal"),
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
    for sprint in data.get("value", []):
        attrs = sprint.get("attributes", {})
        sprint_id = sprint.get("path") or _infer_iteration_path(
            project, resolved_team_path, sprint.get("name")
        )
        out.append(
            SprintSummary(
                id=sprint_id or sprint.get("id", ""),
                name=sprint.get("name", ""),
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
        try:
            pat = credentials.get_secret("azuredevops", org) or ""
        except credentials.CredentialError:
            pat = ""
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
            name="Sprint 42 - Onboarding rework",
            state="active",
            provider=provider,
            start_date="2026-05-01T00:00:00Z",
            end_date="2026-05-15T00:00:00Z",
            item_count=12,
            goal="Reduzir friccao no signup",
        ),
        SprintSummary(
            id="43",
            name="Sprint 43 - Push notifications",
            state="active",
            provider=provider,
            start_date="2026-05-08T00:00:00Z",
            end_date="2026-05-22T00:00:00Z",
            item_count=8,
            goal="Lancar push notifications",
        ),
    ]
