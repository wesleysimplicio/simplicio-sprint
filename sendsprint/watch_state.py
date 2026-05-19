"""Persistent state for ``sendsprint watch`` deduplication."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


class WatchTaskRecord(BaseModel):
    """Last known processing state for one tracker item."""

    task_id: str
    revision: str | None = None
    status: str
    branch: str | None = None
    last_run_id: str | None = None
    final_status: str = "pending"
    pr_url: str | None = None
    last_attempt_at: str = Field(default_factory=_now_iso)
    skip_reason: str | None = None
    failure_reason: str | None = None

    def same_revision(self, revision: str | int | None) -> bool:
        return self.revision == normalize_revision(revision)


class WatchState(BaseModel):
    """Serializable watch-state file."""

    records: dict[str, WatchTaskRecord] = Field(default_factory=dict)


class WatchStateStore:
    """Read/write ``watch-state.json`` with duplicate-protection helpers."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def load(self) -> WatchState:
        if not self.path.exists():
            return WatchState()
        return WatchState.model_validate_json(self.path.read_text(encoding="utf-8"))

    def save(self, state: WatchState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(state.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def should_process(
        self,
        state: WatchState,
        *,
        task_id: str,
        revision: str | int | None,
        status: str,
        force: bool = False,
    ) -> tuple[bool, str | None]:
        """Return whether a task can run in the current cycle."""
        if force:
            return True, None
        record = state.records.get(task_id)
        if record is None:
            return True, None
        normalized_status = status.strip().lower()
        if not record.same_revision(revision):
            return True, None
        if normalized_status == "new" and record.status.strip().lower() != "new":
            return True, None
        if record.final_status == "failed" and not record.branch and not record.pr_url:
            return True, None
        return False, "already processed for this status and revision"

    def mark(
        self,
        state: WatchState,
        *,
        task_id: str,
        revision: str | int | None,
        status: str,
        final_status: str,
        run_id: str | None = None,
        branch: str | None = None,
        pr_url: str | None = None,
        skip_reason: str | None = None,
        failure_reason: str | None = None,
    ) -> WatchTaskRecord:
        record = WatchTaskRecord(
            task_id=task_id,
            revision=normalize_revision(revision),
            status=status,
            branch=branch,
            last_run_id=run_id,
            final_status=final_status,
            pr_url=pr_url,
            skip_reason=skip_reason,
            failure_reason=failure_reason,
        )
        state.records[task_id] = record
        return record


def normalize_revision(value: str | int | None) -> str | None:
    return None if value is None else str(value)


__all__ = ["WatchState", "WatchStateStore", "WatchTaskRecord", "normalize_revision"]
