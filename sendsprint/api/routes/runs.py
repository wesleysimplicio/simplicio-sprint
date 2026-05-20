"""Run endpoints: start a sprint run + list status + SSE event stream."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from sendsprint.api.runs import events, manager
from sendsprint.api.runs.agent_status import build_agent_snapshot
from sendsprint.api.runs.status_answer import render_status_answer
from sendsprint.api.schemas import (
    AgentRunSnapshot,
    AgentStatusAnswer,
    RouteConfidence,
    RoutePreviewLowConfidenceItem,
    RoutePreviewResponse,
    RoutePreviewSelectedRepo,
    RoutePreviewSummary,
    RoutePreviewTaskUnderstanding,
    RunStatus,
    StartRunRequest,
    StartRunResponse,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=StartRunResponse)
def start_run(req: StartRunRequest) -> StartRunResponse:
    status = manager.start_run(req)
    return StartRunResponse(run_id=status.run_id)


@router.post("/preview", response_model=RoutePreviewResponse)
def preview_run(req: StartRunRequest) -> RoutePreviewResponse:
    """Build the route preview used before execution by Web and CLI clients."""
    return build_route_preview(req)


@router.get("", response_model=list[RunStatus])
def list_runs() -> list[RunStatus]:
    return manager.list_runs()


@router.get("/{run_id}", response_model=RunStatus)
def get_run(run_id: str) -> RunStatus:
    s = manager.get_run(run_id)
    if s is None:
        raise HTTPException(status_code=404, detail="run not found")
    return s


@router.get("/{run_id}/agent-status", response_model=AgentRunSnapshot)
def get_agent_status(run_id: str) -> AgentRunSnapshot:
    snapshot = build_agent_snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return snapshot


@router.get("/{run_id}/status-answer", response_model=AgentStatusAnswer)
def get_status_answer(
    run_id: str,
    adapter: str = "generic",
    question: str | None = None,
) -> AgentStatusAnswer:
    snapshot = build_agent_snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return render_status_answer(snapshot, adapter=adapter, question=question)


@router.get("/{run_id}/dashboard", response_model=dict)
def get_run_dashboard(run_id: str) -> dict:
    """Return a local dashboard snapshot backed by run status and evidence files."""
    status = manager.get_run(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="run not found")
    evidence_dir = manager.evidence_root(run_id)
    evidence = [
        {"name": path.name, "path": str(path)}
        for path in sorted(evidence_dir.glob("*"))
        if path.is_file()
    ]
    return {
        "run": status.model_dump(),
        "evidence": evidence,
        "summary": status.summary,
        "pr_url": status.pr_url,
        "blockers": [] if not status.failed else [status.summary or "run failed"],
    }


@router.get("/{run_id}/events")
async def run_events(run_id: str) -> StreamingResponse:
    """Server-Sent Events stream — one JSON event per `data:` line."""
    if manager.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")

    async def gen():
        yield 'event: hello\ndata: {"run_id":"' + run_id + '"}\n\n'
        while True:
            try:
                event = await asyncio.wait_for(events.drain(run_id), timeout=30.0)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            payload = json.dumps({**event, "run_id": run_id})
            yield f"data: {payload}\n\n"
            if event.get("type") in {"done", "error"}:
                events.close(run_id)
                break

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/{run_id}/events/stream")
async def run_event_stream(run_id: str) -> StreamingResponse:
    """SSE stream for live dashboard updates — richer than /events.

    Emits ``hello``, ``step``, ``log``, ``evidence``, ``done``, and ``error``
    frames.  Keepalive every 30 s.  Issue #103.
    """
    if manager.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")

    async def _generate():
        yield f"event: hello\ndata: {json.dumps({'run_id': run_id})}\n\n"
        while True:
            try:
                event = await asyncio.wait_for(events.drain(run_id), timeout=30.0)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            event_type = event.get("type", "message")
            payload = json.dumps({**event, "run_id": run_id})
            yield f"event: {event_type}\ndata: {payload}\n\n"
            if event_type in {"done", "error"}:
                events.close(run_id)
                break

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.get("/{run_id}/evidence/{name}")
def get_evidence(run_id: str, name: str) -> FileResponse:
    """Serve a captured evidence file (screenshot/log) for the web UI."""
    safe = os.path.basename(name)
    candidates = [
        Path("evidence") / run_id / safe,
        Path("evidence") / safe,
    ]
    for path in candidates:
        if path.is_file():
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="evidence not found")


# ---------- route preview helpers ----------


_CONFIDENCE_WEIGHT = {"high": 0, "medium": 1, "low": 2}


def build_route_preview(req: StartRunRequest) -> RoutePreviewResponse:
    """Return a read-only explanation of how SendSprint will route sprint work."""
    try:
        result = _dry_run_delivery_plan(req)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"failed to build route preview: {exc}",
        ) from exc

    plan = result.delivery_plan
    if plan is None:
        raise HTTPException(status_code=500, detail="delivery plan was not produced")
    return _route_preview_from_plan(req, result.sprint, plan)


def _dry_run_delivery_plan(req: StartRunRequest) -> Any:
    from sendsprint.flow import SprintFlow
    from sendsprint.operators import AzureDevopsOperator, JiraOperator
    from sendsprint.policy import AutonomyPolicy
    from sendsprint.scope import build_scope
    from sendsprint.workspace import load_workspace

    operator: Any
    if req.provider == "jira":
        operator = JiraOperator(transport="auto")
    else:
        operator = AzureDevopsOperator(transport="auto")

    workspace = load_workspace(req.workspace_path) if req.workspace_path else None
    scope = build_scope(
        mode="mine" if req.mode == "mine" else "all",
        task_keys=req.item_keys or None,
    )
    flow = SprintFlow(
        operator=operator,
        workspace=workspace,
        scope=scope,
        autonomy_policy=AutonomyPolicy(level="plan"),
    )
    if req.provider == "jira":
        return flow.bootstrap(
            sprint_id=req.sprint_id,
            repo_path=req.repo_path,
            dry_run=True,
            resume=req.resume,
            run_id=req.run_id,
        )
    return flow.bootstrap(
        iteration_path=req.sprint_id,
        repo_path=req.repo_path,
        dry_run=True,
        resume=req.resume,
        run_id=req.run_id,
    )


def _route_preview_from_plan(
    req: StartRunRequest,
    sprint: Any,
    plan: Any,
) -> RoutePreviewResponse:
    from sendsprint.agents.story_task_planner import delivery_items, infer_item_scopes

    deliveries_by_item: dict[str, list[Any]] = {}
    selected_repos: list[RoutePreviewSelectedRepo] = []
    low_confidence: list[RoutePreviewLowConfidenceItem] = []

    for delivery in plan.deliveries:
        deliveries_by_item.setdefault(delivery.item_key, []).append(delivery)
        repo_name = Path(delivery.repo).name
        selected_repos.append(
            RoutePreviewSelectedRepo(
                item_key=delivery.item_key,
                item_type=delivery.item_type,
                title=delivery.title,
                repo=delivery.repo,
                repo_name=repo_name,
                repo_role=delivery.repo_role,
                branch=delivery.branch,
                target_branch=delivery.target_branch,
                confidence=delivery.confidence,
                reasons=[delivery.reason],
                relationship=delivery.relationship,
                worktree_path=delivery.worktree_path,
                validation_template=delivery.validation_template,
                validation_commands=delivery.validation_commands,
            )
        )
        if delivery.confidence == "low":
            low_confidence.append(
                RoutePreviewLowConfidenceItem(
                    item_key=delivery.item_key,
                    title=delivery.title,
                    repo=delivery.repo,
                    repo_name=repo_name,
                    reason=delivery.reason,
                    recommended_action=_recommended_route_action(delivery.reason),
                )
            )

    task_understanding: list[RoutePreviewTaskUnderstanding] = []
    for item in delivery_items(sprint):
        item_key = item.key or item.id
        deliveries = deliveries_by_item.get(item_key, [])
        explicit_scopes = sorted(
            {
                label.split(":", 1)[1]
                for label in item.labels
                if label.startswith("scope:") and ":" in label
            }
        )
        inferred_scopes = sorted(infer_item_scopes(item))
        scopes = explicit_scopes or inferred_scopes
        source = "label" if explicit_scopes else "inferred" if inferred_scopes else "none"
        scope_source = cast(Literal["label", "inferred", "none"], source)
        relationship = (
            "parent" if item.parent_key else "related" if getattr(item, "links", None) else "none"
        )
        reasons = _unique([delivery.reason for delivery in deliveries])
        selected_names = _unique([Path(delivery.repo).name for delivery in deliveries])
        confidence = cast(
            RouteConfidence | None,
            _least_confident([delivery.confidence for delivery in deliveries]),
        )
        task_understanding.append(
            RoutePreviewTaskUnderstanding(
                item_key=item_key,
                item_type=item.type,
                title=item.title,
                status=item.status,
                scopes=scopes,
                scope_source=scope_source,
                relationship=relationship,
                selected_repos=selected_names,
                confidence=confidence,
                reasons=reasons,
            )
        )
        if not deliveries:
            reason = _warning_reason_for_item(plan.warnings, item_key) or (
                "no compatible repository matched"
            )
            low_confidence.append(
                RoutePreviewLowConfidenceItem(
                    item_key=item_key,
                    title=item.title,
                    reason=reason,
                    recommended_action=_recommended_route_action(reason),
                )
            )

    unique_repo_count = len({delivery.repo for delivery in plan.deliveries})
    summary = RoutePreviewSummary(
        text=(
            f"{len(plan.deliveries)} repo route(s) for {len(task_understanding)} task(s), "
            f"{len(low_confidence)} low-confidence or unmatched item(s)"
        ),
        task_count=len(task_understanding),
        planned_delivery_count=len(plan.deliveries),
        selected_repo_count=unique_repo_count,
        low_confidence_count=len(low_confidence),
        warning_count=len(plan.warnings),
    )
    return RoutePreviewResponse(
        provider=req.provider,
        sprint_id=plan.sprint_id,
        sprint_name=plan.sprint_name,
        mode=req.mode,
        item_keys=req.item_keys,
        autonomy_level=plan.autonomy_level,
        side_effects=plan.side_effects,
        summary=summary,
        task_understanding=task_understanding,
        selected_repos=selected_repos,
        low_confidence_items=low_confidence,
        warnings=plan.warnings,
    )


def _least_confident(values: list[str]) -> str | None:
    if not values:
        return None
    return max(values, key=lambda value: _CONFIDENCE_WEIGHT[value])


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


def _warning_reason_for_item(warnings: list[str], item_key: str) -> str | None:
    for warning in warnings:
        if warning.startswith(f"{item_key}:"):
            return warning.split(":", 1)[1].strip()
    return None


def _recommended_route_action(reason: str) -> str:
    lowered = reason.lower()
    if "no compatible repository" in lowered:
        return "Configure a matching repo role in workspace.yaml or add an explicit scope label."
    if "no clear front/back signal" in lowered or "not explicit" in lowered:
        return "Add scope:front or scope:back to the item, or clarify the title/description."
    if "no scope, role, or tech signal" in lowered:
        return "Add workspace repo roles, tech markers, or explicit task scope before execution."
    return "Review this route before execution and add explicit scope or repo metadata if needed."
