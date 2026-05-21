"""Desired TestRunner behavior for generated Playwright auto-flow specs."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from sendsprint.agents.test_runner import TestRunner as SendSprintTestRunner
from sendsprint.models.workspace import FrontendFlowConfig, PlaywrightAutoFlowsConfig, RepoConfig
from sendsprint.tech import TechFingerprint


def make_fp(
    repo: Path,
    *,
    techs: list[str] | None = None,
    roles: list[str] | None = None,
) -> TechFingerprint:
    return TechFingerprint(
        repo_path=str(repo),
        techs=techs or ["react"],
        roles=roles or ["front"],
        package_managers=["npm"],
    )


def write_next_routes(repo: Path) -> None:
    (repo / "app" / "dashboard").mkdir(parents=True)
    (repo / "app" / "settings").mkdir(parents=True)
    (repo / "app" / "page.tsx").write_text("export default function Home() { return null }\n")
    (repo / "app" / "dashboard" / "page.tsx").write_text(
        "export default function Dashboard() { return null }\n"
    )
    (repo / "app" / "settings" / "page.tsx").write_text(
        "export default function Settings() { return null }\n"
    )


def test_front_repo_with_discovered_routes_runs_generated_playwright_spec(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_next_routes(tmp_path)
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout='{"status":"passed"}', stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = SendSprintTestRunner(
        tmp_path, make_fp(tmp_path, techs=["react"], roles=["front"])
    ).run_e2e()

    assert report.status == "ok"
    assert captured["cmd"][:3] == ["npx", "playwright", "test"]
    generated_specs = [
        arg for arg in captured["cmd"] if arg.endswith(".spec.ts") and "sendsprint-evidence" in arg
    ]
    assert generated_specs, "front-route auto-flow should pass a generated spec to Playwright"
    spec_path = tmp_path / generated_specs[0]
    assert spec_path.exists()
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "page.goto('/')" in spec_text
    assert "page.goto('/dashboard')" in spec_text
    assert "page.goto('/settings')" in spec_text


def test_non_front_repo_skips_auto_flow_discovery(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_next_routes(tmp_path)

    def fail_if_called(cmd, **kwargs):
        raise AssertionError(f"subprocess.run should not be called for non-front auto-flow: {cmd}")

    monkeypatch.setattr(subprocess, "run", fail_if_called)

    report = SendSprintTestRunner(
        tmp_path, make_fp(tmp_path, techs=["python"], roles=["back"])
    ).run_e2e()

    assert report.status == "skipped"
    assert "auto" in (report.message or "").lower()
    assert "front" in (report.message or "").lower()


def test_repo_role_front_enables_auto_flow_even_when_fingerprint_is_not_front(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_next_routes(tmp_path)
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(
            args=cmd, returncode=0, stdout='{"status":"passed"}', stderr=""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = SendSprintTestRunner(
        tmp_path,
        make_fp(tmp_path, techs=["python"], roles=["back"]),
        repo_config=RepoConfig(name="web", path=".", role="front"),
    ).run_e2e()

    assert report.status == "ok"
    assert captured["cmd"][:3] == ["npx", "playwright", "test"]


def test_custom_e2e_command_wins_over_generated_auto_flow(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_next_routes(tmp_path)
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="custom ok", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = SendSprintTestRunner(
        tmp_path,
        make_fp(tmp_path, techs=["react"], roles=["front"]),
        custom_e2e_cmd="npm run test:e2e",
    ).run_e2e()

    assert report.status == "ok"
    assert captured["cmd"] == ["npm", "run", "test:e2e"]
    assert not list((tmp_path / "sendsprint-evidence").glob("*.spec.ts"))


def test_workspace_auto_flow_defaults_apply_when_repo_frontend_uses_defaults(
    tmp_path: Path,
) -> None:
    runner = SendSprintTestRunner(
        tmp_path,
        make_fp(tmp_path, techs=["react"], roles=["front"]),
        frontend_config=FrontendFlowConfig(),
        auto_flows_config=PlaywrightAutoFlowsConfig(timeout_seconds=45, max_routes=3),
    )

    assert runner._frontend_timeout() == 45
    assert runner._frontend_max_routes() == 3


def test_invalid_dev_server_command_returns_failed_report(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_next_routes(tmp_path)

    def fail_if_called(cmd, **kwargs):
        raise AssertionError(f"playwright should not run after dev server failure: {cmd}")

    def fake_popen(*args, **kwargs):
        raise FileNotFoundError("missing binary")

    monkeypatch.setattr(subprocess, "run", fail_if_called)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)

    report = SendSprintTestRunner(
        tmp_path,
        make_fp(tmp_path, techs=["react"], roles=["front"]),
        frontend_config=FrontendFlowConfig(dev_server_command="__missing_server_binary__"),
    ).run_e2e()

    assert report.status == "failed"
    assert "could not start frontend dev server" in (report.message or "")


def test_unready_dev_server_returns_failed_report_without_running_playwright(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_next_routes(tmp_path)

    class FakeProcess:
        def poll(self):
            return None

        def terminate(self):
            return None

        def wait(self, timeout=None):
            return 0

    def fail_if_called(cmd, **kwargs):
        raise AssertionError(f"playwright should not run before server readiness: {cmd}")

    monkeypatch.setattr(subprocess, "run", fail_if_called)
    monkeypatch.setattr(subprocess, "Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(SendSprintTestRunner, "_wait_for_base_url", lambda self, base_url: False)

    report = SendSprintTestRunner(
        tmp_path,
        make_fp(tmp_path, techs=["react"], roles=["front"]),
        frontend_config=FrontendFlowConfig(
            base_url="http://127.0.0.1:4173",
            dev_server_command="npm run dev",
        ),
    ).run_e2e()

    assert report.status == "failed"
    assert "did not become ready" in (report.message or "")


def test_generated_playwright_flow_failure_is_failed_report_with_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    write_next_routes(tmp_path)
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=1,
            stdout="",
            stderr="Error: route /settings timed out",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = SendSprintTestRunner(
        tmp_path, make_fp(tmp_path, techs=["react"], roles=["front"])
    ).run_e2e()

    assert report.status == "failed"
    assert "route /settings timed out" in (report.message or "")
    assert any(e.kind == "e2e" and not e.passed for e in report.evidence)
    assert any(arg.endswith(".spec.ts") for arg in captured["cmd"])


def test_timeout_keeps_new_screenshot_evidence(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "sendsprint-evidence").mkdir()

    def fake_run(cmd, **kwargs):
        (tmp_path / "sendsprint-evidence" / "timeout.png").write_bytes(b"png")
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

    monkeypatch.setattr(subprocess, "run", fake_run)

    report = SendSprintTestRunner(
        tmp_path,
        make_fp(tmp_path, techs=["react"], roles=["front"]),
        custom_e2e_cmd="npm run test:e2e",
    ).run_e2e()

    assert report.status == "failed"
    assert any(
        e.kind == "screenshot"
        and e.path
        and e.path.replace("\\", "/") == "sendsprint-evidence/timeout.png"
        for e in report.evidence
    )
