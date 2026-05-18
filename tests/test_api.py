"""Smoke tests for the SendSprint mobile API."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from sendsprint.api.server import app

client = TestClient(app)


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


def test_dashboard_run_404_for_missing():
    resp = client.get("/runs/does-not-exist/dashboard")
    assert resp.status_code == 404


def test_evidence_404_when_missing():
    resp = client.get("/runs/anything/evidence/missing.png")
    assert resp.status_code == 404
