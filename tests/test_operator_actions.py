"""Tests for operator action endpoints and audit trail.

Covers: pause, resume, cancel, rerun, approve actions, autonomy blocking,
confirmation gate for destructive actions, state validation, audit recording,
and audit query endpoint.

Issue: #104
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sendsprint.api.routes.operator import _set_relay
from sendsprint.api.runs import manager
from sendsprint.api.schemas import RunStatus, StartRunRequest
from sendsprint.api.server import create_app
from sendsprint.audit import AuditEntry, AuditLog, audit_log
from sendsprint.status_relay import StatusRelay
from tests.api_client import AuthenticatedTestClient

TestClient = AuthenticatedTestClient


@pytest.fixture(autouse=True)
def _clean_state():
    """Reset in-memory stores between tests."""
    manager._runs.clear()
    manager._threads.clear()
    manager._requests.clear()
    # Reset audit log
    audit_log._entries.clear()
    # Inject fresh relay
    relay = StatusRelay()
    _set_relay(relay)
    yield
    _set_relay(None)


def _seed_run(
    run_id: str = "r1",
    state: str = "running",
    sprint_id: str = "sp1",
    provider: str = "jira",
    failed: bool = False,
    last_step: int | None = None,
) -> RunStatus:
    """Insert a fake run into the manager."""
    status = RunStatus(
        run_id=run_id,
        state=state,
        sprint_id=sprint_id,
        provider=provider,
        failed=failed,
        last_step=last_step,
    )
    manager._runs[run_id] = status
    # Seed a request with default autonomy (plan)
    manager._requests[run_id] = StartRunRequest(
        provider=provider,
        sprint_id=sprint_id,
    )
    return status


@pytest.fixture()
def client():
    app = create_app()
    return AuthenticatedTestClient(app)


# ---------------------------------------------------------------------------
# AuditEntry / AuditLog unit tests
# ---------------------------------------------------------------------------


class TestAuditEntry:
    def test_create_entry(self):
        entry = AuditEntry(operator="alice", action="pause", run_id="r1")
        assert entry.operator == "alice"
        assert entry.action == "pause"
        assert entry.run_id == "r1"
        assert entry.result == "ok"
        assert entry.timestamp is not None

    def test_frozen(self):
        entry = AuditEntry(operator="alice", action="pause", run_id="r1")
        with pytest.raises(ValidationError):
            entry.operator = "bob"  # type: ignore[misc]

    def test_serialization_roundtrip(self):
        entry = AuditEntry(operator="alice", action="cancel", run_id="r1", detail={"step": 3})
        data = entry.model_dump(mode="json")
        assert data["operator"] == "alice"
        assert data["action"] == "cancel"
        assert data["detail"] == {"step": 3}
        assert "timestamp" in data


class TestAuditLog:
    def test_append_and_len(self):
        log = AuditLog()
        entry = AuditEntry(operator="alice", action="pause", run_id="r1")
        log.append(entry)
        assert len(log) == 1

    def test_query_by_run_id(self):
        log = AuditLog()
        log.append(AuditEntry(operator="alice", action="pause", run_id="r1"))
        log.append(AuditEntry(operator="alice", action="resume", run_id="r2"))
        results = log.query(run_id="r1")
        assert len(results) == 1
        assert results[0].run_id == "r1"

    def test_query_by_operator(self):
        log = AuditLog()
        log.append(AuditEntry(operator="alice", action="pause", run_id="r1"))
        log.append(AuditEntry(operator="bob", action="pause", run_id="r1"))
        results = log.query(operator="bob")
        assert len(results) == 1
        assert results[0].operator == "bob"

    def test_query_by_action(self):
        log = AuditLog()
        log.append(AuditEntry(operator="alice", action="pause", run_id="r1"))
        log.append(AuditEntry(operator="alice", action="cancel", run_id="r1"))
        results = log.query(action="cancel")
        assert len(results) == 1

    def test_query_limit(self):
        log = AuditLog()
        for i in range(10):
            log.append(AuditEntry(operator="alice", action="pause", run_id=f"r{i}"))
        results = log.query(limit=3)
        assert len(results) == 3

    def test_query_newest_first(self):
        log = AuditLog()
        log.append(AuditEntry(operator="alice", action="pause", run_id="r1"))
        log.append(AuditEntry(operator="alice", action="resume", run_id="r1"))
        results = log.query(run_id="r1")
        assert results[0].action == "resume"  # newest first
        assert results[1].action == "pause"

    def test_export(self):
        log = AuditLog()
        log.append(AuditEntry(operator="alice", action="pause", run_id="r1"))
        exported = log.export(run_id="r1")
        assert len(exported) == 1
        assert isinstance(exported[0], dict)
        assert exported[0]["operator"] == "alice"

    def test_max_entries(self):
        log = AuditLog(max_entries=3)
        for i in range(5):
            log.append(AuditEntry(operator="alice", action="pause", run_id=f"r{i}"))
        assert len(log) == 3


# ---------------------------------------------------------------------------
# Pause endpoint
# ---------------------------------------------------------------------------


class TestPauseAction:
    def test_pause_running(self, client: AuthenticatedTestClient):
        _seed_run("r1", state="running")
        resp = client.post("/api/runs/r1/actions/pause", json={"operator": "tester"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["action"] == "pause"
        assert data["result"] == "ok"

    def test_pause_not_running(self, client: AuthenticatedTestClient):
        _seed_run("r1", state="done")
        resp = client.post("/api/runs/r1/actions/pause")
        assert resp.status_code == 409

    def test_pause_404(self, client: AuthenticatedTestClient):
        resp = client.post("/api/runs/missing/actions/pause")
        assert resp.status_code == 404

    def test_pause_records_audit(self, client: TestClient):
        _seed_run("r1", state="running")
        client.post("/api/runs/r1/actions/pause", json={"operator": "alice"})
        entries = audit_log.query(run_id="r1")
        assert len(entries) == 1
        assert entries[0].action == "pause"
        assert entries[0].operator == "alice"


# ---------------------------------------------------------------------------
# Resume endpoint
# ---------------------------------------------------------------------------


class TestResumeAction:
    def test_resume_queued(self, client: TestClient):
        _seed_run("r1", state="queued")
        resp = client.post("/api/runs/r1/actions/resume")
        assert resp.status_code == 200

    def test_resume_running(self, client: TestClient):
        _seed_run("r1", state="running")
        resp = client.post("/api/runs/r1/actions/resume")
        assert resp.status_code == 200

    def test_resume_done(self, client: TestClient):
        _seed_run("r1", state="done")
        resp = client.post("/api/runs/r1/actions/resume")
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Cancel endpoint
# ---------------------------------------------------------------------------


class TestCancelAction:
    def test_cancel_requires_confirmation(self, client: TestClient):
        _seed_run("r1", state="running")
        resp = client.post("/api/runs/r1/actions/cancel", json={"operator": "tester"})
        assert resp.status_code == 428
        assert "confirmed" in resp.json()["detail"].lower()

    def test_cancel_confirmed(self, client: TestClient):
        _seed_run("r1", state="running")
        resp = client.post(
            "/api/runs/r1/actions/cancel",
            json={"operator": "tester", "confirmed": True},
        )
        assert resp.status_code == 200
        # Run state should be failed after cancel
        assert manager.get_run("r1").state == "failed"

    def test_cancel_done_run(self, client: TestClient):
        _seed_run("r1", state="done")
        resp = client.post(
            "/api/runs/r1/actions/cancel",
            json={"confirmed": True},
        )
        assert resp.status_code == 409

    def test_cancel_records_audit(self, client: TestClient):
        _seed_run("r1", state="running")
        client.post(
            "/api/runs/r1/actions/cancel",
            json={"operator": "bob", "confirmed": True},
        )
        entries = audit_log.query(run_id="r1", action="cancel")
        assert len(entries) == 1
        assert entries[0].operator == "bob"


# ---------------------------------------------------------------------------
# Rerun endpoint
# ---------------------------------------------------------------------------


class TestRerunAction:
    def test_rerun_failed(self, client: TestClient):
        _seed_run("r1", state="failed", failed=True, last_step=5)
        from sendsprint.api.routes import operator

        original = operator._resolve_autonomy
        operator._resolve_autonomy = lambda run_id: "execute"
        try:
            resp = client.post("/api/runs/r1/actions/rerun")
            assert resp.status_code == 200
            data = resp.json()
            assert data["action"] == "rerun"
            assert data["detail"]["last_step"] == 5
            # State should be reset to running
            assert manager.get_run("r1").state == "running"
        finally:
            operator._resolve_autonomy = original

    def test_rerun_not_failed(self, client: TestClient):
        _seed_run("r1", state="running")
        from sendsprint.api.routes import operator

        original = operator._resolve_autonomy
        operator._resolve_autonomy = lambda run_id: "execute"
        try:
            resp = client.post("/api/runs/r1/actions/rerun")
            assert resp.status_code == 409
        finally:
            operator._resolve_autonomy = original

    def test_rerun_blocked_by_autonomy(self, client: TestClient):
        """Rerun requires 'execute' level; observe-only run should be blocked."""
        _seed_run("r1", state="failed", failed=True)
        from sendsprint.api.routes import operator

        original = operator._resolve_autonomy

        def _observe_only(run_id: str):
            return "observe"

        operator._resolve_autonomy = _observe_only
        try:
            resp = client.post("/api/runs/r1/actions/rerun")
            assert resp.status_code == 403
            assert "autonomy" in resp.json()["detail"].lower()
        finally:
            operator._resolve_autonomy = original


# ---------------------------------------------------------------------------
# Approve endpoint
# ---------------------------------------------------------------------------


class TestApproveAction:
    def test_approve_done_blocked_by_low_autonomy(self, client: TestClient):
        _seed_run("r1", state="done")
        resp = client.post("/api/runs/r1/actions/approve")
        # Default autonomy is 'plan', approve requires 'pr' -> blocked
        assert resp.status_code == 403

    def test_approve_with_sufficient_autonomy(self, client: TestClient):
        _seed_run("r1", state="done")
        from sendsprint.api.routes import operator

        original = operator._resolve_autonomy
        operator._resolve_autonomy = lambda run_id: "pr"
        try:
            resp = client.post("/api/runs/r1/actions/approve")
            assert resp.status_code == 200
            assert resp.json()["action"] == "approve"
        finally:
            operator._resolve_autonomy = original

    def test_approve_not_done(self, client: TestClient):
        _seed_run("r1", state="running")
        from sendsprint.api.routes import operator

        original = operator._resolve_autonomy
        operator._resolve_autonomy = lambda run_id: "pr"
        try:
            resp = client.post("/api/runs/r1/actions/approve")
            assert resp.status_code == 409
        finally:
            operator._resolve_autonomy = original


# ---------------------------------------------------------------------------
# Audit query endpoint
# ---------------------------------------------------------------------------


class TestAuditEndpoint:
    def test_audit_empty(self, client: TestClient):
        _seed_run("r1", state="running")
        resp = client.get("/api/runs/r1/audit")
        assert resp.status_code == 200
        assert resp.json()["entries"] == []
        assert resp.json()["total"] == 0

    def test_audit_after_actions(self, client: TestClient):
        _seed_run("r1", state="running")
        client.post("/api/runs/r1/actions/pause", json={"operator": "alice"})
        resp = client.get("/api/runs/r1/audit")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["entries"][0]["action"] == "pause"
        assert data["entries"][0]["operator"] == "alice"

    def test_audit_404(self, client: TestClient):
        resp = client.get("/api/runs/missing/audit")
        assert resp.status_code == 404

    def test_audit_multiple_actions(self, client: TestClient):
        _seed_run("r1", state="running")
        client.post("/api/runs/r1/actions/pause", json={"operator": "alice"})
        # Resume needs queued or running state — pause doesn't change the state in manager
        client.post("/api/runs/r1/actions/resume", json={"operator": "bob"})
        resp = client.get("/api/runs/r1/audit")
        assert resp.json()["total"] == 2


# ---------------------------------------------------------------------------
# Autonomy blocking
# ---------------------------------------------------------------------------


class TestAutonomyBlocking:
    def test_observe_level_allows_pause(self, client: TestClient):
        """Pause requires observe; even observe-level run should allow it."""
        _seed_run("r1", state="running")
        from sendsprint.api.routes import operator

        original = operator._resolve_autonomy
        operator._resolve_autonomy = lambda run_id: "observe"
        try:
            resp = client.post("/api/runs/r1/actions/pause")
            assert resp.status_code == 200
        finally:
            operator._resolve_autonomy = original

    def test_observe_level_blocks_cancel(self, client: TestClient):
        """Cancel requires plan; observe-level run should be blocked."""
        _seed_run("r1", state="running")
        from sendsprint.api.routes import operator

        original = operator._resolve_autonomy
        operator._resolve_autonomy = lambda run_id: "observe"
        try:
            resp = client.post(
                "/api/runs/r1/actions/cancel",
                json={"confirmed": True},
            )
            assert resp.status_code == 403
        finally:
            operator._resolve_autonomy = original

    def test_plan_level_allows_cancel(self, client: TestClient):
        """Cancel requires plan; plan-level run should allow it."""
        _seed_run("r1", state="running")
        resp = client.post(
            "/api/runs/r1/actions/cancel",
            json={"confirmed": True},
        )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Control command relay integration
# ---------------------------------------------------------------------------


class TestControlCommandRelay:
    def test_pause_enqueues_command(self, client: TestClient):
        relay = StatusRelay()
        _set_relay(relay)
        _seed_run("r1", state="running")
        client.post("/api/runs/r1/actions/pause")
        cmds = relay.drain_commands()
        assert len(cmds) == 1
        assert cmds[0].action == "pause"

    def test_cancel_enqueues_command(self, client: TestClient):
        relay = StatusRelay()
        _set_relay(relay)
        _seed_run("r1", state="running")
        client.post("/api/runs/r1/actions/cancel", json={"confirmed": True})
        cmds = relay.drain_commands()
        assert len(cmds) == 1
        assert cmds[0].action == "cancel"

    def test_rerun_enqueues_resume_with_payload(self, client: TestClient):
        relay = StatusRelay()
        _set_relay(relay)
        _seed_run("r1", state="failed", failed=True, last_step=3)
        from sendsprint.api.routes import operator

        original = operator._resolve_autonomy
        operator._resolve_autonomy = lambda run_id: "execute"
        try:
            client.post("/api/runs/r1/actions/rerun")
            cmds = relay.drain_commands()
            assert len(cmds) == 1
            assert cmds[0].action == "resume"
            assert cmds[0].payload.get("rerun_failed") is True
        finally:
            operator._resolve_autonomy = original
