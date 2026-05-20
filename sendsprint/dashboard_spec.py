"""Node dashboard and Playwright lane boundary specifications.

Defines the contracts that the Node dashboard UI consumes from the
Python control plane, and the isolation rules for Playwright evidence
capture.  The Node layer is UI-only — it never owns orchestration,
scheduling, quality gates, or worker lifecycle.

See: https://github.com/wesleysimplicio/SendSprint/issues/109
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# SSE event protocol
# ---------------------------------------------------------------------------


class SSEEventType(StrEnum):
    """Event types the Python API pushes over the SSE /runs/{run_id}/events
    stream.  The Node dashboard subscribes and renders — it never produces
    these events itself."""

    hello = "hello"
    step = "step"
    log = "log"
    evidence = "evidence"
    loop = "loop"
    regression = "regression"
    summary = "summary"
    done = "done"
    error = "error"
    agent_state = "agent_state"
    operator_chat = "operator_chat"
    keepalive = "keepalive"


class SSEEventPayload(BaseModel):
    """Canonical shape of a single SSE ``data:`` line.  Every field is
    optional except ``type`` and ``run_id`` so the dashboard can handle
    partial updates without crashing."""

    model_config = ConfigDict(extra="allow")

    type: SSEEventType
    run_id: str
    step: int | None = None
    name: str | None = None
    status: str | None = None
    message: str | None = None
    evidence_path: str | None = None
    evidence_label: str | None = None
    progress: float | None = None
    summary: str | None = None
    pr_url: str | None = None
    failed: bool | None = None
    iteration: int | None = None
    max_iterations: int | None = None
    failing_tests: list[str] | None = None
    agent_name: str | None = None
    agent_status: str | None = None
    chat_message: str | None = None
    chat_sender: str | None = None


# ---------------------------------------------------------------------------
# Dashboard event protocol
# ---------------------------------------------------------------------------


class DashboardEventProtocol(BaseModel):
    """Documents the full set of SSE event types, payload schemas, and
    delivery guarantees the Node dashboard can rely on."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol_version: str = "1.0.0"
    transport: Literal["sse"] = "sse"
    endpoint_pattern: str = "/runs/{run_id}/events"
    keepalive_interval_s: int = 30
    event_types: list[str] = Field(
        default_factory=lambda: [e.value for e in SSEEventType],
    )
    terminal_events: list[str] = Field(
        default_factory=lambda: ["done", "error"],
    )
    ordering_guarantee: str = "events arrive in causal order per run_id"
    reconnect_advice: str = (
        "client should reconnect with exponential backoff; "
        "missed events are not replayed — poll GET /runs/{run_id} "
        "for current state after reconnect"
    )


# ---------------------------------------------------------------------------
# Node dashboard scope
# ---------------------------------------------------------------------------


class NodeDashboardScope(StrEnum):
    """Capabilities the Node dashboard is allowed to exercise."""

    render_run_state = "render_run_state"
    render_agent_state = "render_agent_state"
    render_validation_evidence = "render_validation_evidence"
    render_operator_chat = "render_operator_chat"
    subscribe_sse = "subscribe_sse"
    call_read_apis = "call_read_apis"
    call_control_apis = "call_control_apis"


class NodeDashboardSpec(BaseModel):
    """Contract defining what the Node dashboard does and does NOT do.

    The dashboard is a thin UI layer.  It consumes the Python API over
    HTTP + SSE and renders state.  It never:
    - Owns the run loop or scheduler
    - Manages worker processes
    - Evaluates quality gates
    - Writes to operational memory
    - Publishes PRs or updates issues
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    spec_version: str = "1.0.0"
    description: str = (
        "Node dashboard is a read-heavy UI that consumes the Python "
        "control-plane API.  It renders run state, agent state, "
        "validation evidence, and operator chat.  Long-running "
        "operations use SSE and never block UI rendering."
    )
    allowed_scopes: list[NodeDashboardScope] = Field(
        default_factory=lambda: list(NodeDashboardScope),
    )
    forbidden_actions: list[str] = Field(
        default_factory=lambda: [
            "own_orchestration",
            "manage_workers",
            "evaluate_quality_gates",
            "write_operational_memory",
            "publish_prs",
            "update_issues",
            "schedule_runs",
            "manage_credentials",
        ],
    )

    # API endpoints the dashboard consumes (all Python-owned)
    consumed_apis: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {"method": "GET", "path": "/health", "purpose": "liveness check"},
            {"method": "GET", "path": "/runs", "purpose": "list all runs"},
            {"method": "GET", "path": "/runs/{run_id}", "purpose": "run status"},
            {
                "method": "GET",
                "path": "/runs/{run_id}/agent-status",
                "purpose": "agent-level snapshot",
            },
            {
                "method": "GET",
                "path": "/runs/{run_id}/dashboard",
                "purpose": "dashboard composite view",
            },
            {
                "method": "GET",
                "path": "/runs/{run_id}/events",
                "purpose": "SSE event stream",
            },
            {
                "method": "GET",
                "path": "/runs/{run_id}/evidence/{name}",
                "purpose": "evidence file download",
            },
            {
                "method": "GET",
                "path": "/api/runs",
                "purpose": "control-plane enriched run list",
            },
            {
                "method": "GET",
                "path": "/api/runs/{run_id}",
                "purpose": "control-plane run detail",
            },
            {
                "method": "GET",
                "path": "/api/runs/{run_id}/evidence",
                "purpose": "evidence bundle summary",
            },
            {
                "method": "GET",
                "path": "/api/runs/{run_id}/quality",
                "purpose": "quality gate report",
            },
            {
                "method": "POST",
                "path": "/runs",
                "purpose": "start a run (dashboard may trigger)",
            },
            {
                "method": "POST",
                "path": "/api/runs",
                "purpose": "start via control plane",
            },
        ],
    )

    event_protocol: DashboardEventProtocol = Field(
        default_factory=DashboardEventProtocol,
    )


# ---------------------------------------------------------------------------
# Playwright lane isolation
# ---------------------------------------------------------------------------


class PlaywrightEvidenceKind(StrEnum):
    """Types of evidence the Playwright lane can capture."""

    screenshot = "screenshot"
    trace = "trace"
    video = "video"
    har = "har"
    accessibility_snapshot = "accessibility_snapshot"
    console_log = "console_log"


class PlaywrightLaneSpec(BaseModel):
    """Isolation contract for the Playwright evidence capture lane.

    Playwright runs in an isolated Node/browser context.  It captures
    evidence (screenshots, traces, videos, HAR) and writes them to a
    well-known directory.  The Python control plane reads those artifacts
    through the evidence API — Playwright never calls Python internals
    directly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    spec_version: str = "1.0.0"
    description: str = (
        "Playwright evidence capture runs in an isolated browser "
        "context.  It writes artifacts to a local directory; the "
        "Python API serves them.  No direct coupling to Python "
        "worker internals, scheduler, or quality gates."
    )

    evidence_kinds: list[PlaywrightEvidenceKind] = Field(
        default_factory=lambda: list(PlaywrightEvidenceKind),
    )

    # Where Playwright writes evidence (relative to workspace root)
    output_dir_pattern: str = "evidence/{run_id}/"

    # Isolation guarantees
    isolation_rules: list[str] = Field(
        default_factory=lambda: [
            "playwright process has no import path to sendsprint Python packages",
            "communication with Python is via filesystem (evidence dir) or HTTP API only",
            "playwright never reads or writes .sendsprint/runs/ state files",
            "playwright never evaluates quality gates or readiness scores",
            "playwright browser context is disposable — one per evidence capture session",
            "playwright evidence is append-only; Python never mutates captured artifacts",
        ],
    )

    # How evidence flows from Playwright to the dashboard
    evidence_flow: list[str] = Field(
        default_factory=lambda: [
            "1. Playwright captures artifact -> writes to evidence/{run_id}/",
            "2. Python worker emits SSE event type=evidence with evidence_path",
            "3. Dashboard receives SSE event and renders evidence link",
            "4. Dashboard fetches artifact via GET /runs/{run_id}/evidence/{name}",
        ],
    )

    # Allowed interactions with the Python API
    allowed_api_calls: list[str] = Field(
        default_factory=lambda: [
            "GET /runs/{run_id}/evidence/{name}  (read own captured files)",
        ],
    )

    forbidden_actions: list[str] = Field(
        default_factory=lambda: [
            "import sendsprint Python modules",
            "read or write run state files",
            "call internal Python functions",
            "evaluate quality gates",
            "modify operational memory",
            "start or stop worker processes",
        ],
    )
