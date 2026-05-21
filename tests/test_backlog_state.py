from __future__ import annotations

from pathlib import Path

import pytest

from sendsprint.api.backlog_state import BacklogStateStore

PROVIDER = "azuredevops"
SPRINT_ID = "Sprint 12"
ITEM_KEY = "TASK-123"
ACTOR_EMAIL = "dev@example.com"


@pytest.fixture
def store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> BacklogStateStore:
    state_path = tmp_path / ".sendsprint" / "backlog-state.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENDSPRINT_BACKLOG_STATE_PATH", str(state_path))
    return BacklogStateStore(root=tmp_path)


def test_load_empty_returns_transient_state(store: BacklogStateStore) -> None:
    state = store.load()

    assert state.sprints == {}
    assert state.updated_at is not None
    assert store.path.name == "backlog-state.json"
    assert not store.path.exists()


def test_record_move_persists_card_history(store: BacklogStateStore) -> None:
    card = store.record_move(
        PROVIDER,
        SPRINT_ID,
        ITEM_KEY,
        target_column="planning",
        actor_email=ACTOR_EMAIL,
        note="manual move",
    )

    assert card.item_key == ITEM_KEY
    assert card.board_column == "planning"
    assert card.archived is False
    assert card.updated_by == ACTOR_EMAIL
    assert len(card.history) == 1
    assert card.history[0].action == "move"
    assert card.history[0].actor_email == ACTOR_EMAIL
    assert card.history[0].from_column == "backlog"
    assert card.history[0].to_column == "planning"
    assert card.history[0].archived is False
    assert card.history[0].note == "manual move"

    persisted = store.get_sprint_state(PROVIDER, SPRINT_ID)
    assert ITEM_KEY in persisted.items
    assert persisted.items[ITEM_KEY].board_column == "planning"
    assert persisted.items[ITEM_KEY].history[-1].action == "move"


def test_record_archive_and_unarchive_persist_state(store: BacklogStateStore) -> None:
    store.record_move(
        PROVIDER,
        SPRINT_ID,
        ITEM_KEY,
        target_column="testing",
        actor_email=ACTOR_EMAIL,
    )

    archived = store.record_archive(
        PROVIDER,
        SPRINT_ID,
        ITEM_KEY,
        archived=True,
        actor_email=ACTOR_EMAIL,
        note="done for now",
    )
    assert archived.archived is True
    assert archived.history[-1].action == "archive"
    assert archived.history[-1].archived is True
    assert archived.history[-1].from_column == "testing"
    assert archived.history[-1].to_column == "testing"
    assert archived.history[-1].note == "done for now"

    restored = store.record_archive(
        PROVIDER,
        SPRINT_ID,
        ITEM_KEY,
        archived=False,
        actor_email=ACTOR_EMAIL,
        note="reopened",
    )
    assert restored.archived is False
    assert [entry.action for entry in restored.history] == ["move", "archive", "unarchive"]
    assert restored.history[-1].archived is False
    assert restored.history[-1].note == "reopened"

    persisted = store.get_sprint_state(PROVIDER, SPRINT_ID)
    assert persisted.items[ITEM_KEY].archived is False
    assert persisted.items[ITEM_KEY].updated_by == ACTOR_EMAIL


def test_state_persists_between_store_instances(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state_path = tmp_path / ".sendsprint" / "backlog-state.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENDSPRINT_BACKLOG_STATE_PATH", str(state_path))

    first = BacklogStateStore(root=tmp_path)
    first.record_move(
        PROVIDER,
        SPRINT_ID,
        ITEM_KEY,
        target_column="programming",
        actor_email=ACTOR_EMAIL,
        note="first write",
    )
    first.record_archive(
        PROVIDER,
        SPRINT_ID,
        ITEM_KEY,
        archived=True,
        actor_email=ACTOR_EMAIL,
        note="persist me",
    )

    second = BacklogStateStore(root=tmp_path)
    persisted = second.get_sprint_state(PROVIDER, SPRINT_ID)

    assert second.path == first.path
    assert second.path.exists()
    assert ITEM_KEY in persisted.items
    assert persisted.items[ITEM_KEY].board_column == "programming"
    assert persisted.items[ITEM_KEY].archived is True
    assert [entry.action for entry in persisted.items[ITEM_KEY].history] == ["move", "archive"]
