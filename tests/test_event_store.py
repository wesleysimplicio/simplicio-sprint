"""Tests for durable event store with NDJSON persistence and replay (#114)."""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from sendsprint.contracts import EventType, RunEvent
from sendsprint.event_store import (
    EventStore,
    ReplayCursor,
    RetentionPolicy,
    RunSnapshotData,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_event(
    run_id: str = "run-test",
    event_type: EventType = EventType.progress,
    data: dict | None = None,
    timestamp: datetime | None = None,
) -> RunEvent:
    ev = RunEvent(
        event_type=event_type,
        run_id=run_id,
        data=data or {},
    )
    if timestamp is not None:
        ev = ev.model_copy(update={"timestamp": timestamp})
    return ev


# ---------------------------------------------------------------------------
# RetentionPolicy model
# ---------------------------------------------------------------------------


class TestRetentionPolicy:
    def test_defaults(self) -> None:
        p = RetentionPolicy()
        assert p.max_events == 10_000
        assert p.max_age_days == 30
        assert p.compact_after_days == 7

    def test_custom_values(self) -> None:
        p = RetentionPolicy(max_events=500, max_age_days=7, compact_after_days=3)
        assert p.max_events == 500

    def test_min_bound(self) -> None:
        with pytest.raises(Exception):
            RetentionPolicy(max_events=0)

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(Exception):
            RetentionPolicy(unknown_field="x")  # type: ignore[call-arg]

    def test_serialization_roundtrip(self) -> None:
        p = RetentionPolicy(max_events=100, max_age_days=14, compact_after_days=5)
        raw = p.model_dump_json()
        restored = RetentionPolicy.model_validate_json(raw)
        assert restored == p


# ---------------------------------------------------------------------------
# ReplayCursor model
# ---------------------------------------------------------------------------


class TestReplayCursor:
    def test_defaults(self) -> None:
        c = ReplayCursor()
        assert c.seq == 0
        assert c.timestamp is None

    def test_with_timestamp(self) -> None:
        ts = datetime.now(UTC)
        c = ReplayCursor(seq=5, timestamp=ts)
        assert c.seq == 5
        assert c.timestamp == ts

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(Exception):
            ReplayCursor(bad="x")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# RunSnapshotData model
# ---------------------------------------------------------------------------


class TestRunSnapshotData:
    def test_defaults(self) -> None:
        s = RunSnapshotData(run_id="run-1")
        assert s.run_id == "run-1"
        assert s.seq == 0
        assert s.event_count == 0
        assert s.first_event_at is None
        assert s.summary == {}

    def test_populated(self) -> None:
        now = datetime.now(UTC)
        s = RunSnapshotData(
            run_id="run-2",
            seq=10,
            event_count=10,
            first_event_at=now - timedelta(minutes=5),
            last_event_at=now,
            last_event_type="progress",
            summary={"started": 1, "progress": 9},
        )
        assert s.event_count == 10

    def test_serialization_roundtrip(self) -> None:
        s = RunSnapshotData(run_id="run-3", seq=5, event_count=5)
        raw = s.model_dump_json()
        restored = RunSnapshotData.model_validate_json(raw)
        assert restored.run_id == s.run_id
        assert restored.seq == s.seq


# ---------------------------------------------------------------------------
# EventStore — append and basic reads
# ---------------------------------------------------------------------------


class TestEventStoreAppend:
    def test_append_returns_seq(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-a")
        ev = _make_event(run_id="run-a", event_type=EventType.started)
        seq = store.append(ev)
        assert seq == 0

    def test_append_increments_seq(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-b")
        for i in range(5):
            seq = store.append(_make_event(run_id="run-b"))
            assert seq == i

    def test_event_count(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-c")
        assert store.event_count() == 0
        store.append(_make_event(run_id="run-c"))
        store.append(_make_event(run_id="run-c"))
        assert store.event_count() == 2

    def test_current_seq(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-d")
        assert store.current_seq() == 0
        store.append(_make_event(run_id="run-d"))
        assert store.current_seq() == 1


# ---------------------------------------------------------------------------
# EventStore — NDJSON persistence
# ---------------------------------------------------------------------------


class TestEventStorePersistence:
    def test_ndjson_file_created(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-p1")
        store.append(_make_event(run_id="run-p1", event_type=EventType.started))
        assert store.events_path.exists()

    def test_ndjson_content_valid(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-p2")
        store.append(_make_event(run_id="run-p2", event_type=EventType.started))
        store.append(_make_event(run_id="run-p2", event_type=EventType.progress))
        lines = store.events_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 2
        for line in lines:
            record = json.loads(line)
            assert "seq" in record
            assert "event" in record

    def test_run_dir_path(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-xyz")
        store.append(_make_event(run_id="run-xyz"))
        assert store.run_dir.exists()
        assert "run-xyz" in str(store.run_dir)

    def test_safe_id_strips_bad_chars(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run/../bad")
        store.append(_make_event(run_id="run/../bad"))
        assert store.events_path.exists()
        # No path traversal in directory name.
        assert ".." not in store.run_dir.name


# ---------------------------------------------------------------------------
# EventStore — reload from disk (restart simulation)
# ---------------------------------------------------------------------------


class TestEventStoreReload:
    def test_reload_recovers_events(self, tmp_path: Path) -> None:
        store1 = EventStore(root=tmp_path, run_id="run-r1")
        store1.append(_make_event(run_id="run-r1", event_type=EventType.started))
        store1.append(_make_event(run_id="run-r1", event_type=EventType.progress))
        store1.append(_make_event(run_id="run-r1", event_type=EventType.completed))

        # Simulate restart: new EventStore reading same directory.
        store2 = EventStore(root=tmp_path, run_id="run-r1")
        assert store2.event_count() == 3
        assert store2.current_seq() == 3

    def test_reload_replay_matches(self, tmp_path: Path) -> None:
        store1 = EventStore(root=tmp_path, run_id="run-r2")
        store1.append(_make_event(run_id="run-r2", event_type=EventType.started))
        store1.append(_make_event(run_id="run-r2", event_type=EventType.progress))

        store2 = EventStore(root=tmp_path, run_id="run-r2")
        events = store2.replay()
        assert len(events) == 2
        assert events[0][0].event_type == EventType.started
        assert events[1][0].event_type == EventType.progress

    def test_append_after_reload_continues_seq(self, tmp_path: Path) -> None:
        store1 = EventStore(root=tmp_path, run_id="run-r3")
        store1.append(_make_event(run_id="run-r3"))
        store1.append(_make_event(run_id="run-r3"))

        store2 = EventStore(root=tmp_path, run_id="run-r3")
        seq = store2.append(_make_event(run_id="run-r3"))
        assert seq == 2
        assert store2.event_count() == 3

    def test_empty_store_reload(self, tmp_path: Path) -> None:
        store1 = EventStore(root=tmp_path, run_id="run-r4")
        store2 = EventStore(root=tmp_path, run_id="run-r4")
        assert store2.event_count() == 0
        assert store2.current_seq() == 0


# ---------------------------------------------------------------------------
# EventStore — replay
# ---------------------------------------------------------------------------


class TestEventStoreReplay:
    def test_replay_all(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-rp1")
        for _ in range(5):
            store.append(_make_event(run_id="run-rp1"))
        events = store.replay()
        assert len(events) == 5
        assert [e[1] for e in events] == [0, 1, 2, 3, 4]

    def test_replay_from_seq(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-rp2")
        for _ in range(5):
            store.append(_make_event(run_id="run-rp2"))
        events = store.replay(from_seq=3)
        assert len(events) == 2
        assert events[0][1] == 3
        assert events[1][1] == 4

    def test_replay_from_timestamp(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-rp3")
        old = datetime.now(UTC) - timedelta(hours=2)
        recent = datetime.now(UTC) - timedelta(seconds=10)
        store.append(_make_event(run_id="run-rp3", timestamp=old))
        store.append(_make_event(run_id="run-rp3", timestamp=old))
        store.append(_make_event(run_id="run-rp3", timestamp=recent))
        store.append(_make_event(run_id="run-rp3", timestamp=recent))

        cutoff = datetime.now(UTC) - timedelta(minutes=5)
        events = store.replay(from_timestamp=cutoff)
        assert len(events) == 2

    def test_replay_from_seq_takes_precedence(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-rp4")
        old = datetime.now(UTC) - timedelta(hours=2)
        for _ in range(5):
            store.append(_make_event(run_id="run-rp4", timestamp=old))
        # from_seq > 0 overrides from_timestamp.
        events = store.replay(from_seq=4, from_timestamp=datetime.now(UTC) + timedelta(hours=1))
        assert len(events) == 1
        assert events[0][1] == 4

    def test_replay_empty_store(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-rp5")
        assert store.replay() == []


# ---------------------------------------------------------------------------
# EventStore — snapshots
# ---------------------------------------------------------------------------


class TestEventStoreSnapshot:
    def test_get_snapshot_empty(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-s1")
        snap = store.get_snapshot()
        assert snap.run_id == "run-s1"
        assert snap.event_count == 0
        assert snap.first_event_at is None

    def test_get_snapshot_populated(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-s2")
        store.append(_make_event(run_id="run-s2", event_type=EventType.started))
        store.append(_make_event(run_id="run-s2", event_type=EventType.progress))
        store.append(_make_event(run_id="run-s2", event_type=EventType.progress))
        snap = store.get_snapshot()
        assert snap.event_count == 3
        assert snap.seq == 3
        assert snap.last_event_type == "progress"
        assert snap.summary == {"started": 1, "progress": 2}

    def test_write_and_load_snapshot(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-s3")
        store.append(_make_event(run_id="run-s3", event_type=EventType.started))
        path = store.write_snapshot()
        assert path.exists()
        loaded = store.load_snapshot()
        assert loaded is not None
        assert loaded.run_id == "run-s3"
        assert loaded.event_count == 1

    def test_load_snapshot_missing(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-s4")
        assert store.load_snapshot() is None

    def test_auto_snapshot_at_interval(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-s5", snapshot_interval=3)
        store.append(_make_event(run_id="run-s5"))
        store.append(_make_event(run_id="run-s5"))
        assert not store.snapshot_path.exists()
        store.append(_make_event(run_id="run-s5"))  # seq=2, count=3 triggers snapshot.
        assert store.snapshot_path.exists()
        loaded = store.load_snapshot()
        assert loaded is not None
        assert loaded.event_count == 3


# ---------------------------------------------------------------------------
# EventStore — compaction
# ---------------------------------------------------------------------------


class TestEventStoreCompaction:
    def test_compact_removes_old_events(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-c1")
        old = datetime.now(UTC) - timedelta(days=10)
        recent = datetime.now(UTC)
        store.append(_make_event(run_id="run-c1", timestamp=old))
        store.append(_make_event(run_id="run-c1", timestamp=old))
        store.append(_make_event(run_id="run-c1", timestamp=recent))

        policy = RetentionPolicy(compact_after_days=5)
        removed = store.compact(policy)
        assert removed == 2
        assert store.event_count() == 1

    def test_compact_respects_max_events(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-c2")
        now = datetime.now(UTC)
        for i in range(10):
            store.append(_make_event(run_id="run-c2", timestamp=now))

        policy = RetentionPolicy(max_events=3, compact_after_days=999)
        removed = store.compact(policy)
        assert removed == 7
        assert store.event_count() == 3

    def test_compact_rewrites_ndjson(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-c3")
        old = datetime.now(UTC) - timedelta(days=20)
        recent = datetime.now(UTC)
        for _ in range(5):
            store.append(_make_event(run_id="run-c3", timestamp=old))
        store.append(_make_event(run_id="run-c3", timestamp=recent))

        policy = RetentionPolicy(compact_after_days=10)
        store.compact(policy)

        lines = store.events_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1

    def test_compact_updates_seq(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-c4")
        now = datetime.now(UTC)
        for _ in range(5):
            store.append(_make_event(run_id="run-c4", timestamp=now))
        policy = RetentionPolicy(max_events=2, compact_after_days=999)
        store.compact(policy)
        assert store.current_seq() == 2

    def test_compact_no_events_noop(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-c5")
        removed = store.compact(RetentionPolicy())
        assert removed == 0

    def test_compact_default_policy(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-c6")
        now = datetime.now(UTC)
        store.append(_make_event(run_id="run-c6", timestamp=now))
        removed = store.compact()
        assert removed == 0
        assert store.event_count() == 1


# ---------------------------------------------------------------------------
# EventStore — thread safety
# ---------------------------------------------------------------------------


class TestEventStoreThreadSafety:
    def test_concurrent_appends(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-ts1")
        errors: list[str] = []

        def writer(n: int) -> None:
            try:
                for _ in range(20):
                    store.append(_make_event(run_id="run-ts1"))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert store.event_count() == 100

    def test_concurrent_append_and_replay(self, tmp_path: Path) -> None:
        store = EventStore(root=tmp_path, run_id="run-ts2")
        errors: list[str] = []

        def writer() -> None:
            try:
                for _ in range(50):
                    store.append(_make_event(run_id="run-ts2"))
            except Exception as exc:
                errors.append(str(exc))

        def reader() -> None:
            try:
                for _ in range(50):
                    store.replay()
            except Exception as exc:
                errors.append(str(exc))

        t1 = threading.Thread(target=writer)
        t2 = threading.Thread(target=reader)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert not errors
        assert store.event_count() == 50
