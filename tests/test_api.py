"""Smoke tests for the SendSprint mobile API."""

from __future__ import annotations

import time

import pytest

pytest.importorskip("fastapi")

from sendsprint.api.server import app
from sendsprint.profile import Profile
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


def test_auth_azure_accepts_sprint_url_and_returns_inferred_paths(monkeypatch):
    updates: list[dict[str, object]] = []
    secrets: list[tuple[str, str, str]] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"name": "ONS-16058-MANUTSIS-FORT"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        def get(self, url):
            assert "DigitalProjects-Americas" in url
            assert "ONS-16058-MANUTSIS-FORT" in url
            return FakeResponse()

    monkeypatch.setattr("sendsprint.api.routes.auth.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "sendsprint.api.routes.auth.credentials.set_secret",
        lambda provider, account, secret: secrets.append((provider, account, secret)),
    )
    monkeypatch.setattr(
        "sendsprint.api.routes.auth.profile_mod.update",
        lambda **kwargs: updates.append(kwargs),
    )

    payload = {
        "sprint_url": (
            "https://dev.azure.com/DigitalProjects-Americas/ONS-16058-MANUTSIS-FORT/"
            "_sprints/taskboard/Time_019/ONS-16058-MANUTSIS-FORT/Time_019/T019_Sprint_98"
        ),
        "pat": "redacted-test-pat",
    }
    resp = client.post("/auth/azuredevops", json=payload)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ado_team_path"] == "DigitalProjects-Americas/ONS-16058-MANUTSIS-FORT/Time_019"
    assert body["ado_iteration_path"] == "ONS-16058-MANUTSIS-FORT\\Time_019\\T019_Sprint_98"
    assert updates[0]["azuredevops.organization"] == "DigitalProjects-Americas"
    assert updates[0]["azuredevops.project"] == "ONS-16058-MANUTSIS-FORT"
    assert updates[0]["azuredevops.team"] == "Time_019"
    assert secrets[0][:2] == ("azuredevops", "DigitalProjects-Americas")


def test_list_ado_sprints_uses_profile_context_and_iteration_path_id(monkeypatch):
    for var in ("AZURE_DEVOPS_ORG", "AZURE_DEVOPS_PROJECT", "AZURE_DEVOPS_PAT"):
        monkeypatch.delenv(var, raising=False)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "value": [
                    {
                        "id": "guid-1",
                        "name": "T019_Sprint_98",
                        "path": "ONS-16058-MANUTSIS-FORT\\Time_019\\T019_Sprint_98",
                        "attributes": {
                            "startDate": "2026-05-18",
                            "finishDate": "2026-05-31",
                        },
                    }
                ]
            }

    class FakeClient:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        def get(self, url):
            assert "_apis/work/teamsettings/iterations" in url
            assert "DigitalProjects-Americas/ONS-16058-MANUTSIS-FORT/Time_019" in url
            return FakeResponse()

    monkeypatch.setattr("sendsprint.api.routes.sprints.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "sendsprint.api.routes.sprints.profile_mod.load",
        lambda: Profile.model_validate(
            {
                "azuredevops": {
                    "organization": "DigitalProjects-Americas",
                    "project": "ONS-16058-MANUTSIS-FORT",
                    "team": "Time_019",
                }
            }
        ),
    )
    monkeypatch.setattr(
        "sendsprint.api.routes.sprints.credentials.get_secret",
        lambda provider, account: "cached-pat",
    )

    resp = client.get("/sprints", params={"provider": "azuredevops"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body[0]["id"] == "ONS-16058-MANUTSIS-FORT\\Time_019\\T019_Sprint_98"


def test_get_ado_sprint_uses_iteration_path(monkeypatch):
    calls: list[str] = []

    class FakeOperator:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def read_sprint(self, **kwargs):
            calls.append(kwargs["iteration_path"])
            return type(
                "SprintStub",
                (),
                {
                    "id": kwargs["iteration_path"],
                    "name": "Sprint 98",
                    "state": "active",
                    "start_date": None,
                    "end_date": None,
                    "goal": None,
                    "items": [],
                },
            )()

    monkeypatch.setattr("sendsprint.api.routes.sprints.AzureDevopsOperator", FakeOperator)

    resp = client.get(
        "/sprints/ONS-16058-MANUTSIS-FORT%5CTime_019%5CT019_Sprint_98",
        params={"provider": "azuredevops"},
    )

    assert resp.status_code == 200, resp.text
    assert calls == ["ONS-16058-MANUTSIS-FORT\\Time_019\\T019_Sprint_98"]


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
