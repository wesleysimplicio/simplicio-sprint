"""Tests for watch-state deduplication."""

from __future__ import annotations

from sendsprint.watch_state import WatchState, WatchStateStore


def test_watch_state_deduplicates_by_task_revision_and_status(tmp_path) -> None:
    store = WatchStateStore(tmp_path / "watch-state.json")
    state = WatchState()

    assert store.should_process(state, task_id="179851", revision=1, status="New") == (
        True,
        None,
    )

    store.mark(
        state,
        task_id="179851",
        revision=1,
        status="New",
        final_status="ok",
        run_id="run-1",
        branch="feature/179851-fix",
        pr_url="https://pr/1",
    )

    assert store.should_process(state, task_id="179851", revision=1, status="New") == (
        False,
        "already processed for this status and revision",
    )
    assert store.should_process(state, task_id="179851", revision=2, status="New") == (
        True,
        None,
    )
    assert store.should_process(state, task_id="179851", revision=1, status="New", force=True) == (
        True,
        None,
    )


def test_watch_state_persists_records(tmp_path) -> None:
    store = WatchStateStore(tmp_path / ".sendsprint" / "runs" / "watch-state.json")
    state = WatchState()
    store.mark(
        state,
        task_id="TASK-1",
        revision="7",
        status="New",
        final_status="failed",
        failure_reason="build failed",
    )
    store.save(state)

    loaded = store.load()

    assert loaded.records["TASK-1"].revision == "7"
    assert loaded.records["TASK-1"].final_status == "failed"
    assert loaded.records["TASK-1"].failure_reason == "build failed"
