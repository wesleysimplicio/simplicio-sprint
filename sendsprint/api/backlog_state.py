"""Persistent backlog board state for the SendSprint web API.

This module stores lightweight UI-facing board state under a local JSON file so
the API can track column movement, archive actions, and user-attributed history
without mutating the upstream sprint provider.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_BACKLOG_STATE_ENV = "SENDSPRINT_BACKLOG_STATE_PATH"
DEFAULT_BACKLOG_STATE_FILE = Path(".sendsprint") / "backlog_state.json"
BacklogHistoryAction = Literal["move", "archive", "unarchive"]


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _require_text(name: str, value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def normalize_provider(provider: str) -> str:
    return _require_text("provider", provider).lower()


def sprint_state_key(provider: str, sprint_id: str) -> str:
    return f"{normalize_provider(provider)}::{_require_text('sprint_id', sprint_id)}"


class BacklogHistoryEntry(BaseModel):
    """One immutable backlog interaction event."""

    model_config = ConfigDict(extra="forbid")

    action: BacklogHistoryAction
    actor_email: str
    observed_at: datetime = Field(default_factory=_now_utc)
    from_column: str | None = None
    to_column: str | None = None
    archived: bool | None = None
    note: str | None = None


class BacklogCardState(BaseModel):
    """Persisted UI state for a single sprint card."""

    model_config = ConfigDict(extra="forbid")

    item_key: str
    board_column: str = "backlog"
    archived: bool = False
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    updated_by: str | None = None
    history: list[BacklogHistoryEntry] = Field(default_factory=list)

    def record_move(self, *, target_column: str, actor_email: str, note: str | None = None) -> None:
        """Update the card column and append a movement audit event."""

        next_column = _require_text("target_column", target_column)
        actor = _require_text("actor_email", actor_email)
        previous_column = self.board_column
        self.board_column = next_column
        self.updated_by = actor
        self.updated_at = _now_utc()
        self.history.append(
            BacklogHistoryEntry(
                action="move",
                actor_email=actor,
                from_column=previous_column,
                to_column=next_column,
                archived=self.archived,
                note=note,
            )
        )

    def record_archive(
        self,
        *,
        archived: bool,
        actor_email: str,
        note: str | None = None,
    ) -> None:
        """Archive or unarchive the card and append an audit event."""

        actor = _require_text("actor_email", actor_email)
        self.archived = archived
        self.updated_by = actor
        self.updated_at = _now_utc()
        self.history.append(
            BacklogHistoryEntry(
                action="archive" if archived else "unarchive",
                actor_email=actor,
                from_column=self.board_column,
                to_column=self.board_column,
                archived=archived,
                note=note,
            )
        )


class SprintBacklogState(BaseModel):
    """Persisted board state scoped to one provider sprint."""

    model_config = ConfigDict(extra="forbid")

    provider: str
    sprint_id: str
    created_at: datetime = Field(default_factory=_now_utc)
    updated_at: datetime = Field(default_factory=_now_utc)
    items: dict[str, BacklogCardState] = Field(default_factory=dict)

    def get_or_create_item(self, item_key: str) -> BacklogCardState:
        key = _require_text("item_key", item_key)
        card = self.items.get(key)
        if card is None:
            card = BacklogCardState(item_key=key)
            self.items[key] = card
            self.updated_at = _now_utc()
        return card


class BacklogState(BaseModel):
    """Root persisted backlog state for every imported sprint."""

    model_config = ConfigDict(extra="forbid")

    updated_at: datetime = Field(default_factory=_now_utc)
    sprints: dict[str, SprintBacklogState] = Field(default_factory=dict)

    def get_or_create_sprint(self, provider: str, sprint_id: str) -> SprintBacklogState:
        key = sprint_state_key(provider, sprint_id)
        sprint = self.sprints.get(key)
        if sprint is None:
            sprint = SprintBacklogState(
                provider=normalize_provider(provider),
                sprint_id=_require_text("sprint_id", sprint_id),
            )
            self.sprints[key] = sprint
            self.updated_at = _now_utc()
        return sprint


class BacklogStateStore:
    """Load and persist backlog state in a local JSON file."""

    def __init__(
        self,
        root: str | Path | None = None,
        *,
        state_path: str | Path | None = None,
    ) -> None:
        self.root = Path(root or Path.cwd()).expanduser().resolve()
        self.path = self._resolve_state_path(state_path)

    def _resolve_state_path(self, state_path: str | Path | None) -> Path:
        override = state_path or os.environ.get(DEFAULT_BACKLOG_STATE_ENV)
        if override:
            candidate = Path(override).expanduser()
            if not candidate.is_absolute():
                candidate = self.root / candidate
            return candidate.resolve()
        return (self.root / DEFAULT_BACKLOG_STATE_FILE).resolve()

    def load(self) -> BacklogState:
        """Read the persisted board state or return an empty state."""

        if not self.path.exists():
            return BacklogState()
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return BacklogState()
        return BacklogState.model_validate_json(raw)

    def save(self, state: BacklogState) -> Path:
        """Persist the full backlog state to disk."""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        state.updated_at = _now_utc()
        self.path.write_text(state.model_dump_json(indent=2), encoding="utf-8")
        return self.path

    def get_sprint_state(self, provider: str, sprint_id: str) -> SprintBacklogState:
        """Return the saved sprint state, or an empty transient view if missing."""

        state = self.load()
        key = sprint_state_key(provider, sprint_id)
        existing = state.sprints.get(key)
        if existing is not None:
            return existing
        return SprintBacklogState(
            provider=normalize_provider(provider),
            sprint_id=_require_text("sprint_id", sprint_id),
        )

    def record_move(
        self,
        provider: str,
        sprint_id: str,
        item_key: str,
        *,
        target_column: str,
        actor_email: str,
        note: str | None = None,
    ) -> BacklogCardState:
        """Persist a card movement and return the updated card state."""

        state = self.load()
        sprint = state.get_or_create_sprint(provider, sprint_id)
        card = sprint.get_or_create_item(item_key)
        card.record_move(target_column=target_column, actor_email=actor_email, note=note)
        sprint.updated_at = _now_utc()
        self.save(state)
        return card

    def record_archive(
        self,
        provider: str,
        sprint_id: str,
        item_key: str,
        *,
        archived: bool,
        actor_email: str,
        note: str | None = None,
    ) -> BacklogCardState:
        """Persist archive or unarchive state and return the updated card."""

        state = self.load()
        sprint = state.get_or_create_sprint(provider, sprint_id)
        card = sprint.get_or_create_item(item_key)
        card.record_archive(archived=archived, actor_email=actor_email, note=note)
        sprint.updated_at = _now_utc()
        self.save(state)
        return card
