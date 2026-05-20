"""Operator action endpoints for the web UI.

Exposes safe run mutations (pause, resume, cancel, rerun, approve) behind
autonomy-level checks and audit logging.

Issue: #104
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sendsprint.api.runs import events, manager
from sendsprint.audit import AuditEntry, AuditLog, OperatorAction, audit_log
from sendsprint.policy import (
    LEVEL_ORDER,
    AutonomyLevel,
    AutonomyPolicy,
)
from sendsprint.status_relay import ControlAction, ControlCommand

router = APIRouter(prefix="/api/runs", tags=["operator"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

# Actions that require confirmation from the caller (destructive/irreversible).
DESTRUCTIVE_ACTIONS: frozenset[OperatorAction] = frozenset({"cancel"})

# Minimum autonomy level required per operator action.
ACTION_AUTONOMY: dict[OperatorAction, AutonomyLevel] = {
    "pause": "observe",
    "resume": "observe",
    "cancel": "plan",
    "rerun": "execute",
    "approve": "pr",
    "open_evidence": "observe",
    "open_pr": "observe",
}


class ActionRequest(BaseModel):
    """Payload sent by the web UI for an operator action."""

    operator: str = "web-ui"
    confirmed: bool = False
    payload: dict[str, Any] = Field(default_factory=dict)


class ActionResponse(BaseModel):
    """Result returned after an operator action."""

    run_id: str
    action: str
    result: str = "ok"
    detail: dict[str, Any] = Field(default_factory=dict)


class AuditQueryResponse(BaseModel):
    """Audit trail query result."""

    entries: list[dict[str, Any]] = Field(default_factory=list)
    total: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_relay = None  # Lazy — tests can inject via _set_relay


def _get_relay():
    """Return the StatusRelay singleton (lazy import to avoid circular deps)."""
    global _relay
    if _relay is None:
        from sendsprint.status_relay import StatusRelay

        _relay = StatusRelay()
    return _relay


def _set_relay(relay) -> None:
    """Test helper: inject a StatusRelay instance."""
    global _relay
    _relay = relay


def _resolve_autonomy(run_id: str) -> AutonomyLevel:
    """Best-effort autonomy level for a run (falls back to 'plan')."""
    req = manager.get_run_request(run_id)
    if req and hasattr(req, "autonomy_level"):
        raw = getattr(req, "autonomy_level", "plan")
        if raw in LEVEL_ORDER:
            return raw  # type: ignore[return-value]
    return "plan"


def _check_autonomy(action: OperatorAction, run_id: str) -> None:
    """Raise 403 if the run's autonomy level is too low for *action*."""
    required = ACTION_AUTONOMY[action]
    current = _resolve_autonomy(run_id)
    policy = AutonomyPolicy(level=current)
    if not policy.allows_level(required):
        raise HTTPException(
            status_code=403,
            detail=(
                f"action '{action}' requires autonomy level '{required}', "
                f"but run '{run_id}' is at '{current}'"
            ),
        )


def _require_run(run_id: str):
    """Return RunStatus or raise 404."""
    status = manager.get_run(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="run not found")
    return status


def _record(
    action: OperatorAction,
    run_id: str,
    operator: str,
    result: str = "ok",
    detail: dict[str, Any] | None = None,
    log: AuditLog | None = None,
) -> AuditEntry:
    """Append an audit entry and return it."""
    entry = AuditEntry(
        operator=operator,
        action=action,
        run_id=run_id,
        result=result,
        detail=detail or {},
    )
    (log or audit_log).append(entry)
    return entry


def _enqueue_control(action: ControlAction, run_id: str, payload: dict[str, Any] | None = None):
    """Enqueue a ControlCommand on the StatusRelay."""
    relay = _get_relay()
    cmd = ControlCommand(
        action=action,
        issued_by="claude",  # web-ui maps to the claude agent context
        payload=payload or {},
    )
    relay.enqueue_command(cmd)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/{run_id}/actions/pause", response_model=ActionResponse)
def pause_run(run_id: str, req: ActionRequest | None = None) -> ActionResponse:
    """Pause a running run."""
    req = req or ActionRequest()
    status = _require_run(run_id)
    _check_autonomy("pause", run_id)

    if status.state != "running":
        raise HTTPException(status_code=409, detail=f"cannot pause run in state '{status.state}'")

    _enqueue_control("pause", run_id)
    events.publish_threadsafe(
        run_id, {"type": "log", "message": f"operator pause by {req.operator}"}
    )
    _record("pause", run_id, req.operator)
    return ActionResponse(run_id=run_id, action="pause")


@router.post("/{run_id}/actions/resume", response_model=ActionResponse)
def resume_run(run_id: str, req: ActionRequest | None = None) -> ActionResponse:
    """Resume a paused run."""
    req = req or ActionRequest()
    status = _require_run(run_id)
    _check_autonomy("resume", run_id)

    # Accept resume from queued or running (paused is signalled via control command)
    if status.state not in {"queued", "running"}:
        raise HTTPException(status_code=409, detail=f"cannot resume run in state '{status.state}'")

    _enqueue_control("resume", run_id)
    events.publish_threadsafe(
        run_id, {"type": "log", "message": f"operator resume by {req.operator}"}
    )
    _record("resume", run_id, req.operator)
    return ActionResponse(run_id=run_id, action="resume")


@router.post("/{run_id}/actions/cancel", response_model=ActionResponse)
def cancel_run(run_id: str, req: ActionRequest | None = None) -> ActionResponse:
    """Cancel a run. Requires confirmation (destructive)."""
    req = req or ActionRequest()
    status = _require_run(run_id)
    _check_autonomy("cancel", run_id)

    if not req.confirmed:
        raise HTTPException(
            status_code=428,
            detail="cancel is destructive — set confirmed=true to proceed",
        )

    if status.state in {"done", "failed"}:
        raise HTTPException(status_code=409, detail=f"cannot cancel run in state '{status.state}'")

    _enqueue_control("cancel", run_id)
    status.state = "failed"
    status.failed = True
    events.publish_threadsafe(
        run_id, {"type": "log", "message": f"operator cancel by {req.operator}"}
    )
    _record("cancel", run_id, req.operator)
    return ActionResponse(run_id=run_id, action="cancel")


@router.post("/{run_id}/actions/rerun", response_model=ActionResponse)
def rerun_failed_step(run_id: str, req: ActionRequest | None = None) -> ActionResponse:
    """Rerun the last failed step of a run."""
    req = req or ActionRequest()
    status = _require_run(run_id)
    _check_autonomy("rerun", run_id)

    if status.state != "failed":
        raise HTTPException(status_code=409, detail="rerun is only available for failed runs")

    # Reset state to running so the worker can pick it up
    status.state = "running"
    status.failed = False
    _enqueue_control("resume", run_id, {"rerun_failed": True})
    events.publish_threadsafe(
        run_id, {"type": "log", "message": f"operator rerun by {req.operator}"}
    )
    _record("rerun", run_id, req.operator, detail={"last_step": status.last_step})
    return ActionResponse(
        run_id=run_id,
        action="rerun",
        detail={"last_step": status.last_step},
    )


@router.post("/{run_id}/actions/approve", response_model=ActionResponse)
def approve_publish(run_id: str, req: ActionRequest | None = None) -> ActionResponse:
    """Approve a run for publishing (PR merge, release, etc.)."""
    req = req or ActionRequest()
    status = _require_run(run_id)
    _check_autonomy("approve", run_id)

    if status.state != "done":
        raise HTTPException(status_code=409, detail="approve is only available for completed runs")

    _enqueue_control("approve", run_id)
    events.publish_threadsafe(
        run_id, {"type": "log", "message": f"operator approve by {req.operator}"}
    )
    _record("approve", run_id, req.operator)
    return ActionResponse(run_id=run_id, action="approve")


# ---------------------------------------------------------------------------
# Audit trail endpoint
# ---------------------------------------------------------------------------


@router.get("/{run_id}/audit", response_model=AuditQueryResponse)
def get_run_audit(run_id: str, limit: int = 100) -> AuditQueryResponse:
    """Query audit trail for a specific run."""
    _require_run(run_id)
    entries = audit_log.query(run_id=run_id, limit=limit)
    exported = [e.model_dump(mode="json") for e in entries]
    return AuditQueryResponse(entries=exported, total=len(exported))
