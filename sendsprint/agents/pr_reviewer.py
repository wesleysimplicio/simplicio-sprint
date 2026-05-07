"""PrReviewer: automated PR review via diff analysis + static checks."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..models.reports import StepReport, TestEvidence

logger = logging.getLogger(__name__)


class PrReviewer:
    """Step 10: review PR diff, flag issues, report findings."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo = Path(repo_path).resolve()

    def review(self, source_branch: str, target_branch: str = "main") -> StepReport:
        report = StepReport(step=10, name="pr-review", repo=str(self.repo))
        report.started_at = datetime.now(tz=timezone.utc)
        report.status = "running"

        diff = self._get_diff(source_branch, target_branch)
        if not diff:
            report.status = "ok"
            report.message = "no diff between branches"
            report.finished_at = datetime.now(tz=timezone.utc)
            return report

        issues = self._static_checks(diff)
        report.evidence.append(
            TestEvidence(
                kind="log",
                title="diff-summary",
                passed=len(issues) == 0,
                message=f"{len(diff.splitlines())} lines changed, {len(issues)} issue(s)",
            )
        )
        for issue in issues:
            report.evidence.append(
                TestEvidence(
                    kind="log",
                    title=issue["rule"],
                    passed=False,
                    message=issue["message"],
                )
            )

        report.status = "ok" if not issues else "failed"
        report.message = f"{len(issues)} review issue(s) found"
        report.finished_at = datetime.now(tz=timezone.utc)
        return report

    def _get_diff(self, source: str, target: str) -> str:
        try:
            result = subprocess.run(
                ["git", "diff", f"{target}...{source}"],
                cwd=str(self.repo),
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.stdout
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return ""

    def _static_checks(self, diff: str) -> list[dict[str, str]]:
        issues: list[dict[str, str]] = []
        lines = diff.splitlines()
        for i, line in enumerate(lines):
            if not line.startswith("+") or line.startswith("+++"):
                continue
            code = line[1:]
            if "TODO" in code or "FIXME" in code or "HACK" in code:
                issues.append({
                    "rule": "todo-marker",
                    "message": f"line {i + 1}: unresolved TODO/FIXME/HACK",
                })
            debug_patterns = [
                "console.log(", "console.debug(", "debugger",
                "binding.pry", "byebug", "import pdb", "pdb.set_trace(",
                "breakpoint()", "System.out.println(",
                "dd(", "dump(",
            ]
            if any(p in code for p in debug_patterns):
                if not ("logger" in code or "logging" in code):
                    issues.append({
                        "rule": "debug-statement",
                        "message": f"line {i + 1}: debug statement in diff",
                    })
            if len(code) > 200:
                issues.append({
                    "rule": "long-line",
                    "message": f"line {i + 1}: line exceeds 200 chars",
                })
            if code.startswith("<<<<<<<") or code.startswith(">>>>>>>") or code.startswith("======="):
                issues.append({
                    "rule": "merge-conflict",
                    "message": f"line {i + 1}: unresolved merge conflict marker",
                })
        return issues
