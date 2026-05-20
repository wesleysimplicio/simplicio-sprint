"""Tests for the central DeliveryQualityGate (#93)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from sendsprint.evidence import BundleManager, EvidenceItemType
from sendsprint.policy import AutonomyPolicy
from sendsprint.quality_gate import (
    CheckSeverity,
    DeliveryQualityGate,
    GateReport,
    GateVerdict,
    QualityCheckResult,
    _scan_diff_hygiene,
)

# ---------------------------------------------------------------------------
# QualityCheckResult model
# ---------------------------------------------------------------------------


class TestQualityCheckResult:
    def test_passing_check(self) -> None:
        r = QualityCheckResult(check_name="lint", passed=True, details="ok")
        assert r.passed is True
        assert r.severity == CheckSeverity.error  # default

    def test_failing_check_with_severity(self) -> None:
        r = QualityCheckResult(
            check_name="tests",
            passed=False,
            details="2 failed",
            severity=CheckSeverity.blocking,
        )
        assert r.passed is False
        assert r.severity == CheckSeverity.blocking

    def test_frozen(self) -> None:
        r = QualityCheckResult(check_name="x", passed=True)
        with pytest.raises(ValueError):
            r.passed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# GateVerdict enum values
# ---------------------------------------------------------------------------


class TestGateVerdict:
    def test_values(self) -> None:
        assert GateVerdict.passed.value == "pass"
        assert GateVerdict.needs_rework.value == "needs_rework"
        assert GateVerdict.needs_human_approval.value == "needs_human_approval"


# ---------------------------------------------------------------------------
# Diff hygiene scanner
# ---------------------------------------------------------------------------


class TestDiffHygiene:
    def test_clean_file_passes(self, tmp_path: Path) -> None:
        (tmp_path / "clean.py").write_text("x = 1\n")
        result = _scan_diff_hygiene(["clean.py"], repo_root=tmp_path)
        assert result.passed is True
        assert result.check_name == "diff-hygiene"

    def test_conflict_marker_fails(self, tmp_path: Path) -> None:
        (tmp_path / "bad.py").write_text("<<<<<<< HEAD\nmine\n=======\ntheirs\n>>>>>>> branch\n")
        result = _scan_diff_hygiene(["bad.py"], repo_root=tmp_path)
        assert result.passed is False
        assert "<<<<<<<" in result.details

    def test_debug_leftover_fails(self, tmp_path: Path) -> None:
        (tmp_path / "debug.py").write_text("import pdb\npdb.set_trace()\n")
        result = _scan_diff_hygiene(["debug.py"], repo_root=tmp_path)
        assert result.passed is False
        assert "import pdb" in result.details

    def test_missing_file_passes(self, tmp_path: Path) -> None:
        result = _scan_diff_hygiene(["nonexistent.py"], repo_root=tmp_path)
        assert result.passed is True

    def test_empty_file_list_passes(self, tmp_path: Path) -> None:
        result = _scan_diff_hygiene([], repo_root=tmp_path)
        assert result.passed is True


# ---------------------------------------------------------------------------
# DeliveryQualityGate — individual checks (subprocess mocked)
# ---------------------------------------------------------------------------


def _ok_run(cmd: str, **kw) -> tuple[bool, str]:
    return True, "ok"


def _fail_run(cmd: str, **kw) -> tuple[bool, str]:
    return False, "something failed"


class TestIndividualChecks:
    @patch("sendsprint.quality_gate._run_command", _ok_run)
    def test_check_lint_pass(self) -> None:
        gate = DeliveryQualityGate()
        r = gate.check_lint()
        assert r.passed is True
        assert r.check_name == "lint"

    @patch("sendsprint.quality_gate._run_command", _fail_run)
    def test_check_lint_fail(self) -> None:
        gate = DeliveryQualityGate()
        r = gate.check_lint()
        assert r.passed is False
        assert r.severity == CheckSeverity.error

    @patch("sendsprint.quality_gate._run_command", _ok_run)
    def test_check_tests_pass(self) -> None:
        gate = DeliveryQualityGate()
        r = gate.check_tests()
        assert r.passed is True

    @patch("sendsprint.quality_gate._run_command", _fail_run)
    def test_check_tests_fail(self) -> None:
        gate = DeliveryQualityGate()
        r = gate.check_tests()
        assert r.passed is False
        assert r.severity == CheckSeverity.blocking

    @patch("sendsprint.quality_gate._run_command", _ok_run)
    def test_check_security_pass(self) -> None:
        gate = DeliveryQualityGate()
        r = gate.check_security()
        assert r.passed is True

    @patch("sendsprint.quality_gate._run_command", _fail_run)
    def test_check_security_fail(self) -> None:
        gate = DeliveryQualityGate()
        r = gate.check_security()
        assert r.passed is False
        assert r.severity == CheckSeverity.blocking

    @patch("sendsprint.quality_gate._run_command", _ok_run)
    def test_check_coverage_pass(self) -> None:
        gate = DeliveryQualityGate()
        r = gate.check_coverage()
        assert r.passed is True

    @patch("sendsprint.quality_gate._run_command", _fail_run)
    def test_check_coverage_fail(self) -> None:
        gate = DeliveryQualityGate()
        r = gate.check_coverage()
        assert r.passed is False
        assert r.severity == CheckSeverity.warning

    def test_check_playwright_skipped_when_no_cmd(self) -> None:
        gate = DeliveryQualityGate()
        r = gate.check_playwright()
        assert r.passed is True
        assert "skipped" in r.details

    @patch("sendsprint.quality_gate._run_command", _ok_run)
    def test_check_playwright_pass_when_configured(self) -> None:
        gate = DeliveryQualityGate(playwright_cmd="npx playwright test")
        r = gate.check_playwright()
        assert r.passed is True

    @patch("sendsprint.quality_gate._run_command", _fail_run)
    def test_check_playwright_fail(self) -> None:
        gate = DeliveryQualityGate(playwright_cmd="npx playwright test")
        r = gate.check_playwright()
        assert r.passed is False

    def test_check_diff_hygiene_delegates(self, tmp_path: Path) -> None:
        (tmp_path / "ok.py").write_text("x = 1\n")
        gate = DeliveryQualityGate(repo_root=tmp_path, changed_files=["ok.py"])
        r = gate.check_diff_hygiene()
        assert r.passed is True


# ---------------------------------------------------------------------------
# run_all_checks
# ---------------------------------------------------------------------------


class TestRunAllChecks:
    @patch("sendsprint.quality_gate._run_command", _ok_run)
    def test_returns_six_checks(self) -> None:
        gate = DeliveryQualityGate()
        results = gate.run_all_checks()
        assert len(results) == 6
        names = {r.check_name for r in results}
        assert names == {"lint", "tests", "security", "coverage", "playwright", "diff-hygiene"}


# ---------------------------------------------------------------------------
# Verdict logic
# ---------------------------------------------------------------------------


def _make_check(name: str, passed: bool, severity: CheckSeverity) -> QualityCheckResult:
    return QualityCheckResult(check_name=name, passed=passed, severity=severity)


class TestEvaluateVerdict:
    def test_all_pass_gives_pass_verdict(self) -> None:
        checks = [
            _make_check("lint", True, CheckSeverity.info),
            _make_check("tests", True, CheckSeverity.info),
        ]
        gate = DeliveryQualityGate()
        report = gate.evaluate(checks)
        assert report.verdict == GateVerdict.passed
        assert report.reasons == []

    def test_blocking_failure_gives_needs_rework(self) -> None:
        checks = [
            _make_check("lint", True, CheckSeverity.info),
            _make_check("tests", False, CheckSeverity.blocking),
        ]
        gate = DeliveryQualityGate()
        report = gate.evaluate(checks)
        assert report.verdict == GateVerdict.needs_rework
        assert len(report.reasons) == 1

    def test_error_failure_gives_needs_rework(self) -> None:
        checks = [
            _make_check("lint", False, CheckSeverity.error),
            _make_check("tests", True, CheckSeverity.info),
        ]
        gate = DeliveryQualityGate()
        report = gate.evaluate(checks)
        assert report.verdict == GateVerdict.needs_rework

    def test_warning_with_human_review_gives_needs_human_approval(self) -> None:
        checks = [
            _make_check("coverage", False, CheckSeverity.warning),
            _make_check("tests", True, CheckSeverity.info),
        ]
        policy = AutonomyPolicy(level="plan", require_human_review=True)
        gate = DeliveryQualityGate(policy=policy)
        report = gate.evaluate(checks)
        assert report.verdict == GateVerdict.needs_human_approval

    def test_warning_without_human_review_gives_pass(self) -> None:
        checks = [
            _make_check("coverage", False, CheckSeverity.warning),
            _make_check("tests", True, CheckSeverity.info),
        ]
        policy = AutonomyPolicy(level="execute", require_human_review=False)
        gate = DeliveryQualityGate(policy=policy)
        report = gate.evaluate(checks)
        assert report.verdict == GateVerdict.passed
        assert len(report.reasons) == 1  # warning still recorded

    def test_reasons_are_actionable(self) -> None:
        checks = [
            _make_check("lint", False, CheckSeverity.error),
            _make_check("tests", False, CheckSeverity.blocking),
        ]
        gate = DeliveryQualityGate()
        report = gate.evaluate(checks)
        assert report.verdict == GateVerdict.needs_rework
        assert len(report.reasons) == 2
        assert any("lint" in r for r in report.reasons)
        assert any("tests" in r for r in report.reasons)

    def test_empty_checks_gives_pass(self) -> None:
        gate = DeliveryQualityGate()
        report = gate.evaluate([])
        assert report.verdict == GateVerdict.passed


# ---------------------------------------------------------------------------
# Evidence bundle integration
# ---------------------------------------------------------------------------


class TestPersistToBundle:
    def test_persist_adds_decision_item(self, tmp_path: Path) -> None:
        manager = BundleManager(base_dir=tmp_path)
        bundle = manager.create_bundle("run-42")

        report = GateReport(
            verdict=GateVerdict.needs_rework,
            checks=[_make_check("tests", False, CheckSeverity.blocking)],
            reasons=["tests: 3 failed"],
        )
        gate = DeliveryQualityGate()
        gate.persist_to_bundle(report, bundle, manager)

        assert len(bundle.items) == 1
        item = bundle.items[0]
        assert item.type == EvidenceItemType.decision
        assert "needs_rework" in item.content
        assert item.metadata["gate_verdict"] == "needs_rework"
        assert item.metadata["checks_failed"] == 1

    def test_persist_pass_verdict(self, tmp_path: Path) -> None:
        manager = BundleManager(base_dir=tmp_path)
        bundle = manager.create_bundle("run-ok")

        report = GateReport(
            verdict=GateVerdict.passed,
            checks=[_make_check("lint", True, CheckSeverity.info)],
            reasons=[],
        )
        gate = DeliveryQualityGate()
        gate.persist_to_bundle(report, bundle, manager)

        item = bundle.items[0]
        assert "pass" in item.content
        assert item.metadata["checks_passed"] == 1
        assert item.metadata["checks_failed"] == 0

    def test_bundle_is_reloadable(self, tmp_path: Path) -> None:
        manager = BundleManager(base_dir=tmp_path)
        bundle = manager.create_bundle("run-reload")

        report = GateReport(
            verdict=GateVerdict.needs_human_approval,
            checks=[_make_check("coverage", False, CheckSeverity.warning)],
            reasons=["coverage: below 80%"],
        )
        gate = DeliveryQualityGate()
        gate.persist_to_bundle(report, bundle, manager)

        reloaded = manager.load_bundle("run-reload")
        assert reloaded is not None
        assert len(reloaded.items) == 1
        assert reloaded.items[0].metadata["gate_verdict"] == "needs_human_approval"
