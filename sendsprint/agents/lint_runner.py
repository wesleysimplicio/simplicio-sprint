"""LintRunner: runs linting per tech stack."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..models.reports import StepReport
from ..tech import TechFingerprint

logger = logging.getLogger(__name__)

LINT_COMMANDS: dict[str, list[str]] = {
    "angular": ["npx", "ng", "lint"],
    "react": ["npx", "eslint", ".", "--max-warnings=0"],
    "nextjs": ["npx", "eslint", ".", "--max-warnings=0"],
    "vue": ["npx", "eslint", ".", "--max-warnings=0"],
    "nestjs": ["npx", "eslint", ".", "--max-warnings=0"],
    "node": ["npx", "eslint", "."],
    "dotnet": ["dotnet", "format", "--verify-no-changes"],
    "spring": ["mvn", "checkstyle:check"],
    "java": ["mvn", "checkstyle:check"],
    "python": ["ruff", "check", "."],
    "django": ["ruff", "check", "."],
    "fastapi": ["ruff", "check", "."],
    "flask": ["ruff", "check", "."],
    "go": ["golangci-lint", "run"],
    "rust": ["cargo", "clippy", "--", "-D", "warnings"],
    "flutter": ["dart", "analyze"],
    "ruby": ["bundle", "exec", "rubocop"],
    "php": ["vendor/bin/phpcs"],
    "laravel": ["vendor/bin/phpcs"],
}


class LintRunner:
    """Runs linting for a repo based on its tech fingerprint."""

    def __init__(
        self,
        repo_path: str | Path,
        fingerprint: TechFingerprint,
        *,
        custom_command: str | None = None,
    ) -> None:
        self.repo = Path(repo_path).resolve()
        self.fp = fingerprint
        self.custom_command = custom_command

    def run(self) -> StepReport:
        report = StepReport(step=4, name="lint", repo=str(self.repo))
        report.started_at = datetime.now(tz=timezone.utc)
        report.status = "running"

        if self.custom_command:
            cmd = self.custom_command.split()
        else:
            tech = self.fp.primary_tech
            cmd_list = LINT_COMMANDS.get(tech) if tech else None
            if not cmd_list:
                report.status = "skipped"
                report.message = f"no lint command for tech={tech}"
                report.finished_at = datetime.now(tz=timezone.utc)
                return report
            cmd = list(cmd_list)

        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.repo),
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode == 0:
                report.status = "ok"
                report.message = f"{' '.join(cmd)} passed"
            else:
                report.status = "failed"
                report.message = result.stdout[:2000] or result.stderr[:2000]
        except FileNotFoundError:
            report.status = "skipped"
            report.message = f"linter not installed: {cmd[0]}"
        except subprocess.TimeoutExpired:
            report.status = "failed"
            report.message = f"timeout after 120s: {' '.join(cmd)}"

        report.finished_at = datetime.now(tz=timezone.utc)
        return report
