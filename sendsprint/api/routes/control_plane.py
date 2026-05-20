"""Control-plane endpoints for the localhost web UI.

Enriched run listing with autonomy, task, branch, and readiness score.
Quality gate reports and evidence bundles per run.

Issue: #102
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sendsprint.api.routes.runs import build_route_preview
from sendsprint.api.runs import events, manager
from sendsprint.api.schemas import RoutePreviewResponse, StartRunRequest

router = APIRouter(prefix="/api/runs", tags=["control-plane"])


# ---------------------------------------------------------------------------
# Schemas (control-plane specific)
# ---------------------------------------------------------------------------


class ControlPlaneRunSummary(BaseModel):
    """Enriched run listing entry for the web control plane."""

    run_id: str
    state: str
    sprint_id: str
    provider: str
    autonomy_level: str = "plan"
    task: str | None = None
    branch: str | None = None
    readiness_score: float | None = None
    readiness_verdict: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    summary: str | None = None
    pr_url: str | None = None
    failed: bool = False
    last_step: int | None = None
    progress: float | None = None


class QualityGateResponse(BaseModel):
    """Quality gate report for a run."""

    run_id: str
    verdict: str
    checks: list[dict[str, Any]] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    created_at: str | None = None


class EvidenceBundleResponse(BaseModel):
    """Evidence bundle summary for a run."""

    run_id: str
    items: list[dict[str, Any]] = Field(default_factory=list)
    total_items: int = 0
    finalized: bool = False
    created_at: str | None = None


class ControlPlaneRunDetail(BaseModel):
    """Full run detail including quality gate, evidence, and logs."""

    run: ControlPlaneRunSummary
    quality_gate: QualityGateResponse | None = None
    evidence: EvidenceBundleResponse | None = None
    logs: list[str] = Field(default_factory=list)
    timeline: list[dict[str, Any]] = Field(default_factory=list)


class StartControlPlaneRunRequest(BaseModel):
    """Request to start a run from the web control plane."""

    provider: str = "jira"
    sprint_id: str
    mode: str = "all"
    item_keys: list[str] = Field(default_factory=list)
    repo_path: str | None = None
    workspace_path: str | None = None
    dry_run: bool = False
    resume: bool = True
    no_cache: bool = False
    autonomy_level: str = "plan"


class StartControlPlaneRunResponse(BaseModel):
    run_id: str
    status: str = "started"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _enrich_run(run_id: str) -> ControlPlaneRunSummary:
    """Build a ControlPlaneRunSummary from existing run data + events."""
    status = manager.get_run(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="run not found")

    request = manager.get_run_request(run_id)
    latest_step = events.latest_of_type(run_id, "step") or {}

    # Derive task from item_keys
    task: str | None = None
    if request and request.item_keys:
        task = ", ".join(request.item_keys[:5])
        if len(request.item_keys) > 5:
            task += f" (+{len(request.item_keys) - 5} more)"

    # Derive branch from repo_path
    branch: str | None = None
    if request and request.repo_path:
        branch = f"sendsprint/{status.sprint_id}"

    # Compute readiness score from event history
    score, verdict = _compute_readiness(run_id)

    return ControlPlaneRunSummary(
        run_id=status.run_id,
        state=status.state,
        sprint_id=status.sprint_id,
        provider=status.provider,
        autonomy_level=request.autonomy_level if request else "plan",
        task=task,
        branch=branch,
        readiness_score=score,
        readiness_verdict=verdict,
        started_at=status.started_at,
        finished_at=status.finished_at,
        summary=status.summary,
        pr_url=status.pr_url,
        failed=status.failed,
        last_step=status.last_step,
        progress=latest_step.get("progress"),
    )


def _compute_readiness(run_id: str) -> tuple[float | None, str | None]:
    """Derive a readiness score from event history."""
    status = manager.get_run(run_id)
    if status is None:
        return None, None

    if status.state == "queued":
        return 0.0, "blocked"
    if status.state == "running":
        latest_step = events.latest_of_type(run_id, "step") or {}
        progress = latest_step.get("progress", 0.0)
        raw = int(progress * 100) if progress else 10
        return float(raw), "blocked" if raw < 50 else "needs_human_approval"
    if status.state == "done" and not status.failed:
        return 100.0, "auto_publish"
    # failed
    return 0.0, "blocked"


def _build_quality_gate(run_id: str) -> QualityGateResponse | None:
    """Build a quality gate report from event history."""
    history = events.history(run_id)
    if not history:
        return None

    checks: list[dict[str, Any]] = []
    reasons: list[str] = []

    # Derive checks from step events
    step_events = [e for e in history if e.get("type") == "step"]
    for ev in step_events:
        name = ev.get("name", "unknown")
        step_status = ev.get("status", "unknown")
        passed = step_status in {"ok", "done"}
        severity = (
            "info"
            if passed
            else "blocking"
            if name in {"tests-regression", "tests-unit"}
            else "error"
        )
        checks.append(
            {
                "check_name": name,
                "passed": passed,
                "details": ev.get("message", ""),
                "severity": severity,
            }
        )
        if not passed:
            reasons.append(f"{name}: {ev.get('message', 'failed')}")

    # Determine verdict
    has_blocking = any(c["severity"] == "blocking" and not c["passed"] for c in checks)
    has_error = any(c["severity"] == "error" and not c["passed"] for c in checks)
    if has_blocking or has_error:
        verdict = "needs_rework"
    elif reasons:
        verdict = "needs_human_approval"
    else:
        verdict = "pass"

    status = manager.get_run(run_id)
    if status and status.state == "done" and not status.failed:
        verdict = "pass"

    return QualityGateResponse(
        run_id=run_id,
        verdict=verdict,
        checks=checks,
        reasons=reasons,
    )


def _build_evidence(run_id: str) -> EvidenceBundleResponse | None:
    """Build evidence summary from event history."""
    history = events.history(run_id)
    evidence_events = [e for e in history if e.get("type") == "evidence"]
    if not evidence_events:
        return None

    items: list[dict[str, Any]] = []
    for ev in evidence_events:
        items.append(
            {
                "type": "evidence",
                "path": ev.get("evidence_path", ""),
                "label": ev.get("evidence_label", ""),
                "iteration": ev.get("iteration"),
                "observed_at": ev.get("observed_at"),
            }
        )

    status = manager.get_run(run_id)
    finalized = status.state in {"done", "failed"} if status else False

    return EvidenceBundleResponse(
        run_id=run_id,
        items=items,
        total_items=len(items),
        finalized=finalized,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("", response_model=list[ControlPlaneRunSummary])
def list_control_plane_runs() -> list[ControlPlaneRunSummary]:
    """List all runs with enriched control-plane data."""
    runs = manager.list_runs()
    return [_enrich_run(r.run_id) for r in runs]


@router.post("", response_model=StartControlPlaneRunResponse)
def start_control_plane_run(req: StartControlPlaneRunRequest) -> StartControlPlaneRunResponse:
    """Start a new run from the web control plane."""
    start_req = _to_start_run_request(req)
    status = manager.start_run(start_req)
    return StartControlPlaneRunResponse(run_id=status.run_id)


@router.post("/preview", response_model=RoutePreviewResponse)
def preview_control_plane_run(req: StartControlPlaneRunRequest) -> RoutePreviewResponse:
    """Read-only route preview for Web run preparation."""
    return build_route_preview(_to_start_run_request(req))


@router.get("/{run_id}", response_model=ControlPlaneRunDetail)
def get_control_plane_run(run_id: str) -> ControlPlaneRunDetail:
    """Full run detail with quality gate, evidence, and logs."""
    run_summary = _enrich_run(run_id)
    quality_gate = _build_quality_gate(run_id)
    evidence = _build_evidence(run_id)

    history = events.history(run_id)
    logs = [e.get("message", "") for e in history if e.get("type") == "log" and e.get("message")][
        -50:
    ]
    timeline = history[-100:]

    return ControlPlaneRunDetail(
        run=run_summary,
        quality_gate=quality_gate,
        evidence=evidence,
        logs=logs,
        timeline=timeline,
    )


@router.get("/{run_id}/evidence", response_model=EvidenceBundleResponse)
def get_run_evidence(run_id: str) -> EvidenceBundleResponse:
    """Evidence bundle for a run."""
    if manager.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    evidence = _build_evidence(run_id)
    if evidence is None:
        return EvidenceBundleResponse(run_id=run_id)
    return evidence


@router.get("/{run_id}/quality", response_model=QualityGateResponse)
def get_run_quality(run_id: str) -> QualityGateResponse:
    """Quality gate report for a run."""
    if manager.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    gate = _build_quality_gate(run_id)
    if gate is None:
        return QualityGateResponse(run_id=run_id, verdict="pending")
    return gate


def _to_start_run_request(req: StartControlPlaneRunRequest) -> StartRunRequest:
    return StartRunRequest(
        provider=req.provider,  # type: ignore[arg-type]
        sprint_id=req.sprint_id,
        mode=req.mode,  # type: ignore[arg-type]
        item_keys=req.item_keys,
        repo_path=req.repo_path,
        workspace_path=req.workspace_path,
        dry_run=req.dry_run,
        resume=req.resume,
        no_cache=req.no_cache,
        autonomy_level=req.autonomy_level,  # type: ignore[arg-type]
    )
