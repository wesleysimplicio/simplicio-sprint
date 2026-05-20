"""Dashboard endpoints for live tuple, yool, agent, and validation observability.

Provides aggregated views over run events, yool contracts, agent registry,
and validation lanes.  Designed for polling from the web UI; the SSE stream
endpoint lives on the runs router (GET /api/runs/{run_id}/events/stream).

Issue: #103
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from sendsprint.agent_registry import default_agent_registry
from sendsprint.api.runs import events, manager
from sendsprint.yool.contracts import ContractRegistry, InputCache

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# ---------------------------------------------------------------------------
# Shared singletons (injected at import time for simplicity; production
# would use FastAPI dependency injection or a service locator).
# ---------------------------------------------------------------------------

_contract_registry: ContractRegistry | None = None
_input_cache: InputCache | None = None


def configure(
    contract_registry: ContractRegistry | None = None,
    input_cache: InputCache | None = None,
) -> None:
    """Allow the app bootstrap to inject shared instances."""
    global _contract_registry, _input_cache
    _contract_registry = contract_registry
    _input_cache = input_cache


def _get_contract_registry() -> ContractRegistry:
    return _contract_registry or ContractRegistry()


def _get_input_cache() -> InputCache:
    return _input_cache or InputCache()


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class YoolStat(BaseModel):
    """Per-yool aggregate statistics."""

    yool_id: str
    total_invocations: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    total_retries: int = 0
    total_cost_usd: float = 0.0
    total_duration_ms: int = 0
    avg_duration_ms: float = 0.0
    last_status: str = "unknown"
    errors: list[str] = Field(default_factory=list)


class YoolDashboardResponse(BaseModel):
    yools: list[YoolStat] = Field(default_factory=list)
    cache_stats: dict[str, Any] = Field(default_factory=dict)
    registered_contracts: int = 0


class AgentDashboardEntry(BaseModel):
    """One agent provider status."""

    key: str
    name: str
    runtime: str
    capabilities: list[str] = Field(default_factory=list)
    active_runs: int = 0
    notes: list[str] = Field(default_factory=list)


class AgentDashboardResponse(BaseModel):
    agents: list[AgentDashboardEntry] = Field(default_factory=list)
    total_active_runs: int = 0


class ValidationLane(BaseModel):
    """Status of a single validation lane."""

    lane: str
    status: str = "idle"
    last_run_id: str | None = None
    last_result: str | None = None
    events_count: int = 0
    errors: list[str] = Field(default_factory=list)


class ValidationDashboardResponse(BaseModel):
    lanes: list[ValidationLane] = Field(default_factory=list)
    total_events: int = 0


class TupleEntry(BaseModel):
    """Tuple status for a run."""

    run_id: str
    state: str
    sprint_id: str
    provider: str
    started_at: str | None = None
    finished_at: str | None = None
    failed: bool = False
    event_count: int = 0
    last_event_type: str | None = None
    progress: float | None = None


class TupleDashboardResponse(BaseModel):
    tuples: list[TupleEntry] = Field(default_factory=list)
    total_runs: int = 0
    active_runs: int = 0
    failed_runs: int = 0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALIDATION_LANES = ("dev", "lint", "test", "security", "pr")


def _build_yool_stats() -> YoolDashboardResponse:
    """Aggregate yool stats from event history across all runs."""
    registry = _get_contract_registry()
    cache = _get_input_cache()
    yool_map: dict[str, YoolStat] = {}

    for run_status in manager.list_runs():
        run_id = run_status.run_id
        for ev in events.history(run_id):
            yool_id = ev.get("yool_id")
            if not yool_id:
                continue
            if yool_id not in yool_map:
                yool_map[yool_id] = YoolStat(yool_id=yool_id)
            stat = yool_map[yool_id]
            stat.total_invocations += 1
            stat.total_cost_usd += ev.get("cost_usd", 0.0)
            stat.total_duration_ms += ev.get("duration_ms", 0)
            stat.total_retries += ev.get("retry_count", 0)
            if ev.get("cache_hit"):
                stat.cache_hits += 1
            else:
                stat.cache_misses += 1
            status = ev.get("status", "")
            if status:
                stat.last_status = status
            error = ev.get("error")
            if error and error not in stat.errors:
                stat.errors.append(error)

    for stat in yool_map.values():
        total = stat.cache_hits + stat.cache_misses
        stat.cache_hit_rate = stat.cache_hits / total if total > 0 else 0.0
        stat.avg_duration_ms = (
            stat.total_duration_ms / stat.total_invocations if stat.total_invocations > 0 else 0.0
        )

    return YoolDashboardResponse(
        yools=list(yool_map.values()),
        cache_stats=cache.stats(),
        registered_contracts=len(registry.all()),
    )


def _build_agent_dashboard() -> AgentDashboardResponse:
    """Build agent status from registry + active runs."""
    registry = default_agent_registry()
    active_runs = [r for r in manager.list_runs() if r.state == "running"]

    entries: list[AgentDashboardEntry] = []
    for provider in registry.providers:
        entries.append(
            AgentDashboardEntry(
                key=provider.key,
                name=provider.name,
                runtime=provider.runtime,
                capabilities=[c.key for c in provider.capabilities],
                active_runs=0,
                notes=list(provider.notes),
            )
        )

    return AgentDashboardResponse(
        agents=entries,
        total_active_runs=len(active_runs),
    )


def _build_validation_dashboard() -> ValidationDashboardResponse:
    """Build validation lane status from event history."""
    lane_map: dict[str, ValidationLane] = {
        lane: ValidationLane(lane=lane) for lane in VALIDATION_LANES
    }
    total_events = 0

    for run_status in manager.list_runs():
        run_id = run_status.run_id
        for ev in events.history(run_id):
            ev_type = ev.get("type", "")
            ev_name = ev.get("name", "")

            lane_key: str | None = None
            for lane in VALIDATION_LANES:
                if lane in ev_name or lane in ev_type:
                    lane_key = lane
                    break

            if lane_key is None:
                continue

            total_events += 1
            lane_entry = lane_map[lane_key]
            lane_entry.events_count += 1
            lane_entry.last_run_id = run_id

            status = ev.get("status", "")
            if status:
                lane_entry.status = status
                lane_entry.last_result = status

            error = ev.get("error") or ev.get("message", "")
            if ev.get("status") in ("failed", "error") and error and error not in lane_entry.errors:
                lane_entry.errors.append(error)

    return ValidationDashboardResponse(
        lanes=list(lane_map.values()),
        total_events=total_events,
    )


def _build_tuple_dashboard() -> TupleDashboardResponse:
    """Build tuple status from all runs."""
    all_runs = manager.list_runs()
    tuples: list[TupleEntry] = []

    for run_status in all_runs:
        run_id = run_status.run_id
        history = events.history(run_id)
        last_event = history[-1] if history else None
        latest_step = events.latest_of_type(run_id, "step") or {}

        tuples.append(
            TupleEntry(
                run_id=run_id,
                state=run_status.state,
                sprint_id=run_status.sprint_id,
                provider=run_status.provider,
                started_at=run_status.started_at,
                finished_at=run_status.finished_at,
                failed=run_status.failed,
                event_count=len(history),
                last_event_type=last_event.get("type") if last_event else None,
                progress=latest_step.get("progress"),
            )
        )

    active = sum(1 for t in tuples if t.state == "running")
    failed = sum(1 for t in tuples if t.failed)

    return TupleDashboardResponse(
        tuples=tuples,
        total_runs=len(tuples),
        active_runs=active,
        failed_runs=failed,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/yools", response_model=YoolDashboardResponse)
def get_yool_dashboard() -> YoolDashboardResponse:
    """Yool stats: cache hits, retries, cost, duration per yool."""
    return _build_yool_stats()


@router.get("/agents", response_model=AgentDashboardResponse)
def get_agent_dashboard() -> AgentDashboardResponse:
    """Active agent provider status."""
    return _build_agent_dashboard()


@router.get("/validations", response_model=ValidationDashboardResponse)
def get_validation_dashboard() -> ValidationDashboardResponse:
    """Validation lane status (dev, lint, test, security, pr)."""
    return _build_validation_dashboard()


@router.get("/tuples", response_model=TupleDashboardResponse)
def get_tuple_dashboard() -> TupleDashboardResponse:
    """Tuple status across all runs."""
    return _build_tuple_dashboard()


@router.get("/yools/{yool_id}", response_model=YoolStat)
def get_yool_detail(yool_id: str) -> YoolStat:
    """Drill-down for a specific yool with per-event evidence."""
    dashboard = _build_yool_stats()
    for yool in dashboard.yools:
        if yool.yool_id == yool_id:
            return yool
    raise HTTPException(status_code=404, detail=f"yool '{yool_id}' not found in event history")


@router.get("/tuples/{run_id}", response_model=TupleEntry)
def get_tuple_detail(run_id: str) -> TupleEntry:
    """Drill-down for a specific tuple/run."""
    if manager.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    dashboard = _build_tuple_dashboard()
    for entry in dashboard.tuples:
        if entry.run_id == run_id:
            return entry
    raise HTTPException(status_code=404, detail="tuple not found")
