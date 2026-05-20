"""Readiness checks for autonomous SendSprint runs."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.models.workspace import CodeGenerationConfig
from sendsprint.tech import detect_tech
from sendsprint.templates import ValidationTemplate, select_validation_template

CheckStatus = Literal["ok", "warn", "failed"]
Runner = Callable[..., subprocess.CompletedProcess[str]]


class DoctorCheck(BaseModel):
    """One readiness check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    status: CheckStatus
    message: str
    remediation: str | None = None


class DoctorReport(BaseModel):
    """Structured output for `sendsprint doctor`."""

    model_config = ConfigDict(extra="forbid")

    repo_path: str
    checks: list[DoctorCheck] = Field(default_factory=list)
    template: ValidationTemplate | None = None

    @property
    def ok(self) -> bool:
        return not any(check.status == "failed" for check in self.checks)

    def add(
        self,
        name: str,
        status: CheckStatus,
        message: str,
        remediation: str | None = None,
    ) -> None:
        self.checks.append(
            DoctorCheck(name=name, status=status, message=message, remediation=remediation)
        )


def run_doctor(
    repo_path: str | Path,
    *,
    workspace_file: str | Path | None = None,
    code_generation: CodeGenerationConfig | None = None,
    runner: Runner = subprocess.run,
) -> DoctorReport:
    """Run local readiness checks without mutating the repo."""
    repo = Path(repo_path).expanduser().resolve()
    report = DoctorReport(repo_path=str(repo))

    if not repo.exists():
        report.add("repo-exists", "failed", f"path does not exist: {repo}")
        return report
    report.add("repo-exists", "ok", f"found {repo}")

    if not (repo / ".git").exists():
        report.add("git-repo", "failed", "not a git repository", "run inside a git repo")
    else:
        report.add("git-repo", "ok", "git repository detected")
        _check_git_clean_and_sync(report, repo, runner)

    if workspace_file:
        ws = Path(workspace_file).expanduser().resolve()
        if ws.exists():
            report.add("workspace", "ok", f"workspace file found: {ws}")
        else:
            report.add("workspace", "failed", f"workspace file missing: {ws}")
    elif (repo / "workspace.yaml").exists():
        report.add("workspace", "ok", "workspace.yaml found")
    else:
        report.add("workspace", "warn", "no workspace file provided; single-repo mode assumed")

    _check_command(report, "git", "install git")
    _check_gh(report, runner)
    _check_python(report)
    _check_node_toolchain(report, repo)
    _check_playwright(report, repo, runner)
    _check_llm(report, code_generation or CodeGenerationConfig())

    fp = detect_tech(repo)
    template = select_validation_template(fp, repo)
    report.template = template
    report.add(
        "validation-template",
        "ok",
        f"matched {template.name}: {', '.join(template.commands()[:4])}",
    )
    return report


def _check_command(report: DoctorReport, command: str, remediation: str) -> None:
    if shutil.which(command):
        report.add(command, "ok", f"{command} available")
    else:
        report.add(command, "failed", f"{command} not found on PATH", remediation)


def _check_git_clean_and_sync(report: DoctorReport, repo: Path, runner: Runner) -> None:
    status = _run(runner, ["git", "status", "--porcelain"], repo)
    if status.returncode != 0:
        report.add("git-status", "failed", status.stderr.strip() or "git status failed")
        return
    if status.stdout.strip():
        report.add("git-clean", "warn", "working tree has local changes")
    else:
        report.add("git-clean", "ok", "working tree clean")

    upstream = _run(
        runner,
        ["git", "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
        repo,
    )
    if upstream.returncode != 0:
        report.add("git-upstream", "warn", "no upstream configured")
        return
    counts = _run(runner, ["git", "rev-list", "--left-right", "--count", "HEAD...@{u}"], repo)
    if counts.returncode != 0:
        report.add("git-sync", "warn", counts.stderr.strip() or "cannot compare upstream")
        return
    ahead, behind = (counts.stdout.strip().split() + ["0", "0"])[:2]
    if ahead == "0" and behind == "0":
        report.add("git-sync", "ok", "branch is synchronized with upstream")
    else:
        report.add(
            "git-sync",
            "warn",
            f"branch differs from upstream: ahead={ahead} behind={behind}",
        )


def _check_gh(report: DoctorReport, runner: Runner) -> None:
    if not shutil.which("gh"):
        report.add("github-auth", "failed", "gh not found", "install GitHub CLI and authenticate")
        return
    result = _run(runner, ["gh", "auth", "status"], Path.cwd())
    if result.returncode == 0:
        report.add("github-auth", "ok", "GitHub CLI authenticated")
    else:
        report.add("github-auth", "failed", "GitHub CLI is not authenticated", "run gh auth login")


def _check_python(report: DoctorReport) -> None:
    report.add("python", "ok", f"Python runtime: {sys.executable}")


def _check_node_toolchain(report: DoctorReport, repo: Path) -> None:
    package_roots = [repo]
    web_root = repo / "web"
    if web_root.exists():
        package_roots.append(web_root)
    if not any((root / "package.json").exists() for root in package_roots):
        return
    _check_command(report, "node", "install Node.js")
    _check_command(report, "npm", "install Node.js/npm")
    _check_command(report, "npx", "install Node.js/npm")
    if (web_root / "package.json").exists() and not (web_root / "node_modules").exists():
        report.add(
            "web-node-modules",
            "warn",
            "web/node_modules missing",
            "run `cd web && npm install`",
        )


def _check_playwright(report: DoctorReport, repo: Path, runner: Runner) -> None:
    if not (repo / "package.json").exists():
        report.add("playwright", "warn", "no package.json; browser checks may not apply")
        return
    result = _run(runner, ["npx", "playwright", "--version"], repo)
    if result.returncode == 0:
        report.add("playwright", "ok", result.stdout.strip() or "Playwright available")
    else:
        report.add(
            "playwright",
            "warn",
            "Playwright not available",
            "run npm install and npx playwright install",
        )


def _check_llm(report: DoctorReport, config: CodeGenerationConfig) -> None:
    if not config.enabled:
        report.add("llm-codegen", "ok", "LLM code generation disabled")
        return
    provider = config.provider or "anthropic"
    env_var = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
        "groq": "GROQ_API_KEY",
        "ollama": "",
    }.get(provider, "")
    if provider == "ollama" or (env_var and os.getenv(env_var)):
        report.add("llm-codegen", "ok", f"{provider} configured with budget ${config.max_usd:g}")
    else:
        report.add("llm-codegen", "failed", f"{provider} API key missing", f"set {env_var}")


def _run(runner: Runner, cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return runner(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))
