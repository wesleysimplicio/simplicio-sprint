from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace

from sendsprint.models.workspace import CodeGenerationConfig
from sendsprint.profile import RuntimeProfile
from sendsprint.runtime_bootstrap import run_operational_bootstrap


def test_operational_bootstrap_updates_mapper_and_uses_python_fallback(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        "sendsprint.runtime_bootstrap.run_doctor",
        lambda *args, **kwargs: SimpleNamespace(ok=True),
    )
    monkeypatch.setattr(
        "sendsprint.runtime_bootstrap.ensure_localhost_control_plane",
        lambda **kwargs: SimpleNamespace(
            api_url="http://127.0.0.1:8765",
            ui_url="http://localhost:8081",
            api_running=True,
            api_started=True,
            ui_running=False,
            ui_started=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr("sendsprint.runtime_bootstrap.shutil.which", lambda command: "npx")

    commands: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        commands.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    report = run_operational_bootstrap(
        tmp_path,
        runtime=RuntimeProfile(
            verify_dependencies_on_start=True,
            update_llm_project_mapper_on_start=True,
            start_dashboard_on_start=True,
            open_browser_on_start=False,
            fallback_to_python_when_web_blocked=True,
        ),
        code_generation=CodeGenerationConfig(),
        runner=fake_run,
    )

    assert report.doctor is not None
    assert report.mapper_updated is True
    assert report.python_fallback_active is True
    assert commands[0][:2] == ["npx", "-y"]


def test_operational_bootstrap_warns_when_npx_missing(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        "sendsprint.runtime_bootstrap.run_doctor",
        lambda *args, **kwargs: SimpleNamespace(ok=True),
    )
    monkeypatch.setattr("sendsprint.runtime_bootstrap.shutil.which", lambda command: None)
    monkeypatch.setattr(
        "sendsprint.runtime_bootstrap.ensure_localhost_control_plane",
        lambda **kwargs: SimpleNamespace(
            api_url="http://127.0.0.1:8765",
            ui_url="http://localhost:8081",
            api_running=False,
            api_started=False,
            ui_running=False,
            ui_started=False,
            warnings=[],
        ),
    )

    report = run_operational_bootstrap(
        tmp_path,
        runtime=RuntimeProfile(
            verify_dependencies_on_start=True,
            update_llm_project_mapper_on_start=True,
        ),
    )

    assert any(note.name == "llm-project-mapper" for note in report.notes)
