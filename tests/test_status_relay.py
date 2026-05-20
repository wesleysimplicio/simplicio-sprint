"""Tests for the tri-agent status relay (#111)."""

from __future__ import annotations

import json
import threading

import pytest

from sendsprint.contracts import EventType
from sendsprint.status_relay import (
    ControlCommand,
    RunEventEmitter,
    RunSnapshot,
    StatusRelay,
)

# ---------------------------------------------------------------------------
# RunEventEmitter
# ---------------------------------------------------------------------------


class TestRunEventEmitter:
    def test_emit_stores_event(self) -> None:
        emitter = RunEventEmitter("run-abc")
        ev = emitter.emit(EventType.started, {"step": "plan"})
        assert ev.event_type == EventType.started
        assert ev.run_id == "run-abc"
        assert ev.data == {"step": "plan"}

    def test_emit_accepts_string_event_type(self) -> None:
        emitter = RunEventEmitter("run-1")
        ev = emitter.emit("progress", {"pct": 50})
        assert ev.event_type == EventType.progress

    def test_emit_invalid_string_raises(self) -> None:
        emitter = RunEventEmitter("run-1")
        with pytest.raises(ValueError):
            emitter.emit("nonexistent_event")

    def test_history_returns_newest_last(self) -> None:
        emitter = RunEventEmitter("run-1")
        emitter.emit(EventType.started)
        emitter.emit(EventType.progress)
        emitter.emit(EventType.completed)
        history = emitter.history(limit=2)
        assert len(history) == 2
        assert history[0].event_type == EventType.progress
        assert history[1].event_type == EventType.completed

    def test_max_history_evicts_oldest(self) -> None:
        emitter = RunEventEmitter("run-1", max_history=3)
        for _ in range(5):
            emitter.emit(EventType.heartbeat)
        assert len(emitter) == 3

    def test_len(self) -> None:
        emitter = RunEventEmitter("run-1")
        assert len(emitter) == 0
        emitter.emit(EventType.log)
        assert len(emitter) == 1

    def test_thread_safety(self) -> None:
        emitter = RunEventEmitter("run-ts", max_history=500)
        errors: list[str] = []

        def writer() -> None:
            try:
                for _ in range(100):
                    emitter.emit(EventType.heartbeat)
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=writer) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert not errors
        assert len(emitter) == 500


# ---------------------------------------------------------------------------
# RunSnapshot model
# ---------------------------------------------------------------------------


class TestRunSnapshot:
    def test_defaults(self) -> None:
        snap = RunSnapshot(run_id="run-x")
        assert snap.current_action == "idle"
        assert snap.failures == []
        assert snap.blockers == []
        assert snap.next_step == ""
        assert snap.active_agents == []
        assert snap.evidence_refs == []
        assert snap.pr_links == []
        assert snap.event_count == 0

    def test_populated(self) -> None:
        snap = RunSnapshot(
            run_id="run-y",
            current_action="testing",
            failures=["lint failed"],
            blockers=["waiting for review"],
            next_step="fix lint",
            active_agents=["codex-worker-1"],
            evidence_refs=["evidence/run-y/log.txt"],
            pr_links=["https://github.com/org/repo/pull/42"],
            last_command="validate",
            last_evidence="coverage 87%",
            event_count=12,
        )
        assert snap.current_action == "testing"
        assert len(snap.failures) == 1
        assert snap.event_count == 12

    def test_serialization_roundtrip(self) -> None:
        snap = RunSnapshot(run_id="run-rt", current_action="building")
        raw = snap.model_dump_json()
        restored = RunSnapshot.model_validate_json(raw)
        assert restored.run_id == "run-rt"
        assert restored.current_action == "building"

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValueError):
            RunSnapshot(run_id="run-z", unknown_field="bad")


# ---------------------------------------------------------------------------
# ControlCommand
# ---------------------------------------------------------------------------


class TestControlCommand:
    def test_create_pause(self) -> None:
        cmd = ControlCommand(action="pause", issued_by="claude")
        assert cmd.action == "pause"
        assert cmd.issued_by == "claude"

    def test_payload_default_empty(self) -> None:
        cmd = ControlCommand(action="resume", issued_by="hermes")
        assert cmd.payload == {}

    def test_with_payload(self) -> None:
        cmd = ControlCommand(
            action="change_autonomy",
            issued_by="codex",
            payload={"level": "execute"},
        )
        assert cmd.payload["level"] == "execute"


# ---------------------------------------------------------------------------
# StatusRelay — snapshot management
# ---------------------------------------------------------------------------


class TestStatusRelaySnapshots:
    def test_get_snapshot_none_when_missing(self) -> None:
        relay = StatusRelay()
        assert relay.get_snapshot("nope") is None

    def test_update_and_get(self) -> None:
        relay = StatusRelay()
        snap = RunSnapshot(run_id="run-1", current_action="planning")
        relay.update_snapshot(snap)
        got = relay.get_snapshot("run-1")
        assert got is not None
        assert got.current_action == "planning"

    def test_update_replaces(self) -> None:
        relay = StatusRelay()
        relay.update_snapshot(RunSnapshot(run_id="run-1", current_action="planning"))
        relay.update_snapshot(RunSnapshot(run_id="run-1", current_action="testing"))
        assert relay.get_snapshot("run-1").current_action == "testing"

    def test_list_runs(self) -> None:
        relay = StatusRelay()
        relay.update_snapshot(RunSnapshot(run_id="a"))
        relay.update_snapshot(RunSnapshot(run_id="b"))
        assert sorted(relay.list_runs()) == ["a", "b"]


# ---------------------------------------------------------------------------
# StatusRelay — command queue
# ---------------------------------------------------------------------------


class TestStatusRelayCommands:
    def test_enqueue_and_drain(self) -> None:
        relay = StatusRelay()
        relay.enqueue_command(ControlCommand(action="pause", issued_by="claude"))
        relay.enqueue_command(ControlCommand(action="resume", issued_by="hermes"))
        assert relay.pending_commands() == 2
        cmds = relay.drain_commands()
        assert len(cmds) == 2
        assert cmds[0].action == "pause"
        assert relay.pending_commands() == 0

    def test_drain_empty(self) -> None:
        relay = StatusRelay()
        assert relay.drain_commands() == []

    def test_commands_thread_safe(self) -> None:
        relay = StatusRelay()
        errors: list[str] = []

        def enqueuer() -> None:
            try:
                for _ in range(50):
                    relay.enqueue_command(ControlCommand(action="pause", issued_by="claude"))
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=enqueuer) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        assert relay.pending_commands() == 200  # 4*50=200, capped at maxlen=200


# ---------------------------------------------------------------------------
# StatusRelay — format_for_claude (Markdown)
# ---------------------------------------------------------------------------


class TestFormatForClaude:
    def test_missing_run(self) -> None:
        relay = StatusRelay()
        out = relay.format_for_claude("nope")
        assert "No active run" in out
        assert "`nope`" in out

    def test_basic_fields(self) -> None:
        relay = StatusRelay()
        relay.update_snapshot(
            RunSnapshot(
                run_id="run-md",
                current_action="testing",
                next_step="publish PR",
                active_agents=["codex-1", "claude-main"],
                event_count=7,
            )
        )
        md = relay.format_for_claude("run-md")
        assert "## Run `run-md`" in md
        assert "**Current action:** testing" in md
        assert "**Next step:** publish PR" in md
        assert "codex-1, claude-main" in md

    def test_blockers_section(self) -> None:
        relay = StatusRelay()
        relay.update_snapshot(
            RunSnapshot(
                run_id="run-b",
                blockers=["review pending", "CI timeout"],
            )
        )
        md = relay.format_for_claude("run-b")
        assert "### Blockers" in md
        assert "- review pending" in md

    def test_evidence_truncation(self) -> None:
        relay = StatusRelay()
        refs = [f"evidence/{i}.txt" for i in range(8)]
        relay.update_snapshot(RunSnapshot(run_id="run-e", evidence_refs=refs))
        md = relay.format_for_claude("run-e")
        assert "and 3 more" in md


# ---------------------------------------------------------------------------
# StatusRelay — format_for_codex (JSON)
# ---------------------------------------------------------------------------


class TestFormatForCodex:
    def test_missing_run(self) -> None:
        relay = StatusRelay()
        out = relay.format_for_codex("nope")
        data = json.loads(out)
        assert data["error"] == "no_active_run"

    def test_valid_json(self) -> None:
        relay = StatusRelay()
        relay.update_snapshot(
            RunSnapshot(
                run_id="run-j",
                current_action="building",
                failures=["lint"],
                pr_links=["https://github.com/o/r/pull/1"],
                evidence_refs=[f"e{i}" for i in range(15)],
            )
        )
        out = relay.format_for_codex("run-j")
        data = json.loads(out)
        assert data["run_id"] == "run-j"
        assert data["current_action"] == "building"
        assert data["failures"] == ["lint"]
        # evidence capped at 10 in output
        assert len(data["evidence_refs"]) == 10
        assert data["evidence_total"] == 15
        assert "updated_at" in data


# ---------------------------------------------------------------------------
# StatusRelay — format_for_hermes (concise)
# ---------------------------------------------------------------------------


class TestFormatForHermes:
    def test_missing_run(self) -> None:
        relay = StatusRelay()
        out = relay.format_for_hermes("nope")
        assert out == "[nope] no active run"

    def test_concise_format(self) -> None:
        relay = StatusRelay()
        relay.update_snapshot(
            RunSnapshot(
                run_id="run-h",
                current_action="deploying",
                next_step="smoke test",
                active_agents=["hermes-1"],
            )
        )
        out = relay.format_for_hermes("run-h")
        assert "[run-h] deploying" in out
        assert "next: smoke test" in out
        assert "agents: hermes-1" in out

    def test_blocker_highlighted(self) -> None:
        relay = StatusRelay()
        relay.update_snapshot(
            RunSnapshot(
                run_id="run-hb",
                current_action="blocked",
                blockers=["human approval needed"],
            )
        )
        out = relay.format_for_hermes("run-hb")
        assert "BLOCKED:" in out

    def test_failure_count(self) -> None:
        relay = StatusRelay()
        relay.update_snapshot(
            RunSnapshot(
                run_id="run-hf",
                current_action="retrying",
                failures=["lint", "test", "build"],
            )
        )
        out = relay.format_for_hermes("run-hf")
        assert "failures: 3" in out

    def test_pr_count(self) -> None:
        relay = StatusRelay()
        relay.update_snapshot(
            RunSnapshot(
                run_id="run-hp",
                current_action="reviewing",
                pr_links=["pr1", "pr2"],
            )
        )
        out = relay.format_for_hermes("run-hp")
        assert "PRs: 2" in out


# ---------------------------------------------------------------------------
# Integration: emitter + relay together
# ---------------------------------------------------------------------------


class TestEmitterRelayIntegration:
    def test_emitter_feeds_snapshot(self) -> None:
        """Simulate worker emitting events and publishing snapshots."""
        emitter = RunEventEmitter("run-int")
        relay = StatusRelay()

        emitter.emit(EventType.started, {"step": "plan"})
        emitter.emit(EventType.progress, {"pct": 50})

        snap = RunSnapshot(
            run_id="run-int",
            current_action="implementing",
            next_step="test",
            event_count=len(emitter),
            active_agents=["codex-worker"],
        )
        relay.update_snapshot(snap)

        # All three adapters return immediately
        assert "implementing" in relay.format_for_claude("run-int")
        codex_data = json.loads(relay.format_for_codex("run-int"))
        assert codex_data["event_count"] == 2
        assert "[run-int] implementing" in relay.format_for_hermes("run-int")

    def test_concurrent_reads_dont_block(self) -> None:
        """Multiple threads reading snapshots while worker updates."""
        relay = StatusRelay()
        relay.update_snapshot(RunSnapshot(run_id="run-c", current_action="working"))
        errors: list[str] = []

        def reader(agent: str) -> None:
            try:
                for _ in range(100):
                    formatter = getattr(relay, f"format_for_{agent}")
                    result = formatter("run-c")
                    assert result  # non-empty
            except Exception as exc:
                errors.append(str(exc))

        def updater() -> None:
            try:
                for i in range(100):
                    relay.update_snapshot(RunSnapshot(run_id="run-c", current_action=f"step-{i}"))
            except Exception as exc:
                errors.append(str(exc))

        threads = [
            threading.Thread(target=reader, args=("claude",)),
            threading.Thread(target=reader, args=("codex",)),
            threading.Thread(target=reader, args=("hermes",)),
            threading.Thread(target=updater),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
