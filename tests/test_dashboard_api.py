"""Tests for the live dashboard API endpoints (issue #103)."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")

from sendsprint.api.routes.dashboard import configure
from sendsprint.api.runs import events, manager
from sendsprint.api.server import app
from sendsprint.yool.contracts import ContractRegistry, InputCache, YoolContract
from tests.api_client import AuthenticatedTestClient

client = AuthenticatedTestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _clean_dashboard_singletons():
    """Reset dashboard singletons between tests."""
    configure(contract_registry=None, input_cache=None)
    yield
    configure(contract_registry=None, input_cache=None)


def _seed_run(sprint_id: str = "dash-100", extra_events: list[dict] | None = None) -> str:
    """Start a run and optionally seed events.  Returns run_id."""
    payload = {
        "provider": "jira",
        "sprint_id": sprint_id,
        "mode": "all",
        "item_keys": ["DASH-1"],
    }
    resp = client.post("/runs", json=payload)
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    # Wait for the run to start
    _wait_for_state(run_id, {"running", "done", "failed"})

    if extra_events:
        for ev in extra_events:
            events.publish_threadsafe(run_id, ev)
        time.sleep(0.05)

    return run_id


def _wait_for_state(run_id: str, states: set[str], timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = manager.get_run(run_id)
        if status and status.state in states:
            return
        time.sleep(0.05)


# ---------------------------------------------------------------------------
# GET /api/dashboard/yools
# ---------------------------------------------------------------------------


def test_yools_empty():
    resp = client.get("/api/dashboard/yools")
    assert resp.status_code == 200
    data = resp.json()
    assert "yools" in data
    assert "cache_stats" in data
    assert "registered_contracts" in data


def test_yools_with_events():
    _seed_run(
        extra_events=[
            {
                "type": "step",
                "yool_id": "agent.codex.plan",
                "status": "ok",
                "cost_usd": 0.02,
                "duration_ms": 150,
                "cache_hit": True,
            },
            {
                "type": "step",
                "yool_id": "agent.codex.plan",
                "status": "ok",
                "cost_usd": 0.01,
                "duration_ms": 100,
                "cache_hit": False,
            },
        ]
    )
    resp = client.get("/api/dashboard/yools")
    assert resp.status_code == 200
    data = resp.json()
    yools = data["yools"]
    codex = [y for y in yools if y["yool_id"] == "agent.codex.plan"]
    assert len(codex) == 1
    stat = codex[0]
    assert stat["total_invocations"] == 2
    assert stat["cache_hits"] == 1
    assert stat["cache_misses"] == 1
    assert stat["cache_hit_rate"] == 0.5
    assert stat["total_cost_usd"] == pytest.approx(0.03)
    assert stat["total_duration_ms"] == 250
    assert stat["avg_duration_ms"] == 125.0


def test_yools_with_configured_registry():
    registry = ContractRegistry()
    registry.register(YoolContract(yool_id="test.yool"))
    cache = InputCache(ttl_s=60.0)
    configure(contract_registry=registry, input_cache=cache)

    resp = client.get("/api/dashboard/yools")
    assert resp.status_code == 200
    data = resp.json()
    assert data["registered_contracts"] == 1


def test_yools_with_errors():
    _seed_run(
        extra_events=[
            {
                "type": "step",
                "yool_id": "agent.hermes.test",
                "status": "failed",
                "error": "timeout exceeded",
                "duration_ms": 5000,
            },
        ]
    )
    resp = client.get("/api/dashboard/yools")
    data = resp.json()
    hermes = [y for y in data["yools"] if y["yool_id"] == "agent.hermes.test"]
    assert len(hermes) == 1
    assert hermes[0]["last_status"] == "failed"
    assert "timeout exceeded" in hermes[0]["errors"]


# ---------------------------------------------------------------------------
# GET /api/dashboard/yools/{yool_id} — drill-down
# ---------------------------------------------------------------------------


def test_yool_detail_found():
    _seed_run(
        extra_events=[
            {
                "type": "step",
                "yool_id": "agent.lint.check",
                "status": "ok",
                "cost_usd": 0.005,
                "duration_ms": 80,
            },
        ]
    )
    resp = client.get("/api/dashboard/yools/agent.lint.check")
    assert resp.status_code == 200
    data = resp.json()
    assert data["yool_id"] == "agent.lint.check"
    assert data["total_invocations"] >= 1


def test_yool_detail_not_found():
    resp = client.get("/api/dashboard/yools/nonexistent.yool")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/dashboard/agents
# ---------------------------------------------------------------------------


def test_agents_returns_registry():
    resp = client.get("/api/dashboard/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert "agents" in data
    assert "total_active_runs" in data
    agents = data["agents"]
    keys = [a["key"] for a in agents]
    assert "codex" in keys
    assert "claude-code" in keys
    assert "hermes" in keys
    assert "openclaw" in keys


def test_agents_have_capabilities():
    resp = client.get("/api/dashboard/agents")
    data = resp.json()
    codex = [a for a in data["agents"] if a["key"] == "codex"][0]
    assert "plan" in codex["capabilities"]
    assert "implement" in codex["capabilities"]
    assert codex["runtime"] == "goal"


# ---------------------------------------------------------------------------
# GET /api/dashboard/validations
# ---------------------------------------------------------------------------


def test_validations_all_lanes_present():
    resp = client.get("/api/dashboard/validations")
    assert resp.status_code == 200
    data = resp.json()
    lanes = {lane["lane"] for lane in data["lanes"]}
    assert lanes == {"dev", "lint", "test", "security", "pr"}


def test_validations_with_events():
    _seed_run(
        extra_events=[
            {"type": "step", "name": "lint-check", "status": "ok"},
            {"type": "step", "name": "test-unit", "status": "failed", "message": "2 tests failed"},
        ]
    )
    resp = client.get("/api/dashboard/validations")
    data = resp.json()
    lint_lane = [lane for lane in data["lanes"] if lane["lane"] == "lint"][0]
    assert lint_lane["events_count"] >= 1
    assert lint_lane["last_result"] == "ok"

    test_lane = [lane for lane in data["lanes"] if lane["lane"] == "test"][0]
    assert test_lane["events_count"] >= 1
    assert test_lane["last_result"] == "failed"


# ---------------------------------------------------------------------------
# GET /api/dashboard/tuples
# ---------------------------------------------------------------------------


def test_tuples_returns_runs():
    _seed_run(sprint_id="tuple-200")
    resp = client.get("/api/dashboard/tuples")
    assert resp.status_code == 200
    data = resp.json()
    assert "tuples" in data
    assert "total_runs" in data
    assert data["total_runs"] >= 1
    assert "active_runs" in data
    assert "failed_runs" in data

    ids = [t["run_id"] for t in data["tuples"]]
    assert len(ids) >= 1


def test_tuples_contain_run_fields():
    run_id = _seed_run(sprint_id="tuple-300")
    resp = client.get("/api/dashboard/tuples")
    data = resp.json()
    matching = [t for t in data["tuples"] if t["run_id"] == run_id]
    assert len(matching) == 1
    entry = matching[0]
    assert entry["sprint_id"] == "tuple-300"
    assert entry["provider"] == "jira"
    assert "state" in entry
    assert "event_count" in entry


# ---------------------------------------------------------------------------
# GET /api/dashboard/tuples/{run_id} — drill-down
# ---------------------------------------------------------------------------


def test_tuple_detail_found():
    run_id = _seed_run(sprint_id="tuple-400")
    resp = client.get(f"/api/dashboard/tuples/{run_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["run_id"] == run_id
    assert data["sprint_id"] == "tuple-400"


def test_tuple_detail_not_found():
    resp = client.get("/api/dashboard/tuples/nonexistent-run")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /runs/{run_id}/events/stream — SSE stream endpoint
# ---------------------------------------------------------------------------


def test_sse_stream_404_for_missing_run():
    resp = client.get("/runs/nonexistent/events/stream")
    assert resp.status_code == 404


def test_sse_stream_emits_hello():
    run_id = _seed_run(sprint_id="sse-100")

    # Pre-load the async queue with a done event so the stream terminates.
    # We must put it directly on the async queue since publish_threadsafe
    # without a running loop only appends to history.
    q = events.queue_for(run_id)
    import asyncio

    loop = asyncio.new_event_loop()
    loop.run_until_complete(q.put({"type": "done", "summary": "ok"}))
    loop.close()

    with client.stream("GET", f"/runs/{run_id}/events/stream") as resp:
        assert resp.status_code == 200
        lines = []
        for chunk in resp.iter_text():
            lines.append(chunk)
            if "done" in chunk:
                break

    full = "".join(lines)
    assert "event: hello" in full
    assert run_id in full
