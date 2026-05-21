"""Tests for the localhost web control plane API endpoints (issue #102)."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

from sendsprint.api.server import app
from tests.api_client import AuthenticatedTestClient

client = AuthenticatedTestClient(app)


# ---------------------------------------------------------------------------
# GET /api/runs — list runs
# ---------------------------------------------------------------------------


def test_list_runs_empty_initially():
    """Listing before any run starts returns a list (may have runs from other tests)."""
    resp = client.get("/api/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_list_runs_contains_started_run():
    payload = {
        "provider": "jira",
        "sprint_id": "cp-100",
        "mode": "all",
        "item_keys": ["CP-1", "CP-2"],
    }
    start_resp = client.post("/api/runs", json=payload)
    assert start_resp.status_code == 200
    run_id = start_resp.json()["run_id"]

    _wait_for_state(run_id, {"running", "done"})

    resp = client.get("/api/runs")
    assert resp.status_code == 200
    runs = resp.json()
    ids = [r["run_id"] for r in runs]
    assert run_id in ids

    matching = [r for r in runs if r["run_id"] == run_id][0]
    assert matching["sprint_id"] == "cp-100"
    assert matching["provider"] == "jira"
    assert "autonomy_level" in matching
    assert "readiness_score" in matching
    assert "readiness_verdict" in matching


# ---------------------------------------------------------------------------
# POST /api/runs — start run
# ---------------------------------------------------------------------------


def test_start_run_returns_run_id():
    payload = {
        "provider": "jira",
        "sprint_id": "cp-200",
        "item_keys": ["DEMO-A"],
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"]
    assert body["status"] == "started"


def test_start_run_with_autonomy_level():
    payload = {
        "provider": "jira",
        "sprint_id": "cp-201",
        "autonomy_level": "execute",
    }
    resp = client.post("/api/runs", json=payload)
    assert resp.status_code == 200
    assert resp.json()["run_id"]


def test_start_run_materializes_workspace_from_project_setup(monkeypatch):
    captured = {}

    class FakeStatus:
        run_id = "cp-workspace"

    def fake_start_run(req):
        captured["request"] = req
        return FakeStatus()

    monkeypatch.setattr(
        "sendsprint.api.routes.control_plane.materialize_workspace_from_project_setup",
        lambda project_setup: "generated-workspace.json",
    )
    monkeypatch.setattr("sendsprint.api.routes.control_plane.manager.start_run", fake_start_run)

    resp = client.post(
        "/api/runs",
        json={
            "provider": "jira",
            "sprint_id": "cp-202",
            "project_setup": {
                "deployTargetBranch": "dev",
                "repositories": [
                    {
                        "name": "web",
                        "repoPath": "C:/workspace/web",
                        "role": "frontend",
                        "project": "Portal",
                    }
                ]
            },
        },
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["run_id"] == "cp-workspace"
    assert captured["request"].workspace_path == "generated-workspace.json"
    assert captured["request"].repo_path is None


def test_control_plane_preview_is_read_only_and_filterable(monkeypatch, tmp_path: Path) -> None:
    from sendsprint.api.runs import manager
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
                        key="API-2",
                        type="Task",
                        title="Implement backend endpoint",
                        status="New",
                    ),
                ],
            )

    workspace_path = _preview_workspace(tmp_path)
    monkeypatch.setattr("sendsprint.operators.JiraOperator", FakeJiraOperator)
    before = len(manager.list_runs())

    resp = client.post(
        "/api/runs/preview",
        json={
            "provider": "jira",
            "sprint_id": "131",
            "mode": "selected",
            "item_keys": ["API-2"],
            "workspace_path": str(workspace_path),
        },
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(manager.list_runs()) == before
    assert body["item_keys"] == ["API-2"]
    assert [task["item_key"] for task in body["task_understanding"]] == ["API-2"]
    assert body["selected_repos"][0]["repo_name"] == "api"
    assert body["selected_repos"][0]["confidence"] == "high"
    assert body["low_confidence_items"] == []


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id} — run detail
# ---------------------------------------------------------------------------


def test_get_run_detail_404():
    resp = client.get("/api/runs/nonexistent-id")
    assert resp.status_code == 404


def test_get_run_detail_has_quality_and_evidence():
    payload = {
        "provider": "jira",
        "sprint_id": "cp-300",
        "item_keys": ["QA-1"],
    }
    start_resp = client.post("/api/runs", json=payload)
    run_id = start_resp.json()["run_id"]

    _wait_for_state(run_id, {"done", "failed"}, timeout=15.0)

    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()

    # run summary
    assert body["run"]["run_id"] == run_id
    assert body["run"]["state"] in {"done", "failed"}
    assert body["run"]["readiness_score"] is not None

    # quality gate
    assert body["quality_gate"] is not None
    assert body["quality_gate"]["run_id"] == run_id
    assert body["quality_gate"]["verdict"] in {
        "pass",
        "needs_rework",
        "needs_human_approval",
        "pending",
    }

    # logs
    assert isinstance(body["logs"], list)

    # timeline
    assert isinstance(body["timeline"], list)
    assert len(body["timeline"]) > 0


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/evidence
# ---------------------------------------------------------------------------


def test_evidence_404_for_missing_run():
    resp = client.get("/api/runs/ghost/evidence")
    assert resp.status_code == 404


def test_evidence_returns_bundle_after_run():
    payload = {
        "provider": "jira",
        "sprint_id": "cp-400",
        "item_keys": ["EV-1"],
    }
    start_resp = client.post("/api/runs", json=payload)
    run_id = start_resp.json()["run_id"]

    _wait_for_state(run_id, {"done", "failed"}, timeout=15.0)

    resp = client.get(f"/api/runs/{run_id}/evidence")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_id
    assert isinstance(body["items"], list)
    assert body["total_items"] >= 0


# ---------------------------------------------------------------------------
# GET /api/runs/{run_id}/quality
# ---------------------------------------------------------------------------


def test_quality_404_for_missing_run():
    resp = client.get("/api/runs/ghost/quality")
    assert resp.status_code == 404


def test_quality_returns_gate_report_after_run():
    payload = {
        "provider": "jira",
        "sprint_id": "cp-500",
        "item_keys": ["QG-1"],
    }
    start_resp = client.post("/api/runs", json=payload)
    run_id = start_resp.json()["run_id"]

    _wait_for_state(run_id, {"done", "failed"}, timeout=15.0)

    resp = client.get(f"/api/runs/{run_id}/quality")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_id
    assert body["verdict"] in {
        "pass",
        "needs_rework",
        "needs_human_approval",
        "pending",
    }
    assert isinstance(body["checks"], list)
    assert isinstance(body["reasons"], list)


# ---------------------------------------------------------------------------
# Readiness score integration
# ---------------------------------------------------------------------------


def test_done_run_has_readiness_100():
    payload = {
        "provider": "jira",
        "sprint_id": "cp-600",
        "item_keys": ["RS-1"],
    }
    start_resp = client.post("/api/runs", json=payload)
    run_id = start_resp.json()["run_id"]

    _wait_for_state(run_id, {"done"}, timeout=15.0)

    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run"]["readiness_score"] == 100.0
    assert body["run"]["readiness_verdict"] == "auto_publish"


def test_failed_run_has_readiness_zero():
    """A failed run should have readiness_score 0."""
    payload = {
        "provider": "jira",
        "sprint_id": "cp-700",
        "item_keys": ["FAIL-1"],
    }
    start_resp = client.post("/api/runs", json=payload)
    run_id = start_resp.json()["run_id"]

    _wait_for_state(run_id, {"done", "failed"}, timeout=15.0)

    resp = client.get(f"/api/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    if body["run"]["state"] == "failed":
        assert body["run"]["readiness_score"] == 0.0
        assert body["run"]["readiness_verdict"] == "blocked"


# ---------------------------------------------------------------------------
# CLI web command
# ---------------------------------------------------------------------------


def test_cli_web_command_registered():
    """The 'web' command is registered in the CLI app."""
    from typer.testing import CliRunner

    from sendsprint.cli import app as cli_app

    runner = CliRunner()
    result = runner.invoke(cli_app, ["web", "--help"])
    assert result.exit_code == 0
    assert "port" in result.output.lower()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _wait_for_state(run_id: str, target_states: set[str], timeout: float = 10.0) -> dict:
    """Poll /api/runs/{run_id} until state is in target_states."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        resp = client.get(f"/api/runs/{run_id}")
        if resp.status_code == 200:
            body = resp.json()
            state = body.get("run", {}).get("state") or body.get("state")
            if state in target_states:
                return body
        time.sleep(0.15)
    return resp.json() if resp.status_code == 200 else {}


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
