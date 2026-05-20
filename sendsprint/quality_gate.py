"""Central delivery quality gate — consolidates lint, tests, security, coverage,
Playwright, and diff-hygiene checks into a single pass/rework/human-approval
verdict before publish and closeout.

Issue: #93
"""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.evidence import BundleManager, EvidenceBundle, EvidenceItemType
from sendsprint.policy import AutonomyPolicy

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class CheckSeverity(StrEnum):
    """How critical a failing check is."""

    info = "info"
    warning = "warning"
    error = "error"
    blocking = "blocking"


class QualityCheckResult(BaseModel):
    """Result of a single quality check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    check_name: str
    passed: bool
    details: str = ""
    severity: CheckSeverity = CheckSeverity.error
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GateVerdict(StrEnum):
    """Outcome produced by the delivery quality gate."""

    passed = "pass"
    needs_rework = "needs_rework"
    needs_human_approval = "needs_human_approval"


class GateReport(BaseModel):
    """Full report produced by :class:`DeliveryQualityGate`."""

    model_config = ConfigDict(extra="forbid")

    verdict: GateVerdict
    checks: list[QualityCheckResult] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Diff-hygiene helpers
# ---------------------------------------------------------------------------

_DIFF_DIRTY_MARKERS = (
    "<<<<<<< ",
    ">>>>>>> ",
    "======= ",
    "TODO: remove",
    "FIXME: hack",
    "console.log(",
    "debugger;",
    "binding.pry",
    "import pdb",
)


def _scan_diff_hygiene(changed_files: list[str], repo_root: str | Path = ".") -> QualityCheckResult:
    """Check changed files for conflict markers, debug leftovers, etc."""
    root = Path(repo_root).expanduser().resolve()
    dirty: list[str] = []
    for relpath in changed_files:
        filepath = root / relpath
        if not filepath.is_file():
            continue
        try:
            text = filepath.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for marker in _DIFF_DIRTY_MARKERS:
            if marker in text:
                dirty.append(f"{relpath}: contains '{marker.strip()}'")
    if dirty:
        return QualityCheckResult(
            check_name="diff-hygiene",
            passed=False,
            details="; ".join(dirty[:10]),
            severity=CheckSeverity.blocking,
        )
    return QualityCheckResult(
        check_name="diff-hygiene",
        passed=True,
        details="no conflict markers or debug leftovers found",
    )


# ---------------------------------------------------------------------------
# Command runner helper
# ---------------------------------------------------------------------------


def _run_command(
    cmd: str,
    *,
    cwd: str | Path = ".",
    timeout: int = 120,
) -> tuple[bool, str]:
    """Run a shell command and return (success, combined_output)."""
    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=str(cwd),
            timeout=timeout,
        )
        output = (result.stdout + "\n" + result.stderr).strip()
        return result.returncode == 0, output
    except subprocess.TimeoutExpired:
        return False, f"command timed out after {timeout}s: {cmd}"
    except OSError as exc:
        return False, f"command failed to start: {exc}"


# ---------------------------------------------------------------------------
# DeliveryQualityGate
# ---------------------------------------------------------------------------


class DeliveryQualityGate:
    """Central quality gate that aggregates all checks and produces a verdict.

    Parameters
    ----------
    repo_root:
        Working directory for subprocess commands.
    changed_files:
        List of file paths (relative to *repo_root*) changed in the delivery.
    policy:
        Autonomy policy — used to decide whether human review is forced.
    lint_cmd:
        Shell command for lint (default ``ruff check .``).
    test_cmd:
        Shell command for tests (default ``pytest tests -q``).
    security_cmd:
        Shell command for security scanning (default ``bandit -r . -q``).
    coverage_threshold:
        Minimum coverage percentage to pass (default ``80``).
    playwright_cmd:
        Shell command for Playwright E2E (optional).
    """

    def __init__(
        self,
        *,
        repo_root: str | Path = ".",
        changed_files: list[str] | None = None,
        policy: AutonomyPolicy | None = None,
        lint_cmd: str = "ruff check .",
        test_cmd: str = "pytest tests -q",
        security_cmd: str = "bandit -r . -q",
        coverage_threshold: int = 80,
        playwright_cmd: str | None = None,
    ) -> None:
        self.repo_root = Path(repo_root).expanduser().resolve()
        self.changed_files = changed_files or []
        self.policy = policy or AutonomyPolicy(level="plan")
        self.lint_cmd = lint_cmd
        self.test_cmd = test_cmd
        self.security_cmd = security_cmd
        self.coverage_threshold = coverage_threshold
        self.playwright_cmd = playwright_cmd

    # -- individual checks ---------------------------------------------------

    def check_lint(self) -> QualityCheckResult:
        ok, output = _run_command(self.lint_cmd, cwd=self.repo_root)
        return QualityCheckResult(
            check_name="lint",
            passed=ok,
            details=output[:500] if not ok else "lint passed",
            severity=CheckSeverity.error if not ok else CheckSeverity.info,
        )

    def check_tests(self) -> QualityCheckResult:
        ok, output = _run_command(self.test_cmd, cwd=self.repo_root)
        return QualityCheckResult(
            check_name="tests",
            passed=ok,
            details=output[:500] if not ok else "tests passed",
            severity=CheckSeverity.blocking if not ok else CheckSeverity.info,
        )

    def check_security(self) -> QualityCheckResult:
        ok, output = _run_command(self.security_cmd, cwd=self.repo_root)
        return QualityCheckResult(
            check_name="security",
            passed=ok,
            details=output[:500] if not ok else "no security issues found",
            severity=CheckSeverity.blocking if not ok else CheckSeverity.info,
        )

    def check_coverage(self) -> QualityCheckResult:
        """Run tests with coverage and verify the threshold is met."""
        cmd = f"pytest tests --cov --cov-report=term -q --cov-fail-under={self.coverage_threshold}"
        ok, output = _run_command(cmd, cwd=self.repo_root)
        return QualityCheckResult(
            check_name="coverage",
            passed=ok,
            details=output[:500] if not ok else f"coverage >= {self.coverage_threshold}%",
            severity=CheckSeverity.warning if not ok else CheckSeverity.info,
        )

    def check_playwright(self) -> QualityCheckResult:
        """Run Playwright E2E tests if a command is configured."""
        if not self.playwright_cmd:
            return QualityCheckResult(
                check_name="playwright",
                passed=True,
                details="playwright check skipped (no command configured)",
                severity=CheckSeverity.info,
            )
        ok, output = _run_command(self.playwright_cmd, cwd=self.repo_root)
        return QualityCheckResult(
            check_name="playwright",
            passed=ok,
            details=output[:500] if not ok else "playwright tests passed",
            severity=CheckSeverity.error if not ok else CheckSeverity.info,
        )

    def check_diff_hygiene(self) -> QualityCheckResult:
        return _scan_diff_hygiene(self.changed_files, self.repo_root)

    # -- aggregate -----------------------------------------------------------

    def run_all_checks(self) -> list[QualityCheckResult]:
        """Run every configured check and return all results."""
        return [
            self.check_lint(),
            self.check_tests(),
            self.check_security(),
            self.check_coverage(),
            self.check_playwright(),
            self.check_diff_hygiene(),
        ]

    # -- verdict -------------------------------------------------------------

    def evaluate(self, checks: list[QualityCheckResult] | None = None) -> GateReport:
        """Run checks (if not supplied) and produce a :class:`GateReport`.

        Decision logic:
        - Any *blocking* failure -> ``needs_rework``
        - Any *error* failure -> ``needs_rework``
        - Any *warning* failure AND policy requires human review -> ``needs_human_approval``
        - Any *warning* failure AND policy does NOT require human review -> ``pass`` (with reasons)
        - All pass -> ``pass``
        """
        results = checks if checks is not None else self.run_all_checks()
        reasons: list[str] = []
        has_blocking = False
        has_error = False
        has_warning = False

        for check in results:
            if check.passed:
                continue
            reasons.append(f"{check.check_name}: {check.details[:120]}")
            if check.severity == CheckSeverity.blocking:
                has_blocking = True
            elif check.severity == CheckSeverity.error:
                has_error = True
            elif check.severity == CheckSeverity.warning:
                has_warning = True

        if has_blocking or has_error:
            verdict = GateVerdict.needs_rework
        elif has_warning and self.policy.require_human_review:
            verdict = GateVerdict.needs_human_approval
        else:
            verdict = GateVerdict.passed

        return GateReport(verdict=verdict, checks=results, reasons=reasons)

    # -- evidence integration ------------------------------------------------

    def persist_to_bundle(
        self,
        report: GateReport,
        bundle: EvidenceBundle,
        manager: BundleManager,
    ) -> None:
        """Persist the gate verdict into an evidence bundle."""
        summary_lines = [f"verdict: {report.verdict.value}"]
        for reason in report.reasons:
            summary_lines.append(f"  - {reason}")
        content = "\n".join(summary_lines)
        manager.add_item(
            bundle,
            item_type=EvidenceItemType.decision,
            content=content,
            metadata={
                "gate_verdict": report.verdict.value,
                "checks_total": len(report.checks),
                "checks_passed": sum(1 for c in report.checks if c.passed),
                "checks_failed": sum(1 for c in report.checks if not c.passed),
            },
        )
