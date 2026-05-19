"""Stuck-agent watchdog and bounded retry policy."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from pydantic import BaseModel, ConfigDict, Field


class WatchdogState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    provider_key: str
    retry_count: int = 0
    last_progress_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def heartbeat(self) -> None:
        self.last_progress_at = datetime.now(UTC)


class WatchdogDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    stuck: bool
    should_retry: bool
    reason: str


def evaluate_watchdog(
    state: WatchdogState,
    *,
    now: datetime | None = None,
    timeout_minutes: int = 15,
    max_retries: int = 2,
) -> WatchdogDecision:
    current = now or datetime.now(UTC)
    stuck = current - state.last_progress_at > timedelta(minutes=timeout_minutes)
    if not stuck:
        return WatchdogDecision(stuck=False, should_retry=False, reason="heartbeat is recent")
    should_retry = state.retry_count < max_retries
    return WatchdogDecision(
        stuck=True,
        should_retry=should_retry,
        reason="task exceeded the heartbeat timeout",
    )
