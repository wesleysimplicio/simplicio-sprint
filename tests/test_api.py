"""Smoke tests for the SendSprint mobile API."""

from __future__ import annotations

import time
from pathlib import Path

import httpx
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


def test_version_check_reports_available_update(monkeypatch):
    monkeypatch.setattr("sendsprint.api.server.__version__", "0.20.0")
    monkeypatch.setattr("sendsprint.api.server._fetch_latest_pypi_version", lambda: "0.21.0")

    resp = client.get("/version/check")

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_version"] == "0.20.0"
    assert body["latest_version"] == "0.21.0"
    assert body["update_available"] is True
    assert body["status"] == "ok"


def test_version_check_reports_up_to_date(monkeypatch):
    monkeypatch.setattr("sendsprint.api.server.__version__", "0.20.0")
    monkeypatch.setattr("sendsprint.api.server._fetch_latest_pypi_version", lambda: "0.20.0")

    resp = client.get("/version/check")

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_version"] == "0.20.0"
    assert body["latest_version"] == "0.20.0"
    assert body["update_available"] is False
    assert body["status"] == "ok"


def test_version_check_reports_unavailable_when_pypi_fails(monkeypatch):
    monkeypatch.setattr("sendsprint.api.server.__version__", "0.20.0")

    def fail() -> str:
        raise RuntimeError("network blocked")

    monkeypatch.setattr("sendsprint.api.server._fetch_latest_pypi_version", fail)

    resp = client.get("/version/check")

    assert resp.status_code == 200
    body = resp.json()
    assert body["current_version"] == "0.20.0"
    assert body["latest_version"] is None
    assert body["update_available"] is False
    assert body["status"] == "unavailable"
    assert "network blocked" in body["message"]


def test_list_sprints_returns_demo_when_creds_missing(monkeypatch):
    for var in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)
    resp = client.get("/sprints", params={"provider": "jira"})
    assert resp.status_code == 200
    sprints = resp.json()
    assert len(sprints) >= 1
    assert all(s["provider"] == "jira" for s in sprints)


def test_auth_bootstrap_exposes_operator_token():
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("sendsprint.api.routes.auth.get_operator_token", lambda: "local-token")
    monkeypatch.setattr(
        "sendsprint.api.routes.auth.status",
        lambda: {
            "default_provider": None,
            "jira_configured": False,
            "azuredevops_configured": False,
            "providers": {},
        },
    )
    resp = client.get("/auth/bootstrap")

    try:
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["operator_token"] == "local-token"
    finally:
        monkeypatch.undo()


def test_app_login_marks_local_user_active():
    resp = client.post(
        "/auth/app-login",
        json={"email": "dev@example.com", "password": "local-pass"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "dev@example.com"
    assert body["active"] is True


def test_auth_jira_uses_browser_fallback_on_401(monkeypatch):
    updates: list[dict[str, object]] = []

    request = httpx.Request("GET", "https://example.atlassian.net/rest/api/3/myself")
    response = httpx.Response(401, request=request, text="Unauthorized")

    class FakeClient:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        def get(self, url):
            raise httpx.HTTPStatusError(
                "Unauthorized",
                request=request,
                response=response,
            )

    monkeypatch.setattr("sendsprint.api.routes.auth.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "sendsprint.api.routes.auth._capture_jira_with_browser_fallback",
        lambda **kwargs: {"sprint_id": "browser-captured", "capture_transport": "playwright"},
    )
    monkeypatch.setattr(
        "sendsprint.api.routes.auth.profile_mod.update",
        lambda **kwargs: updates.append(kwargs),
    )

    resp = client.post(
        "/auth/jira",
        json={
            "base_url": "https://example.atlassian.net",
            "email": "dev@example.com",
            "api_token": "bad-token",
            "sprint_url": "https://example.atlassian.net/jira/software/projects/APP/boards/1",
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["fallback_used"] is True
    assert body["capture_transport"] == "playwright"
    assert updates[0]["jira.last_sprint_url"] == "https://example.atlassian.net/jira/software/projects/APP/boards/1"


def test_list_jira_sprints_uses_profile_context(monkeypatch):
    for var in ("JIRA_BASE_URL", "JIRA_EMAIL", "JIRA_API_TOKEN"):
        monkeypatch.delenv(var, raising=False)

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "values": [
                    {
                        "id": 131,
                        "name": "Sprint 131",
                        "state": "active",
                        "goal": "Ship auth shell",
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
            assert url.endswith("/rest/agile/1.0/board/42/sprint?state=active")
            return FakeResponse()

    monkeypatch.setattr("sendsprint.api.routes.sprints.httpx.Client", FakeClient)
    monkeypatch.setattr(
        "sendsprint.api.routes.sprints.profile_mod.load",
        lambda: Profile.model_validate(
            {
                "jira": {
                    "base_url": "https://example.atlassian.net",
                    "email": "dev@example.com",
                }
            }
        ),
    )
    monkeypatch.setattr(
        "sendsprint.api.routes.sprints.credentials.get_secret",
        lambda provider, account: "cached-token",
    )

    resp = client.get("/sprints", params={"provider": "jira", "board_id": "42"})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body[0]["id"] == "131"
    assert body[0]["goal"] == "Ship auth shell"


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
    assert updates[0]["azuredevops.last_sprint_url"] == payload["sprint_url"]
    assert secrets[0][:2] == ("azuredevops", "DigitalProjects-Americas")


def test_auth_azure_allows_manual_project_context_override(monkeypatch):
    updates: list[dict[str, object]] = []
    secrets: list[tuple[str, str, str]] = []

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"name": "ManualProject"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            del args, kwargs

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

        def get(self, url):
            assert url.endswith("/_apis/projects/ManualProject?api-version=7.1")
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
            "https://myorg.visualstudio.com/ManualProject/"
            "_sprints/taskboard/MyTeam/Sprint 12"
        ),
        "organization": "myorg",
        "project": "ManualProject",
        "team": "CustomTeam",
        "pat": "redacted-test-pat",
    }
    resp = client.post("/auth/azuredevops", json=payload)

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["ado_team_path"] == "myorg/ManualProject/CustomTeam"
    assert body["ado_iteration_path"] == "ManualProject\\CustomTeam\\Sprint 12"
    assert updates[0]["azuredevops.team"] == "CustomTeam"
    assert updates[0]["azuredevops.last_sprint_url"] == payload["sprint_url"]
    assert secrets[0][:2] == ("azuredevops", "myorg")


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


def test_route_preview_exposes_task_understanding_and_low_confidence(
    monkeypatch, tmp_path: Path
) -> None:
    from sendsprint.models import Sprint, SprintItem

    class FakeJiraOperator:
        source = "jira"

        def __init__(self, *args, **kwargs):
            del args, kwargs

        def read_sprint(self, **kwargs):
            assert kwargs["sprint_id"] == "131"
            return Sprint(
                id="131",
                name="Preview Sprint",
                source="jira",
                items=[
                    SprintItem(
                        id="1",
                        key="WEB-1",
                        type="Task",
                        title="Criar tela de login",
                        status="New",
                        labels=["scope:front"],
                    ),
                    SprintItem(
                        id="2",
                        key="OPS-2",
                        type="Task",
                        title="Organize rollout notes",
                        status="New",
                    ),
                ],
            )

    workspace_path = _preview_workspace(tmp_path)
    monkeypatch.setattr("sendsprint.operators.JiraOperator", FakeJiraOperator)

    resp = client.post(
        "/runs/preview",
        json={
            "provider": "jira",
            "sprint_id": "131",
            "mode": "all",
            "workspace_path": str(workspace_path),
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["task_count"] == 2
    assert body["summary"]["selected_repo_count"] == 2
    assert body["summary"]["low_confidence_count"] == 2
    assert body["side_effects"]["push"] is False

    web_task = [t for t in body["task_understanding"] if t["item_key"] == "WEB-1"][0]
    assert web_task["scopes"] == ["front"]
    assert web_task["scope_source"] == "label"
    assert web_task["selected_repos"] == ["frontend"]
    assert web_task["confidence"] == "high"

    low_items = body["low_confidence_items"]
    assert {item["repo_name"] for item in low_items} == {"frontend", "api"}
    assert all(item["recommended_action"] for item in low_items)
    assert any(repo["reasons"] for repo in body["selected_repos"])


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


def _preview_workspace(tmp_path: Path) -> Path:
    frontend = tmp_path / "frontend"
    api = tmp_path / "api"
    frontend.mkdir()
    api.mkdir()
    (frontend / "package.json").write_text(
        '{"dependencies":{"react":"latest"}}',
        encoding="utf-8",
    )
    (api / "pyproject.toml").write_text(
        "[project]\ndependencies = ['fastapi']\n",
        encoding="utf-8",
    )
    workspace_path = tmp_path / "workspace.yaml"
    workspace_path.write_text(
        "\n".join(
            [
                "name: preview",
                f"root_path: {tmp_path.as_posix()}",
                "repos:",
                "  - name: frontend",
                "    path: frontend",
                "    role: front",
                "  - name: api",
                "    path: api",
                "    role: api",
            ]
        ),
        encoding="utf-8",
    )
    return workspace_path
