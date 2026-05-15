"""Tests for persistent resumable run state."""

from __future__ import annotations

from sendsprint.run_state import RunStateStore, delivery_key, stable_run_id


def test_stable_run_id_is_deterministic() -> None:
    assert stable_run_id("azuredevops", "Sprint 29") == stable_run_id("azuredevops", "Sprint 29")
    assert stable_run_id("azuredevops", "Sprint 29") != stable_run_id("jira", "Sprint 29")


def test_run_state_store_persists_completion(tmp_path) -> None:
    store = RunStateStore(tmp_path)
    state = store.load_or_create("run-demo", source="jira", sprint_id="42")
    key = delivery_key("PROJ-1", "api")

    state.mark_planned(key)
    state.mark_completed(key)
    store.save(state)

    loaded = store.load_or_create("run-demo", source="jira", sprint_id="42")
    assert loaded.is_completed(key) is True
    assert key in loaded.planned
