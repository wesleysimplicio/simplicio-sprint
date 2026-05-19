"""Tests for failure taxonomy, flaky tracking, and trust scoring."""

from __future__ import annotations

from sendsprint.failure_learning import (
    FailureEvent,
    FlakyOutcomeTracker,
    calculate_trust_score,
    classify_failure,
)


def test_classify_failure_uses_step_and_message_heuristics() -> None:
    assert classify_failure(step="step-4-lint", message="ruff check failed") == "quality"
    assert classify_failure(step="step-5-tests", message="pytest assertion failed") == "test"
    assert classify_failure(step="step-3-dev", message="module not found during build") == "build"
    assert classify_failure(step="step-6-security", message="secret detected") == "security"
    assert classify_failure(step="step-1-auth", message="401 unauthorized") == "authentication"
    assert classify_failure(step="step-5-tests", message="network timeout") == "infrastructure"


def test_flaky_tracker_marks_fingerprint_when_status_flips() -> None:
    tracker = FlakyOutcomeTracker()
    tracker.record(
        FailureEvent.inferred(
            fingerprint="tests::login",
            step="step-5-tests",
            status="failed",
            message="playwright timeout",
        )
    )
    learned = tracker.record(
        FailureEvent.inferred(
            fingerprint="tests::login",
            step="step-5-tests",
            status="passed",
            message="playwright passed on retry",
        )
    )

    assert learned.is_flaky is True
    assert learned.transitions == 1
    assert tracker.flaky_fingerprints() == ["tests::login"]


def test_calculate_trust_score_penalizes_failures_flakiness_and_unknowns() -> None:
    events = [
        FailureEvent.inferred(
            fingerprint="lint::ruff",
            step="step-4-lint",
            status="passed",
            message="ruff clean",
        ),
        FailureEvent.inferred(
            fingerprint="tests::login",
            step="step-5-tests",
            status="failed",
            message="pytest assertion failed",
        ),
        FailureEvent.inferred(
            fingerprint="tests::login",
            step="step-5-tests",
            status="passed",
            message="pytest passed on retry",
        ),
        FailureEvent.inferred(
            fingerprint="misc::unknown",
            step="step-7-fix-loop",
            status="failed",
            message="weird issue",
        ),
    ]

    score = calculate_trust_score(events)

    assert score.total_events == 4
    assert score.failure_rate == 0.5
    assert score.flaky_rate == 0.5
    assert score.unknown_rate == 0.25
    assert score.level == "medium"
    assert 0.5 < score.score < 0.8


def test_calculate_trust_score_is_high_for_empty_history() -> None:
    score = calculate_trust_score([])
    assert score.score == 1.0
    assert score.level == "high"
