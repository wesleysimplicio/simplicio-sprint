"""Tests for the audited control-command queue.

Covers: allowed/denied commands, duplicate protection, full lifecycle
(queued -> accepted -> applied), rejected flow, failed flow, invalid
transitions, poll filtering, history, and concurrent enqueue safety.

See: https://github.com/wesleysimplicio/SendSprint/issues/115
"""

from __future__ import annotations

import threading

import pytest

from sendsprint.command_queue import (
    CommandNotFoundError,
    CommandPolicyError,
    CommandQueue,
    CommandStatus,
    DuplicateCommandError,
    InvalidCommandTransition,
    RunControlCommand,
    COMMAND_AUTONOMY_REQUIREMENTS,
)
from sendsprint.policy import AutonomyPolicy


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def execute_queue() -> CommandQueue:
    """Queue with execute-level autonomy (allows pause/resume/cancel)."""
    return CommandQueue(policy=AutonomyPolicy(level="execute"))


@pytest.fixture()
def observe_queue() -> CommandQueue:
    """Queue with observe-level autonomy (pause/resume only)."""
    return CommandQueue(policy=AutonomyPolicy(level="observe"))


@pytest.fixture()
def pr_queue() -> CommandQueue:
    """Queue with pr-level autonomy (allows everything including approve)."""
    return CommandQueue(policy=AutonomyPolicy(level="pr"))


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestRunControlCommand:
    def test_defaults(self) -> None:
        cmd = RunControlCommand(command_type="pause", run_id="run-1")
        assert cmd.status == CommandStatus.queued
        assert cmd.command_id  # auto-generated
        assert cmd.issued_by == "operator"
        assert cmd.params == {}
        assert cmd.reason == ""
        assert cmd.created_at is not None
        assert cmd.accepted_at is None
        assert cmd.applied_at is None
        assert cmd.resolved_at is None

    def test_explicit_fields(self) -> None:
        cmd = RunControlCommand(
            command_id="my-cmd",
            command_type="cancel",
            run_id="run-2",
            params={"priority": 1},
            issued_by="claude",
        )
        assert cmd.command_id == "my-cmd"
        assert cmd.command_type == "cancel"
        assert cmd.params == {"priority": 1}

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(Exception):
            RunControlCommand(
                command_type="pause", run_id="run-1", bogus="nope"
            )

    def test_serialization_roundtrip(self) -> None:
        cmd = RunControlCommand(command_type="resume", run_id="run-3")
        data = cmd.model_dump_json()
        restored = RunControlCommand.model_validate_json(data)
        assert restored.command_id == cmd.command_id
        assert restored.command_type == cmd.command_type


class TestCommandStatus:
    def test_all_values(self) -> None:
        assert set(CommandStatus) == {
            CommandStatus.queued,
            CommandStatus.accepted,
            CommandStatus.rejected,
            CommandStatus.applied,
            CommandStatus.failed,
        }


# ---------------------------------------------------------------------------
# Enqueue + policy tests
# ---------------------------------------------------------------------------

class TestEnqueue:
    def test_allowed_pause(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        assert cmd.status == CommandStatus.queued
        assert len(execute_queue) == 1

    def test_allowed_cancel_at_execute(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="cancel", run_id="run-1")
        assert cmd.command_type == "cancel"

    def test_denied_cancel_at_observe(self, observe_queue: CommandQueue) -> None:
        with pytest.raises(CommandPolicyError, match="cancel"):
            observe_queue.enqueue(command_type="cancel", run_id="run-1")

    def test_denied_approve_at_execute(self, execute_queue: CommandQueue) -> None:
        with pytest.raises(CommandPolicyError, match="approve"):
            execute_queue.enqueue(command_type="approve", run_id="run-1")

    def test_allowed_approve_at_pr(self, pr_queue: CommandQueue) -> None:
        cmd = pr_queue.enqueue(command_type="approve", run_id="run-1")
        assert cmd.status == CommandStatus.queued

    def test_duplicate_command_id(self, execute_queue: CommandQueue) -> None:
        execute_queue.enqueue(
            command_type="pause", run_id="run-1", command_id="dup-1"
        )
        with pytest.raises(DuplicateCommandError, match="dup-1"):
            execute_queue.enqueue(
                command_type="resume", run_id="run-1", command_id="dup-1"
            )

    def test_custom_issued_by(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(
            command_type="pause", run_id="run-1", issued_by="hermes"
        )
        assert cmd.issued_by == "hermes"

    def test_params_forwarded(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(
            command_type="reprioritize",
            run_id="run-1",
            params={"new_priority": 5},
        )
        assert cmd.params["new_priority"] == 5


# ---------------------------------------------------------------------------
# Poll tests
# ---------------------------------------------------------------------------

class TestPoll:
    def test_poll_returns_queued_only(self, execute_queue: CommandQueue) -> None:
        c1 = execute_queue.enqueue(command_type="pause", run_id="run-1")
        c2 = execute_queue.enqueue(command_type="resume", run_id="run-1")
        execute_queue.accept(c1.command_id)  # no longer queued

        pending = execute_queue.poll("run-1")
        assert len(pending) == 1
        assert pending[0].command_id == c2.command_id

    def test_poll_empty_run(self, execute_queue: CommandQueue) -> None:
        assert execute_queue.poll("nonexistent") == []

    def test_poll_isolates_runs(self, execute_queue: CommandQueue) -> None:
        execute_queue.enqueue(command_type="pause", run_id="run-a")
        execute_queue.enqueue(command_type="pause", run_id="run-b")
        assert len(execute_queue.poll("run-a")) == 1
        assert len(execute_queue.poll("run-b")) == 1


# ---------------------------------------------------------------------------
# Lifecycle transition tests
# ---------------------------------------------------------------------------

class TestLifecycle:
    def test_full_happy_path(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        assert cmd.status == CommandStatus.queued

        accepted = execute_queue.accept(cmd.command_id)
        assert accepted.status == CommandStatus.accepted
        assert accepted.accepted_at is not None

        applied = execute_queue.apply(cmd.command_id)
        assert applied.status == CommandStatus.applied
        assert applied.applied_at is not None
        assert applied.resolved_at is not None

    def test_reject_from_queued(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        rejected = execute_queue.reject(cmd.command_id, reason="not now")
        assert rejected.status == CommandStatus.rejected
        assert rejected.reason == "not now"
        assert rejected.resolved_at is not None

    def test_fail_from_accepted(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        execute_queue.accept(cmd.command_id)
        failed = execute_queue.fail(cmd.command_id, reason="worker crash")
        assert failed.status == CommandStatus.failed
        assert failed.reason == "worker crash"
        assert failed.resolved_at is not None

    def test_cannot_accept_non_queued(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        execute_queue.accept(cmd.command_id)
        with pytest.raises(InvalidCommandTransition, match="accept"):
            execute_queue.accept(cmd.command_id)

    def test_cannot_apply_non_accepted(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        with pytest.raises(InvalidCommandTransition, match="apply"):
            execute_queue.apply(cmd.command_id)

    def test_cannot_reject_accepted(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        execute_queue.accept(cmd.command_id)
        with pytest.raises(InvalidCommandTransition, match="reject"):
            execute_queue.reject(cmd.command_id)

    def test_cannot_fail_queued(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        with pytest.raises(InvalidCommandTransition, match="fail"):
            execute_queue.fail(cmd.command_id)


# ---------------------------------------------------------------------------
# Query tests
# ---------------------------------------------------------------------------

class TestQueries:
    def test_get_existing(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        assert execute_queue.get(cmd.command_id).command_id == cmd.command_id

    def test_get_not_found(self, execute_queue: CommandQueue) -> None:
        with pytest.raises(CommandNotFoundError):
            execute_queue.get("nope")

    def test_history_order(self, execute_queue: CommandQueue) -> None:
        c1 = execute_queue.enqueue(command_type="pause", run_id="run-1")
        c2 = execute_queue.enqueue(command_type="resume", run_id="run-1")
        c3 = execute_queue.enqueue(command_type="cancel", run_id="run-1")

        hist = execute_queue.history("run-1")
        assert [c.command_id for c in hist] == [
            c1.command_id, c2.command_id, c3.command_id,
        ]

    def test_history_empty_run(self, execute_queue: CommandQueue) -> None:
        assert execute_queue.history("ghost") == []

    def test_len(self, execute_queue: CommandQueue) -> None:
        assert len(execute_queue) == 0
        execute_queue.enqueue(command_type="pause", run_id="run-1")
        execute_queue.enqueue(command_type="resume", run_id="run-2")
        assert len(execute_queue) == 2


# ---------------------------------------------------------------------------
# Autonomy requirements mapping
# ---------------------------------------------------------------------------

class TestAutonomyRequirements:
    def test_all_actions_mapped(self) -> None:
        expected_actions = {
            "pause", "resume", "cancel", "change_autonomy",
            "reprioritize", "approve", "reject",
        }
        assert set(COMMAND_AUTONOMY_REQUIREMENTS.keys()) == expected_actions

    def test_pause_resume_lowest(self) -> None:
        assert COMMAND_AUTONOMY_REQUIREMENTS["pause"] == "observe"
        assert COMMAND_AUTONOMY_REQUIREMENTS["resume"] == "observe"

    def test_cancel_needs_execute(self) -> None:
        assert COMMAND_AUTONOMY_REQUIREMENTS["cancel"] == "execute"

    def test_approve_needs_pr(self) -> None:
        assert COMMAND_AUTONOMY_REQUIREMENTS["approve"] == "pr"


# ---------------------------------------------------------------------------
# Default policy
# ---------------------------------------------------------------------------

class TestDefaultPolicy:
    def test_default_is_plan(self) -> None:
        q = CommandQueue()
        assert q.policy.level == "plan"

    def test_default_allows_pause(self) -> None:
        q = CommandQueue()
        cmd = q.enqueue(command_type="pause", run_id="run-1")
        assert cmd.status == CommandStatus.queued

    def test_default_denies_cancel(self) -> None:
        q = CommandQueue()
        with pytest.raises(CommandPolicyError):
            q.enqueue(command_type="cancel", run_id="run-1")


# ---------------------------------------------------------------------------
# Concurrency
# ---------------------------------------------------------------------------

class TestConcurrency:
    def test_concurrent_enqueue(self, pr_queue: CommandQueue) -> None:
        """Multiple threads enqueue without data corruption."""
        errors: list[Exception] = []

        def worker(idx: int) -> None:
            try:
                pr_queue.enqueue(
                    command_type="pause",
                    run_id="run-1",
                    command_id=f"cmd-{idx}",
                )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(pr_queue) == 20

    def test_poll_does_not_block_enqueue(self, execute_queue: CommandQueue) -> None:
        """Polling while enqueueing does not deadlock."""
        execute_queue.enqueue(command_type="pause", run_id="run-1")

        results: list[list[RunControlCommand]] = []

        def poller() -> None:
            results.append(execute_queue.poll("run-1"))

        def enqueuer() -> None:
            execute_queue.enqueue(command_type="resume", run_id="run-1")

        t1 = threading.Thread(target=poller)
        t2 = threading.Thread(target=enqueuer)
        t1.start()
        t2.start()
        t1.join(timeout=2)
        t2.join(timeout=2)

        assert not t1.is_alive()
        assert not t2.is_alive()


# ---------------------------------------------------------------------------
# Worker consumption simulation
# ---------------------------------------------------------------------------

class TestWorkerConsumption:
    """Simulates a fake worker consuming commands without blocking reads."""

    def test_worker_drains_commands(self, execute_queue: CommandQueue) -> None:
        c1 = execute_queue.enqueue(command_type="pause", run_id="run-1")
        c2 = execute_queue.enqueue(command_type="resume", run_id="run-1")

        pending = execute_queue.poll("run-1")
        assert len(pending) == 2

        for cmd in pending:
            execute_queue.accept(cmd.command_id)
            execute_queue.apply(cmd.command_id)

        assert execute_queue.poll("run-1") == []

        hist = execute_queue.history("run-1")
        assert all(c.status == CommandStatus.applied for c in hist)

    def test_worker_rejects_unsupported(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(
            command_type="reprioritize", run_id="run-1"
        )
        execute_queue.reject(cmd.command_id, reason="unsupported by this worker")
        assert execute_queue.get(cmd.command_id).status == CommandStatus.rejected

    def test_worker_reports_failure(self, execute_queue: CommandQueue) -> None:
        cmd = execute_queue.enqueue(command_type="pause", run_id="run-1")
        execute_queue.accept(cmd.command_id)
        execute_queue.fail(cmd.command_id, reason="checkpoint unreachable")
        assert execute_queue.get(cmd.command_id).status == CommandStatus.failed
