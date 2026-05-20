"""Smoke tests for the SendSprint mobile API."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")

from sendsprint.api.server import app
from tests.api_client import AuthenticatedTestClient

client = AuthenticatedTestClient(app)


def test_health_returns_version_and_provider_flags():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "version" in body
    assert "providers_configured" in body
    assert set(body["providers_configured"]) == {"jira", "azuredevops"}


def test_list_sprints_returns_demo_when_creds_missing(monkeypatch):
    for var in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    resp = client.get("/sprints", params={"provider": "jira"})
    assert resp.status_code == 200
    sprints = resp.json()
    assert len(sprints) >= 1
    assert all(s["provider"] == "jira" for s in sprints)


def test_start_run_returns_run_id_and_emits_events():
    payload = {
        "provider": "jira",
        "sprint_id": "42",
        "mode": "all",
        "item_keys": ["DEMO-1", "DEMO-2"],
    }
    resp = client.post("/runs", json=payload)
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]
    assert run_id

    # Wait briefly for the worker thread to publish at least one event.
    deadline = time.monotonic() + 5.0
    status = None
    while time.monotonic() < deadline:
        status_resp = client.get(f"/runs/{run_id}")
        assert status_resp.status_code == 200
        status = status_resp.json()
        if status["state"] in {"running", "done"}:
            break
        time.sleep(0.1)
    assert status is not None
    assert status["state"] in {"running", "done"}


def test_get_run_404_for_missing():
    resp = client.get("/runs/does-not-exist")
    assert resp.status_code == 404


def test_agent_status_returns_detailed_snapshot() -> None:
    payload = {
        "provider": "jira",
        "sprint_id": "77",
        "mode": "selected",
        "item_keys": ["APP-7"],
    }
    resp = client.post("/runs", json=payload)
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    deadline = time.monotonic() + 5.0
    snapshot = None
    while time.monotonic() < deadline:
        snap_resp = client.get(f"/runs/{run_id}/agent-status")
        assert snap_resp.status_code == 200
        snapshot = snap_resp.json()
        if snapshot["timeline"]:
            break
        time.sleep(0.1)

    assert snapshot is not None
    assert snapshot["run_id"] == run_id
    assert snapshot["item_keys"] == ["APP-7"]
    assert snapshot["timeline"]
    assert "recent_logs" in snapshot


def test_status_answer_returns_read_only_agent_summary() -> None:
    payload = {
        "provider": "jira",
        "sprint_id": "88",
        "mode": "selected",
        "item_keys": ["APP-8"],
    }
    resp = client.post("/runs", json=payload)
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    answer_resp = client.get(
        f"/runs/{run_id}/status-answer",
        params={"adapter": "codex", "question": "what is running?"},
    )

    assert answer_resp.status_code == 200
    answer = answer_resp.json()
    assert answer["adapter"] == "codex"
    assert answer["run_id"] == run_id
    assert "read-only status answer" in answer["constraints"]


def test_dashboard_run_404_for_missing():
    resp = client.get("/runs/does-not-exist/dashboard")
    assert resp.status_code == 404


def test_agent_status_404_for_missing():
    resp = client.get("/runs/does-not-exist/agent-status")
    assert resp.status_code == 404


def test_evidence_404_when_missing():
    resp = client.get("/runs/anything/evidence/missing.png")
    assert resp.status_code == 404
