"""Durable per-run event log with NDJSON persistence and replay support.

Provides disk-backed event storage so run events survive API restarts,
compact snapshots for quick status reads, and cursor-based replay for
SSE subscribers reconnecting mid-run.

See: https://github.com/wesleysimplicio/SendSprint/issues/114
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.contracts import RunEvent


# ---------------------------------------------------------------------------
# Retention policy
# ---------------------------------------------------------------------------


class RetentionPolicy(BaseModel):
    """Controls how event logs are bounded and compacted."""

    model_config = ConfigDict(extra="forbid")

    max_events: int = Field(default=10_000, ge=1)
    max_age_days: int = Field(default=30, ge=1)
    compact_after_days: int = Field(default=7, ge=1)


# ---------------------------------------------------------------------------
# Replay cursor
# ---------------------------------------------------------------------------


class ReplayCursor(BaseModel):
    """Bookmark for resuming replay from a known position."""

    model_config = ConfigDict(extra="forbid")

    seq: int = 0
    timestamp: datetime | None = None


# ---------------------------------------------------------------------------
# Snapshot data
# ---------------------------------------------------------------------------


class RunSnapshotData(BaseModel):
    """Compact point-in-time snapshot persisted to disk."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    seq: int = 0
    event_count: int = 0
    first_event_at: datetime | None = None
    last_event_at: datetime | None = None
    last_event_type: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Event store
# ---------------------------------------------------------------------------


class EventStore:
    """Append-only, NDJSON-backed event store for a single run.

    Thread-safe. The in-memory list is the live transport; the NDJSON
    file on disk is the durable recovery source.

    Usage::

        store = EventStore(root=Path("."), run_id="run-abc123")
        store.append(event)
        for ev, seq in store.replay(from_seq=0):
            ...
        snapshot = store.get_snapshot()
        store.compact(RetentionPolicy())
    """

    def __init__(
        self,
        root: Path,
        run_id: str,
        *,
        snapshot_interval: int = 50,
    ) -> None:
        self.run_id = run_id
        self._root = Path(root).expanduser().resolve()
        self._run_dir = self._root / ".sendsprint" / "runs" / self._safe_id(run_id)
        self._events_path = self._run_dir / "events.ndjson"
        self._snapshot_path = self._run_dir / "snapshot.json"
        self._snapshot_interval = snapshot_interval

        self._lock = threading.Lock()
        self._events: list[RunEvent] = []
        self._seq: int = 0

        # Bootstrap from disk if prior events exist.
        self._load_from_disk()

    # -- public API --------------------------------------------------------

    def append(self, event: RunEvent) -> int:
        """Persist *event* to disk and memory. Returns the assigned seq."""
        with self._lock:
            seq = self._seq
            self._seq += 1
            self._events.append(event)
            self._write_event(event, seq)
            if self._seq % self._snapshot_interval == 0:
                self._write_snapshot_unlocked()
        return seq

    def replay(
        self,
        *,
        from_seq: int = 0,
        from_timestamp: datetime | None = None,
    ) -> list[tuple[RunEvent, int]]:
        """Return events starting at *from_seq* or *from_timestamp*.

        If both are given, *from_seq* takes precedence when non-zero.
        """
        with self._lock:
            results: list[tuple[RunEvent, int]] = []
            for idx, ev in enumerate(self._events):
                if from_seq > 0:
                    if idx < from_seq:
                        continue
                elif from_timestamp is not None:
                    if ev.timestamp < from_timestamp:
                        continue
                results.append((ev, idx))
            return results

    def compact(self, policy: RetentionPolicy | None = None) -> int:
        """Remove events older than policy thresholds. Returns count removed."""
        policy = policy or RetentionPolicy()
        cutoff = datetime.now(UTC) - timedelta(days=policy.compact_after_days)
        with self._lock:
            before = len(self._events)
            # Keep events newer than cutoff.
            kept: list[RunEvent] = [
                ev for ev in self._events if ev.timestamp >= cutoff
            ]
            # Trim to max_events (keep newest).
            if len(kept) > policy.max_events:
                kept = kept[-policy.max_events :]
            removed = before - len(kept)
            self._events = kept
            self._seq = len(kept)
            # Rewrite NDJSON with surviving events.
            self._rewrite_ndjson_unlocked()
            self._write_snapshot_unlocked()
        return removed

    def get_snapshot(self) -> RunSnapshotData:
        """Build a compact snapshot from current in-memory state."""
        with self._lock:
            return self._build_snapshot_unlocked()

    def write_snapshot(self) -> Path:
        """Force-write snapshot to disk and return its path."""
        with self._lock:
            self._write_snapshot_unlocked()
        return self._snapshot_path

    def load_snapshot(self) -> RunSnapshotData | None:
        """Load the most recent snapshot from disk, or None."""
        if not self._snapshot_path.exists():
            return None
        raw = self._snapshot_path.read_text(encoding="utf-8")
        return RunSnapshotData.model_validate_json(raw)

    def event_count(self) -> int:
        with self._lock:
            return len(self._events)

    def current_seq(self) -> int:
        with self._lock:
            return self._seq

    @property
    def events_path(self) -> Path:
        return self._events_path

    @property
    def snapshot_path(self) -> Path:
        return self._snapshot_path

    @property
    def run_dir(self) -> Path:
        return self._run_dir

    # -- internal ----------------------------------------------------------

    @staticmethod
    def _safe_id(run_id: str) -> str:
        return "".join(
            ch for ch in run_id if ch.isalnum() or ch in {"-", "_"}
        ).strip("-_") or "run"

    def _ensure_dir(self) -> None:
        self._run_dir.mkdir(parents=True, exist_ok=True)

    def _write_event(self, event: RunEvent, seq: int) -> None:
        """Append a single NDJSON line to the events file."""
        self._ensure_dir()
        line = json.dumps({"seq": seq, "event": json.loads(event.model_dump_json())})
        with open(self._events_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _rewrite_ndjson_unlocked(self) -> None:
        """Rewrite the full NDJSON file from in-memory events (caller holds lock)."""
        self._ensure_dir()
        with open(self._events_path, "w", encoding="utf-8") as f:
            for idx, ev in enumerate(self._events):
                line = json.dumps({"seq": idx, "event": json.loads(ev.model_dump_json())})
                f.write(line + "\n")

    def _build_snapshot_unlocked(self) -> RunSnapshotData:
        events = self._events
        summary: dict[str, int] = {}
        for ev in events:
            key = ev.event_type.value if hasattr(ev.event_type, "value") else str(ev.event_type)
            summary[key] = summary.get(key, 0) + 1
        return RunSnapshotData(
            run_id=self.run_id,
            seq=self._seq,
            event_count=len(events),
            first_event_at=events[0].timestamp if events else None,
            last_event_at=events[-1].timestamp if events else None,
            last_event_type=(
                events[-1].event_type.value
                if events and hasattr(events[-1].event_type, "value")
                else ""
            ),
            summary=summary,
        )

    def _write_snapshot_unlocked(self) -> None:
        self._ensure_dir()
        snap = self._build_snapshot_unlocked()
        self._snapshot_path.write_text(
            snap.model_dump_json(indent=2), encoding="utf-8"
        )

    def _load_from_disk(self) -> None:
        """Reload events from the NDJSON file on disk (cold start)."""
        if not self._events_path.exists():
            return
        events: list[RunEvent] = []
        max_seq = -1
        with open(self._events_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                record = json.loads(line)
                ev = RunEvent.model_validate(record["event"])
                events.append(ev)
                seq = record.get("seq", 0)
                if seq > max_seq:
                    max_seq = seq
        self._events = events
        self._seq = max_seq + 1 if events else 0
