"""Preflight checks for sprint delivery safety and environment readiness."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from sendsprint.agents.story_task_planner import plan_story_tasks
from sendsprint.models import Sprint
from sendsprint.models.workspace import ScopeConfig, WorkspaceConfig
from sendsprint.operators.base import BaseOperator
from sendsprint.post_validation import validate_sprint_links
from sendsprint.scope import apply_scope
from sendsprint.workspace import resolve_repo_path

CheckStatus = Literal["ok", "warn", "failed"]


class PreflightCheck(BaseModel):
    """One preflight check result."""

    name: str
    status: CheckStatus
    message: str


class PreflightReport(BaseModel):
    """Preflight report rendered by CLI and usable in tests."""

    provider: str
    identifier: str | None = None
    transport: str | None = None
    sprint: Sprint | None = None
    checks: list[PreflightCheck] = Field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not any(check.status == "failed" for check in self.checks)

    def add(self, name: str, status: CheckStatus, message: str) -> None:
        self.checks.append(PreflightCheck(name=name, status=status, message=message))


def run_preflight(
    operator: BaseOperator,
    *,
    identifier: str | int | None = None,
    workspace: WorkspaceConfig | None = None,
    repo_path: Path | None = None,
    scope: ScopeConfig | None = None,
) -> PreflightReport:
    """Validate environment and sprint safety without mutating external systems."""
    report = PreflightReport(provider=operator.source, identifier=str(identifier or ""))

    try:
        transport = operator._resolve_transport()
        report.transport = transport
        status: CheckStatus = "warn" if transport == "playwright" else "ok"
        report.add("transport", status, f"resolved transport: {transport}")
    except Exception as exc:  # noqa: BLE001 - defensive CLI UX
        report.add("transport", "failed", f"transport resolution failed: {exc}")

    if operator._api_available():
        report.add("api-credentials", "ok", "API credentials are available")
    else:
        report.add(
            "api-credentials",
            "warn",
            "API credentials are not available; MCP or browser fallback is required",
        )

    repos = _resolve_repos(workspace, repo_path)
    if not repos:
        report.add("repos", "failed", "no repository path or workspace repos were provided")
    for name, path in repos:
        if not path.exists():
            report.add("repo-exists", "failed", f"{name}: path does not exist: {path}")
            continue
        report.add("repo-exists", "ok", f"{name}: {path}")
        _check_git(report, name, path)

    if identifier is None:
        report.add("sprint", "warn", "no sprint identifier provided; sprint content not checked")
        return report

    try:
        kwargs: dict[str, object] = (
            {"sprint_id": int(identifier)}
            if operator.source == "jira"
            else {"iteration_path": str(identifier)}
        )
        sprint = operator.read_sprint(**kwargs)  # type: ignore[arg-type]
        sprint = apply_scope(sprint, scope or ScopeConfig())
        sprint, planning = plan_story_tasks(sprint, workspace)
        report.sprint = sprint
        report.add("sprint", "ok", f"{len(sprint.items)} item(s) after scope/planning")
        if planning.message:
            report.add("planning", "ok", planning.message)
        link_validation = validate_sprint_links(sprint)
        report.add(
            "work-item-links",
            "failed" if link_validation.status == "failed" else "ok",
            link_validation.message or "work-item links checked",
        )
    except Exception as exc:  # noqa: BLE001 - preflight should report, not crash
        report.add("sprint", "failed", f"sprint read/check failed: {exc}")

    return report


def _resolve_repos(
    workspace: WorkspaceConfig | None,
    repo_path: Path | None,
) -> list[tuple[str, Path]]:
    if workspace and workspace.repos:
        return [(repo.name, resolve_repo_path(workspace, repo)) for repo in workspace.repos]
    if repo_path:
        return [(repo_path.name, repo_path.expanduser().resolve())]
    return []


def _check_git(report: PreflightReport, name: str, path: Path) -> None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=str(path),
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        report.add("git", "warn", f"{name}: git check skipped: {exc}")
        return

    if result.returncode == 0 and result.stdout.strip() == "true":
        report.add("git", "ok", f"{name}: git repository detected")
    else:
        report.add("git", "warn", f"{name}: not a git repository")
