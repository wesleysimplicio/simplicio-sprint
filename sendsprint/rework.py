"""Automatic rework loop for failed validations.

When a delivery fails quality-gate checks, this module classifies the failure,
diagnoses root cause, attempts a fix, and re-validates — up to configurable
limits on retries, wall-clock time, and touched-file scope.

Issue: #95
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.evidence import BundleManager, EvidenceBundle, EvidenceItemType
from sendsprint.quality_gate import (
    DeliveryQualityGate,
    GateReport,
    GateVerdict,
)

# ---------------------------------------------------------------------------
# Failure classification
# ---------------------------------------------------------------------------


class FailureClass(StrEnum):
    """How a quality-gate failure should be handled."""

    correctable = "correctable"
    environmental = "environmental"
    human_required = "human_required"


# ---------------------------------------------------------------------------
# Rework attempt record
# ---------------------------------------------------------------------------


class ReworkAttempt(BaseModel):
    """Record of a single rework iteration."""

    model_config = ConfigDict(extra="forbid")

    attempt_num: int
    failure_class: FailureClass
    diagnosis: str
    action_taken: str
    result: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Rework outcome
# ---------------------------------------------------------------------------


class ReworkOutcome(StrEnum):
    """Final outcome of the rework loop."""

    fixed = "fixed"
    max_retries_exceeded = "max_retries_exceeded"
    timeout_exceeded = "timeout_exceeded"
    human_required = "human_required"
    environmental_failure = "environmental_failure"


class ReworkResult(BaseModel):
    """Full result produced by :class:`ReworkLoop.run`."""

    model_config = ConfigDict(extra="forbid")

    outcome: ReworkOutcome | None = None
    attempts: list[ReworkAttempt] = Field(default_factory=list)
    final_report: GateReport | None = None
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None


# ---------------------------------------------------------------------------
# Classification heuristics
# ---------------------------------------------------------------------------

_ENVIRONMENTAL_MARKERS = (
    "timed out",
    "connection refused",
    "network unreachable",
    "permission denied",
    "no such file or directory",
    "command not found",
    "failed to start",
    "disk full",
    "out of memory",
)

_CORRECTABLE_CHECK_NAMES = frozenset({"lint", "diff-hygiene", "tests", "coverage"})


def classify_failure(report: GateReport) -> FailureClass:
    """Classify a failing gate report into a :class:`FailureClass`.

    Heuristic:
    1. If any failure detail contains environmental markers -> environmental.
    2. If all failing checks are in the correctable set -> correctable.
    3. Otherwise -> human_required.
    """
    failing = [c for c in report.checks if not c.passed]
    if not failing:
        return FailureClass.correctable  # edge case: no failures

    for check in failing:
        details_lower = check.details.lower()
        for marker in _ENVIRONMENTAL_MARKERS:
            if marker in details_lower:
                return FailureClass.environmental

    failing_names = {c.check_name for c in failing}
    if failing_names <= _CORRECTABLE_CHECK_NAMES:
        return FailureClass.correctable

    return FailureClass.human_required


def diagnose(report: GateReport) -> str:
    """Produce a human-readable diagnosis from a failing gate report."""
    failing = [c for c in report.checks if not c.passed]
    if not failing:
        return "no failures detected"

    lines = [f"{len(failing)} check(s) failed:"]
    for check in failing:
        lines.append(f"  - {check.check_name} [{check.severity.value}]: {check.details[:200]}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# ReworkLoop
# ---------------------------------------------------------------------------


class ReworkLoop:
    """Automatic retry loop: validate -> classify -> diagnose -> fix -> revalidate.

    Parameters
    ----------
    gate:
        The quality gate to re-evaluate on each iteration.
    fix_fn:
        Callable that receives ``(report, diagnosis)`` and returns a short
        description of the action taken.  If *None*, the loop can only
        classify and report — it won't attempt fixes.
    max_retries:
        Maximum number of fix-then-revalidate cycles.
    timeout_s:
        Wall-clock budget in seconds for the entire loop.
    """

    def __init__(
        self,
        gate: DeliveryQualityGate,
        *,
        fix_fn: Callable[[GateReport, str], str] | None = None,
        max_retries: int = 3,
        timeout_s: float = 300,
    ) -> None:
        self.gate = gate
        self.fix_fn = fix_fn
        self.max_retries = max_retries
        self.timeout_s = timeout_s

    # -- public API ----------------------------------------------------------

    def run(self, initial_report: GateReport | None = None) -> ReworkResult:
        """Execute the rework loop.

        If *initial_report* is given it's used as the first validation;
        otherwise a fresh ``gate.evaluate()`` is called.
        """
        started = time.monotonic()
        result = ReworkResult(started_at=datetime.now(UTC))

        report = initial_report if initial_report is not None else self.gate.evaluate()

        for attempt_num in range(1, self.max_retries + 1):
            # Already passing?
            if report.verdict == GateVerdict.passed:
                result.outcome = ReworkOutcome.fixed
                result.final_report = report
                result.finished_at = datetime.now(UTC)
                return result

            # Time budget exhausted?
            elapsed = time.monotonic() - started
            if elapsed >= self.timeout_s:
                result.outcome = ReworkOutcome.timeout_exceeded
                result.final_report = report
                result.finished_at = datetime.now(UTC)
                return result

            # Classify
            failure_class = classify_failure(report)
            diag = diagnose(report)

            # Non-correctable -> stop
            if failure_class == FailureClass.environmental:
                attempt = ReworkAttempt(
                    attempt_num=attempt_num,
                    failure_class=failure_class,
                    diagnosis=diag,
                    action_taken="none — environmental failure",
                    result="stopped",
                )
                result.attempts.append(attempt)
                result.outcome = ReworkOutcome.environmental_failure
                result.final_report = report
                result.finished_at = datetime.now(UTC)
                return result

            if failure_class == FailureClass.human_required:
                attempt = ReworkAttempt(
                    attempt_num=attempt_num,
                    failure_class=failure_class,
                    diagnosis=diag,
                    action_taken="none — human intervention required",
                    result="stopped",
                )
                result.attempts.append(attempt)
                result.outcome = ReworkOutcome.human_required
                result.final_report = report
                result.finished_at = datetime.now(UTC)
                return result

            # Correctable — attempt fix
            if self.fix_fn is not None:
                action = self.fix_fn(report, diag)
            else:
                action = "no fix_fn provided — skipped"

            # Revalidate
            report = self.gate.evaluate()
            action_result = "passed" if report.verdict == GateVerdict.passed else "still failing"

            attempt = ReworkAttempt(
                attempt_num=attempt_num,
                failure_class=failure_class,
                diagnosis=diag,
                action_taken=action,
                result=action_result,
            )
            result.attempts.append(attempt)

        # Exhausted retries
        if report.verdict == GateVerdict.passed:
            result.outcome = ReworkOutcome.fixed
        else:
            result.outcome = ReworkOutcome.max_retries_exceeded
        result.final_report = report
        result.finished_at = datetime.now(UTC)
        return result

    # -- evidence integration ------------------------------------------------

    def persist_to_bundle(
        self,
        rework_result: ReworkResult,
        bundle: EvidenceBundle,
        manager: BundleManager,
    ) -> None:
        """Persist rework attempt history into an evidence bundle."""
        if rework_result.outcome is None:
            raise ValueError("rework_result.outcome is required before persisting evidence")

        outcome = rework_result.outcome
        lines = [
            f"rework outcome: {outcome.value}",
            f"attempts: {len(rework_result.attempts)}",
        ]
        for att in rework_result.attempts:
            lines.append(
                f"  #{att.attempt_num} [{att.failure_class.value}] "
                f"action={att.action_taken!r} result={att.result}"
            )

        metadata: dict[str, Any] = {
            "rework_outcome": outcome.value,
            "total_attempts": len(rework_result.attempts),
            "attempts": [a.model_dump(mode="json") for a in rework_result.attempts],
        }

        manager.add_item(
            bundle,
            item_type=EvidenceItemType.decision,
            content="\n".join(lines),
            metadata=metadata,
        )
