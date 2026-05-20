"""Operational bootstrap for SendSprint local runs."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from sendsprint.doctor import DoctorReport, Runner, run_doctor
from sendsprint.models.workspace import CodeGenerationConfig
from sendsprint.profile import RuntimeProfile
from sendsprint.web_runtime import LocalhostRuntimeStatus, ensure_localhost_control_plane


@dataclass(slots=True)
class BootstrapNote:
    name: str
    status: str
    message: str


@dataclass(slots=True)
class OperationalBootstrapReport:
    repo_path: Path
    doctor: DoctorReport | None = None
    dashboard: LocalhostRuntimeStatus | None = None
    mapper_updated: bool = False
    python_fallback_active: bool = False
    notes: list[BootstrapNote] = field(default_factory=list)


def run_operational_bootstrap(
    repo_path: str | Path,
    *,
    workspace_file: str | Path | None = None,
    runtime: RuntimeProfile,
    code_generation: CodeGenerationConfig | None = None,
    runner: Runner = subprocess.run,
) -> OperationalBootstrapReport:
    """Prepare the local runtime without blocking the main delivery loop."""
    repo = Path(repo_path).expanduser().resolve()
    report = OperationalBootstrapReport(repo_path=repo)

    if runtime.verify_dependencies_on_start:
        report.doctor = run_doctor(
            repo,
            workspace_file=workspace_file,
            code_generation=code_generation,
            runner=runner,
        )
        report.notes.append(
            BootstrapNote(
                name="doctor",
                status="ok" if report.doctor.ok else "warn",
                message="dependency checks passed"
                if report.doctor.ok
                else "dependency checks need attention",
            )
        )

    if runtime.update_llm_project_mapper_on_start:
        _update_llm_project_mapper(report, runner=runner)

    if runtime.start_dashboard_on_start:
        status = ensure_localhost_control_plane(open_browser=runtime.open_browser_on_start)
        report.dashboard = status
        if (
            runtime.fallback_to_python_when_web_blocked
            and not status.ui_running
            and (status.api_running or status.api_started)
        ):
            report.python_fallback_active = True
            report.notes.append(
                BootstrapNote(
                    name="dashboard-fallback",
                    status="warn",
                    message="web UI unavailable; continuing with Python API/runtime only",
                )
            )
    return report


def _update_llm_project_mapper(report: OperationalBootstrapReport, *, runner: Runner) -> None:
    if not shutil.which("npx"):
        report.notes.append(
            BootstrapNote(
                name="llm-project-mapper",
                status="warn",
                message="npx not found; skipping llm-project-mapper update",
            )
        )
        return
    result = runner(
        ["npx", "-y", "@wesleysimplicio/llm-project-mapper@latest", "--update"],
        cwd=str(report.repo_path),
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if result.returncode == 0:
        report.mapper_updated = True
        report.notes.append(
            BootstrapNote(
                name="llm-project-mapper",
                status="ok",
                message="llm-project-mapper updated",
            )
        )
        return
    message = (result.stderr or result.stdout).strip() or "llm-project-mapper update failed"
    report.notes.append(
        BootstrapNote(
            name="llm-project-mapper",
            status="warn",
            message=message[:500],
        )
    )
