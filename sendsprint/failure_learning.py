"""Lightweight failure taxonomy, flaky tracking, and trust scoring."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FailureCategory = Literal[
    "build",
    "quality",
    "test",
    "security",
    "infrastructure",
    "authentication",
    "unknown",
]
OutcomeStatus = Literal["passed", "failed"]
TrustLevel = Literal["high", "medium", "low"]


class FailureEvent(BaseModel):
    """One normalized execution outcome used for learning."""

    model_config = ConfigDict(extra="forbid")

    fingerprint: str
    step: str
    status: OutcomeStatus
    message: str = ""
    category: FailureCategory = "unknown"
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def inferred(
        cls,
        *,
        fingerprint: str,
        step: str,
        status: OutcomeStatus,
        message: str = "",
    ) -> FailureEvent:
        return cls(
            fingerprint=fingerprint,
            step=step,
            status=status,
            message=message,
            category=classify_failure(step=step, message=message),
        )


class LearnedFailure(BaseModel):
    """Aggregate knowledge for one failure fingerprint."""

    model_config = ConfigDict(extra="forbid")

    fingerprint: str
    step: str
    category: FailureCategory
    first_seen_at: datetime
    last_seen_at: datetime
    failure_count: int = 0
    success_count: int = 0
    transitions: int = 0
    last_status: OutcomeStatus | None = None
    sample_message: str = ""

    def record(self, event: FailureEvent) -> None:
        if self.last_status and self.last_status != event.status:
            self.transitions += 1
        self.last_status = event.status
        self.last_seen_at = event.observed_at
        if event.status == "failed":
            self.failure_count += 1
            if event.message:
                self.sample_message = event.message
        else:
            self.success_count += 1

    @property
    def total_runs(self) -> int:
        return self.failure_count + self.success_count

    @property
    def is_flaky(self) -> bool:
        return self.failure_count > 0 and self.success_count > 0


class TrustScore(BaseModel):
    """Simple repository trust score derived from recent outcomes."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: float
    level: TrustLevel
    total_events: int
    failure_rate: float
    flaky_rate: float
    unknown_rate: float


class FlakyOutcomeTracker(BaseModel):
    """Tracks status transitions per fingerprint to detect flaky behavior."""

    model_config = ConfigDict(extra="forbid")

    failures: dict[str, LearnedFailure] = Field(default_factory=dict)

    def record(self, event: FailureEvent) -> LearnedFailure:
        learned = self.failures.get(event.fingerprint)
        if learned is None:
            learned = LearnedFailure(
                fingerprint=event.fingerprint,
                step=event.step,
                category=event.category,
                first_seen_at=event.observed_at,
                last_seen_at=event.observed_at,
                sample_message=event.message,
            )
            self.failures[event.fingerprint] = learned
        learned.record(event)
        return learned

    def flaky_fingerprints(self) -> list[str]:
        return sorted(
            fingerprint
            for fingerprint, learned in self.failures.items()
            if learned.is_flaky or learned.transitions > 0
        )


def classify_failure(*, step: str, message: str = "") -> FailureCategory:
    """Infer a coarse failure category from step and message heuristics."""
    haystack = f"{step} {message}".lower()
    if any(token in haystack for token in ("401", "403", "unauthorized", "forbidden", "token")):
        return "authentication"
    if any(token in haystack for token in ("audit", "secret", "vulnerability", "security")):
        return "security"
    if any(token in haystack for token in ("timeout", "econn", "dns", "network", "rate limit")):
        return "infrastructure"
    if any(
        token in haystack
        for token in ("pytest", "playwright", "assert", "snapshot", "test failed", "spec")
    ):
        return "test"
    if any(
        token in haystack for token in ("lint", "ruff", "eslint", "mypy", "format", "type-check")
    ):
        return "quality"
    if any(
        token in haystack
        for token in ("build", "compile", "install", "module not found", "syntaxerror")
    ):
        return "build"
    return "unknown"


def calculate_trust_score(events: Iterable[FailureEvent]) -> TrustScore:
    """Score a repository from 0..1, penalizing failures, flakiness, and unknowns."""
    materialized = list(events)
    if not materialized:
        return TrustScore(
            score=1.0,
            level="high",
            total_events=0,
            failure_rate=0.0,
            flaky_rate=0.0,
            unknown_rate=0.0,
        )

    tracker = FlakyOutcomeTracker()
    for event in materialized:
        tracker.record(event)

    total = len(materialized)
    failures = sum(1 for event in materialized if event.status == "failed")
    failure_rate = failures / total
    unknown_rate = sum(1 for event in materialized if event.category == "unknown") / total

    flaky_event_count = 0
    for event in materialized:
        learned = tracker.failures[event.fingerprint]
        if learned.is_flaky:
            flaky_event_count += 1
    flaky_rate = flaky_event_count / total

    score = 1.0 - (failure_rate * 0.6) - (flaky_rate * 0.25) - (unknown_rate * 0.15)
    score = round(min(1.0, max(0.0, score)), 3)
    if score >= 0.8:
        level: TrustLevel = "high"
    elif score >= 0.5:
        level = "medium"
    else:
        level = "low"

    return TrustScore(
        score=score,
        level=level,
        total_events=total,
        failure_rate=round(failure_rate, 3),
        flaky_rate=round(flaky_rate, 3),
        unknown_rate=round(unknown_rate, 3),
    )
