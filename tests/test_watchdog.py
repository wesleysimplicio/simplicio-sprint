from datetime import UTC, datetime, timedelta

from sendsprint.watchdog import WatchdogState, evaluate_watchdog


def test_watchdog_requests_retry_when_task_is_stuck() -> None:
    state = WatchdogState(
        task_id="task-1",
        provider_key="codex",
        retry_count=1,
        last_progress_at=datetime.now(UTC) - timedelta(minutes=30),
    )
    decision = evaluate_watchdog(state, timeout_minutes=10, max_retries=2)
    assert decision.stuck is True
    assert decision.should_retry is True
