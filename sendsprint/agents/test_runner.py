"""TestRunner: unit + E2E (Playwright) with screenshot evidence."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..models.reports import StepReport, TestEvidence
from ..tech import TechFingerprint

logger = logging.getLogger(__name__)

UNIT_COMMANDS: dict[str, list[str]] = {
    "angular": ["npx", "ng", "test", "--watch=false", "--browsers=ChromeHeadless"],
    "react": ["npx", "react-scripts", "test", "--watchAll=false"],
    "nextjs": ["npm", "test", "--", "--passWithNoTests"],
    "vue": ["npm", "test", "--", "--run"],
    "nestjs": ["npm", "test"],
    "node": ["npm", "test"],
    "dotnet": ["dotnet", "test"],
    "spring": ["mvn", "test"],
    "java": ["mvn", "test"],
    "python": ["pytest", "--tb=short", "-q"],
    "django": ["python", "manage.py", "test"],
    "fastapi": ["pytest", "--tb=short", "-q"],
    "flask": ["pytest", "--tb=short", "-q"],
    "go": ["go", "test", "./..."],
    "rust": ["cargo", "test"],
    "flutter": ["flutter", "test"],
    "ruby": ["bundle", "exec", "rspec"],
    "php": ["vendor/bin/phpunit"],
    "laravel": ["vendor/bin/phpunit"],
}

E2E_COMMANDS: dict[str, list[str]] = {
    "angular": ["npx", "playwright", "test"],
    "react": ["npx", "playwright", "test"],
    "nextjs": ["npx", "playwright", "test"],
    "vue": ["npx", "playwright", "test"],
    "nestjs": ["npx", "playwright", "test"],
    "node": ["npx", "playwright", "test"],
    "dotnet": ["dotnet", "test", "--filter", "Category=E2E"],
    "flutter": ["flutter", "test", "integration_test"],
}

SCREENSHOT_DIR = "sendsprint-evidence"


class TestRunner:
    """Runs unit tests + Playwright E2E with screenshot capture."""

    def __init__(
        self,
        repo_path: str | Path,
        fingerprint: TechFingerprint,
        *,
        custom_unit_cmd: str | None = None,
        custom_e2e_cmd: str | None = None,
    ) -> None:
        self.repo = Path(repo_path).resolve()
        self.fp = fingerprint
        self.custom_unit_cmd = custom_unit_cmd
        self.custom_e2e_cmd = custom_e2e_cmd
        self.evidence_dir = self.repo / SCREENSHOT_DIR
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def run_unit(self) -> StepReport:
        report = StepReport(step=5, name="unit-tests", repo=str(self.repo))
        report.status = "running"
        if self.custom_unit_cmd:
            cmd = self.custom_unit_cmd.split()
        else:
            tech = self.fp.primary_tech
            cmd_list = UNIT_COMMANDS.get(tech) if tech else None
            if not cmd_list:
                report.status = "skipped"
                report.message = f"no unit test command for tech={tech}"
                return report
            cmd = list(cmd_list)
        return self._exec(cmd, report, kind="unit")

    def run_e2e(self) -> StepReport:
        report = StepReport(step=5, name="e2e-tests", repo=str(self.repo))
        report.status = "running"
        if self.custom_e2e_cmd:
            cmd = self.custom_e2e_cmd.split()
        else:
            tech = self.fp.primary_tech
            cmd_list = E2E_COMMANDS.get(tech) if tech else None
            if not cmd_list:
                report.status = "skipped"
                report.message = f"no e2e command for tech={tech}"
                return report
            cmd = list(cmd_list)
        pw_args = ["--reporter=json", f"--output={self.evidence_dir}"]
        if cmd[0] == "npx" and cmd[1] == "playwright":
            cmd.extend(pw_args)
        return self._exec(cmd, report, kind="e2e")

    def run_all(self) -> list[StepReport]:
        return [self.run_unit(), self.run_e2e()]

    def _exec(
        self, cmd: list[str], report: StepReport, *, kind: str
    ) -> StepReport:
        report.started_at = datetime.now(tz=timezone.utc)
        try:
            result = subprocess.run(
                cmd,
                cwd=str(self.repo),
                capture_output=True,
                text=True,
                timeout=600,
            )
            passed = result.returncode == 0
            report.status = "ok" if passed else "failed"
            report.message = (
                result.stdout[:3000] if passed else result.stderr[:3000] or result.stdout[:3000]
            )
            report.evidence.append(
                TestEvidence(
                    kind=kind,  # type: ignore[arg-type]
                    title=f"{kind} tests",
                    passed=passed,
                    message=report.message,
                )
            )
            self._collect_screenshots(report)
        except FileNotFoundError:
            report.status = "failed"
            report.message = f"command not found: {cmd[0]}"
        except subprocess.TimeoutExpired:
            report.status = "failed"
            report.message = f"timeout after 600s: {' '.join(cmd)}"
        report.finished_at = datetime.now(tz=timezone.utc)
        return report

    def _collect_screenshots(self, report: StepReport) -> None:
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            for f in self.evidence_dir.rglob(ext):
                report.evidence.append(
                    TestEvidence(
                        kind="screenshot",
                        title=f.name,
                        passed=report.status == "ok",
                        path=str(f.relative_to(self.repo)),
                    )
                )
