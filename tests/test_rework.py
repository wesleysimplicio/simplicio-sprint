"""Tests for sendsprint.rework — automatic rework loop for failed validations.

Issue: #95
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from sendsprint.evidence import BundleManager, EvidenceItemType
from sendsprint.quality_gate import (
    CheckSeverity,
    DeliveryQualityGate,
    GateReport,
    GateVerdict,
    QualityCheckResult,
)
from sendsprint.rework import (
    FailureClass,
    ReworkAttempt,
    ReworkLoop,
    ReworkOutcome,
    ReworkResult,
    classify_failure,
    diagnose,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check(name: str, passed: bool, severity: str = "error", details: str = "") -> QualityCheckResult:
    return QualityCheckResult(
        check_name=name,
        passed=passed,
        severity=CheckSeverity(severity),
        details=details or ("ok" if passed else f"{name} failed"),
    )


def _report(verdict: str, checks: list[QualityCheckResult] | None = None) -> GateReport:
    return GateReport(
        verdict=GateVerdict(verdict),
        checks=checks or [],
        reasons=[c.details for c in (checks or []) if not c.passed],
    )


# ---------------------------------------------------------------------------
# FailureClass enum
# ---------------------------------------------------------------------------


class TestFailureClass:
    def test_values(self) -> None:
        assert FailureClass.correctable.value == "correctable"
        assert FailureClass.environmental.value == "environmental"
        assert FailureClass.human_required.value == "human_required"

    def test_string_enum(self) -> None:
        assert isinstance(FailureClass.correctable, str)


# ---------------------------------------------------------------------------
# ReworkAttempt model
# ---------------------------------------------------------------------------


class TestReworkAttempt:
    def test_basic_fields(self) -> None:
        att = ReworkAttempt(
            attempt_num=1,
            failure_class=FailureClass.correctable,
            diagnosis="lint failed",
            action_taken="ran ruff --fix",
            result="passed",
        )
        assert att.attempt_num == 1
        assert att.failure_class == FailureClass.correctable
        assert att.diagnosis == "lint failed"
        assert att.action_taken == "ran ruff --fix"
        assert att.result == "passed"
        assert att.timestamp is not None

    def test_serialization_roundtrip(self) -> None:
        att = ReworkAttempt(
            attempt_num=2,
            failure_class=FailureClass.environmental,
            diagnosis="connection refused",
            action_taken="none",
            result="stopped",
        )
        data = att.model_dump(mode="json")
        restored = ReworkAttempt.model_validate(data)
        assert restored.attempt_num == att.attempt_num
        assert restored.failure_class == att.failure_class

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):
            ReworkAttempt(
                attempt_num=1,
                failure_class=FailureClass.correctable,
                diagnosis="x",
                action_taken="y",
                result="z",
                bogus="extra",
            )


# ---------------------------------------------------------------------------
# classify_failure
# ---------------------------------------------------------------------------


class TestClassifyFailure:
    def test_correctable_lint(self) -> None:
        report = _report("needs_rework", [_check("lint", False)])
        assert classify_failure(report) == FailureClass.correctable

    def test_correctable_tests(self) -> None:
        report = _report("needs_rework", [_check("tests", False, "blocking")])
        assert classify_failure(report) == FailureClass.correctable

    def test_correctable_diff_hygiene(self) -> None:
        report = _report("needs_rework", [_check("diff-hygiene", False, "blocking")])
        assert classify_failure(report) == FailureClass.correctable

    def test_correctable_coverage(self) -> None:
        report = _report("needs_rework", [_check("coverage", False, "warning")])
        assert classify_failure(report) == FailureClass.correctable

    def test_environmental_timeout(self) -> None:
        report = _report(
            "needs_rework",
            [_check("tests", False, "blocking", details="command timed out after 120s")],
        )
        assert classify_failure(report) == FailureClass.environmental

    def test_environmental_connection_refused(self) -> None:
        report = _report(
            "needs_rework",
            [_check("security", False, "blocking", details="Connection refused on port 443")],
        )
        assert classify_failure(report) == FailureClass.environmental

    def test_environmental_command_not_found(self) -> None:
        report = _report(
            "needs_rework",
            [_check("lint", False, details="command not found: ruff")],
        )
        assert classify_failure(report) == FailureClass.environmental

    def test_human_required_unknown_check(self) -> None:
        report = _report("needs_rework", [_check("manual-review", False)])
        assert classify_failure(report) == FailureClass.human_required

    def test_human_required_security_blocking(self) -> None:
        report = _report("needs_rework", [_check("security", False, "blocking")])
        assert classify_failure(report) == FailureClass.human_required

    def test_no_failures_returns_correctable(self) -> None:
        report = _report("pass", [_check("lint", True)])
        assert classify_failure(report) == FailureClass.correctable

    def test_mixed_correctable_and_unknown(self) -> None:
        report = _report(
            "needs_rework",
            [_check("lint", False), _check("unknown-gate", False)],
        )
        assert classify_failure(report) == FailureClass.human_required


# ---------------------------------------------------------------------------
# diagnose
# ---------------------------------------------------------------------------


class TestDiagnose:
    def test_no_failures(self) -> None:
        report = _report("pass", [_check("lint", True)])
        assert diagnose(report) == "no failures detected"

    def test_single_failure(self) -> None:
        report = _report("needs_rework", [_check("lint", False, details="E302 expected 2 blank lines")])
        result = diagnose(report)
        assert "1 check(s) failed" in result
        assert "lint" in result
        assert "E302" in result

    def test_multiple_failures(self) -> None:
        report = _report(
            "needs_rework",
            [
                _check("lint", False, details="lint issues"),
                _check("tests", False, "blocking", details="3 tests failed"),
            ],
        )
        result = diagnose(report)
        assert "2 check(s) failed" in result


# ---------------------------------------------------------------------------
# ReworkLoop.run
# ---------------------------------------------------------------------------


class TestReworkLoopRun:
    def test_already_passing(self) -> None:
        """If the initial report passes, loop returns fixed with 0 attempts."""
        gate = MagicMock(spec=DeliveryQualityGate)
        report = _report("pass", [_check("lint", True)])

        loop = ReworkLoop(gate, max_retries=3)
        result = loop.run(initial_report=report)

        assert result.outcome == ReworkOutcome.fixed
        assert len(result.attempts) == 0
        assert result.final_report is not None
        assert result.finished_at is not None

    def test_fix_on_first_retry(self) -> None:
        """fix_fn fixes the issue and gate passes on revalidation."""
        gate = MagicMock(spec=DeliveryQualityGate)
        passing_report = _report("pass", [_check("lint", True)])
        gate.evaluate.return_value = passing_report

        failing_report = _report("needs_rework", [_check("lint", False)])

        fix_fn = MagicMock(return_value="applied ruff --fix")

        loop = ReworkLoop(gate, fix_fn=fix_fn, max_retries=3)
        result = loop.run(initial_report=failing_report)

        assert result.outcome == ReworkOutcome.fixed
        assert len(result.attempts) == 1
        assert result.attempts[0].failure_class == FailureClass.correctable
        assert result.attempts[0].action_taken == "applied ruff --fix"
        assert result.attempts[0].result == "passed"
        fix_fn.assert_called_once()

    def test_fix_after_multiple_retries(self) -> None:
        """Takes 2 attempts to fix."""
        gate = MagicMock(spec=DeliveryQualityGate)
        still_failing = _report("needs_rework", [_check("tests", False, "blocking")])
        now_passing = _report("pass", [_check("tests", True)])
        gate.evaluate.side_effect = [still_failing, now_passing]

        fix_fn = MagicMock(return_value="patched test fixture")
        failing_report = _report("needs_rework", [_check("tests", False, "blocking")])

        loop = ReworkLoop(gate, fix_fn=fix_fn, max_retries=5)
        result = loop.run(initial_report=failing_report)

        assert result.outcome == ReworkOutcome.fixed
        assert len(result.attempts) == 2

    def test_max_retries_exceeded(self) -> None:
        """Loop exhausts retries without fixing."""
        gate = MagicMock(spec=DeliveryQualityGate)
        failing = _report("needs_rework", [_check("lint", False)])
        gate.evaluate.return_value = failing

        fix_fn = MagicMock(return_value="tried fix")
        loop = ReworkLoop(gate, fix_fn=fix_fn, max_retries=2)
        result = loop.run(initial_report=failing)

        assert result.outcome == ReworkOutcome.max_retries_exceeded
        assert len(result.attempts) == 2

    def test_environmental_stops_immediately(self) -> None:
        gate = MagicMock(spec=DeliveryQualityGate)
        failing = _report(
            "needs_rework",
            [_check("tests", False, "blocking", details="command timed out after 120s")],
        )

        fix_fn = MagicMock(return_value="noop")
        loop = ReworkLoop(gate, fix_fn=fix_fn, max_retries=5)
        result = loop.run(initial_report=failing)

        assert result.outcome == ReworkOutcome.environmental_failure
        assert len(result.attempts) == 1
        assert result.attempts[0].failure_class == FailureClass.environmental
        fix_fn.assert_not_called()

    def test_human_required_stops_immediately(self) -> None:
        gate = MagicMock(spec=DeliveryQualityGate)
        failing = _report("needs_rework", [_check("security", False, "blocking")])

        fix_fn = MagicMock(return_value="noop")
        loop = ReworkLoop(gate, fix_fn=fix_fn, max_retries=5)
        result = loop.run(initial_report=failing)

        assert result.outcome == ReworkOutcome.human_required
        assert len(result.attempts) == 1
        assert result.attempts[0].failure_class == FailureClass.human_required
        fix_fn.assert_not_called()

    def test_timeout_exceeded(self) -> None:
        gate = MagicMock(spec=DeliveryQualityGate)
        failing = _report("needs_rework", [_check("lint", False)])

        loop = ReworkLoop(gate, max_retries=10, timeout_s=0)
        result = loop.run(initial_report=failing)

        assert result.outcome == ReworkOutcome.timeout_exceeded

    def test_no_fix_fn_still_records_attempts(self) -> None:
        """Without fix_fn, loop still iterates but can't fix."""
        gate = MagicMock(spec=DeliveryQualityGate)
        failing = _report("needs_rework", [_check("lint", False)])
        gate.evaluate.return_value = failing

        loop = ReworkLoop(gate, fix_fn=None, max_retries=2)
        result = loop.run(initial_report=failing)

        assert result.outcome == ReworkOutcome.max_retries_exceeded
        assert len(result.attempts) == 2
        assert "no fix_fn provided" in result.attempts[0].action_taken

    def test_calls_gate_evaluate_when_no_initial_report(self) -> None:
        gate = MagicMock(spec=DeliveryQualityGate)
        passing = _report("pass", [_check("lint", True)])
        gate.evaluate.return_value = passing

        loop = ReworkLoop(gate, max_retries=3)
        result = loop.run()

        gate.evaluate.assert_called_once()
        assert result.outcome == ReworkOutcome.fixed


# ---------------------------------------------------------------------------
# ReworkResult model
# ---------------------------------------------------------------------------


class TestReworkResult:
    def test_default_fields(self) -> None:
        r = ReworkResult(outcome=ReworkOutcome.fixed)
        assert r.outcome == ReworkOutcome.fixed
        assert r.attempts == []
        assert r.final_report is None
        assert r.finished_at is None
        assert r.started_at is not None

    def test_outcome_optional_initially(self) -> None:
        r = ReworkResult()
        assert r.outcome is None

    def test_serialization_roundtrip(self) -> None:
        att = ReworkAttempt(
            attempt_num=1,
            failure_class=FailureClass.correctable,
            diagnosis="lint",
            action_taken="fix",
            result="passed",
        )
        r = ReworkResult(
            outcome=ReworkOutcome.fixed,
            attempts=[att],
            final_report=_report("pass"),
            finished_at=datetime.now(UTC),
        )
        data = r.model_dump(mode="json")
        restored = ReworkResult.model_validate(data)
        assert restored.outcome == ReworkOutcome.fixed
        assert len(restored.attempts) == 1


# ---------------------------------------------------------------------------
# Evidence integration
# ---------------------------------------------------------------------------


class TestEvidenceIntegration:
    def test_persist_to_bundle(self, tmp_path: object) -> None:
        manager = BundleManager(base_dir=str(tmp_path))
        bundle = manager.create_bundle("test-run")

        gate = MagicMock(spec=DeliveryQualityGate)
        loop = ReworkLoop(gate, max_retries=3)

        rework_result = ReworkResult(
            outcome=ReworkOutcome.fixed,
            attempts=[
                ReworkAttempt(
                    attempt_num=1,
                    failure_class=FailureClass.correctable,
                    diagnosis="lint failed",
                    action_taken="ruff --fix",
                    result="passed",
                ),
            ],
            finished_at=datetime.now(UTC),
        )

        loop.persist_to_bundle(rework_result, bundle, manager)

        assert len(bundle.items) == 1
        item = bundle.items[0]
        assert item.type == EvidenceItemType.decision
        assert "rework outcome: fixed" in item.content
        assert item.metadata["rework_outcome"] == "fixed"
        assert item.metadata["total_attempts"] == 1

    def test_persist_reloads_from_disk(self, tmp_path: object) -> None:
        manager = BundleManager(base_dir=str(tmp_path))
        bundle = manager.create_bundle("reload-test")

        gate = MagicMock(spec=DeliveryQualityGate)
        loop = ReworkLoop(gate)

        rework_result = ReworkResult(
            outcome=ReworkOutcome.max_retries_exceeded,
            attempts=[
                ReworkAttempt(
                    attempt_num=1,
                    failure_class=FailureClass.correctable,
                    diagnosis="tests failed",
                    action_taken="patched fixture",
                    result="still failing",
                ),
                ReworkAttempt(
                    attempt_num=2,
                    failure_class=FailureClass.correctable,
                    diagnosis="tests failed",
                    action_taken="patched assertion",
                    result="still failing",
                ),
            ],
        )

        loop.persist_to_bundle(rework_result, bundle, manager)

        reloaded = manager.load_bundle("reload-test")
        assert reloaded is not None
        assert len(reloaded.items) == 1
        assert reloaded.items[0].metadata["total_attempts"] == 2

    def test_persist_multiple_attempts_metadata(self, tmp_path: object) -> None:
        manager = BundleManager(base_dir=str(tmp_path))
        bundle = manager.create_bundle("multi-att")

        gate = MagicMock(spec=DeliveryQualityGate)
        loop = ReworkLoop(gate)

        attempts = [
            ReworkAttempt(
                attempt_num=i,
                failure_class=FailureClass.correctable,
                diagnosis=f"diag-{i}",
                action_taken=f"fix-{i}",
                result="still failing" if i < 3 else "passed",
            )
            for i in range(1, 4)
        ]
        rework_result = ReworkResult(outcome=ReworkOutcome.fixed, attempts=attempts)

        loop.persist_to_bundle(rework_result, bundle, manager)
        stored_attempts = bundle.items[0].metadata["attempts"]
        assert len(stored_attempts) == 3
        assert stored_attempts[0]["attempt_num"] == 1
        assert stored_attempts[2]["result"] == "passed"


# ---------------------------------------------------------------------------
# ReworkOutcome enum
# ---------------------------------------------------------------------------


class TestReworkOutcome:
    def test_all_values(self) -> None:
        assert set(ReworkOutcome) == {
            ReworkOutcome.fixed,
            ReworkOutcome.max_retries_exceeded,
            ReworkOutcome.timeout_exceeded,
            ReworkOutcome.human_required,
            ReworkOutcome.environmental_failure,
        }
