"""Audited control-command queue for active runs.

Operator actions (pause, resume, cancel, reprioritize, change_autonomy,
approve) flow through a typed command queue with autonomy policy checks,
lifecycle tracking, and audit records.  Workers poll at safe checkpoints;
the queue never blocks status reads.

See: https://github.com/wesleysimplicio/SendSprint/issues/115
"""

from __future__ import annotations

import threading
import uuid
from collections import defaultdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.policy import AutonomyLevel, AutonomyPolicy
from sendsprint.status_relay import ControlAction

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class CommandStatus(StrEnum):
    """Lifecycle states for a control command."""

    queued = "queued"
    accepted = "accepted"
    rejected = "rejected"
    applied = "applied"
    failed = "failed"


# Map control actions to the minimum autonomy level required to accept them.
COMMAND_AUTONOMY_REQUIREMENTS: dict[ControlAction, AutonomyLevel] = {
    "pause": "observe",
    "resume": "observe",
    "cancel": "execute",
    "change_autonomy": "plan",
    "reprioritize": "plan",
    "approve": "pr",
    "reject": "plan",
}


# ---------------------------------------------------------------------------
# RunControlCommand model
# ---------------------------------------------------------------------------


class RunControlCommand(BaseModel):
    """Typed, audited operator command targeting an active run."""

    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    command_type: ControlAction
    run_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    issued_by: str = "operator"
    status: CommandStatus = CommandStatus.queued
    reason: str = ""

    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    accepted_at: datetime | None = None
    applied_at: datetime | None = None
    resolved_at: datetime | None = None


# ---------------------------------------------------------------------------
# CommandQueue
# ---------------------------------------------------------------------------


class CommandQueue:
    """Thread-safe, audited command queue with policy enforcement.

    Usage::

        queue = CommandQueue(policy=AutonomyPolicy(level="execute"))
        cmd = queue.enqueue(command_type="pause", run_id="run-abc")
        pending = queue.poll("run-abc")
        queue.accept(cmd.command_id)
        queue.apply(cmd.command_id)
    """

    def __init__(self, policy: AutonomyPolicy | None = None) -> None:
        self._lock = threading.Lock()
        self._commands: dict[str, RunControlCommand] = {}
        self._by_run: dict[str, list[str]] = defaultdict(list)
        self._policy = policy or AutonomyPolicy(level="plan")

    @property
    def policy(self) -> AutonomyPolicy:
        return self._policy

    # -- enqueue ------------------------------------------------------------

    def enqueue(
        self,
        *,
        command_type: ControlAction,
        run_id: str,
        params: dict[str, Any] | None = None,
        issued_by: str = "operator",
        command_id: str | None = None,
    ) -> RunControlCommand:
        """Create and enqueue a command, enforcing autonomy policy.

        Returns the command with status ``queued`` on success.
        Raises ``CommandPolicyError`` if the autonomy level forbids it.
        Raises ``DuplicateCommandError`` if *command_id* already exists.
        """
        required_level = COMMAND_AUTONOMY_REQUIREMENTS.get(command_type, "plan")
        if not self._policy.allows_level(required_level):
            raise CommandPolicyError(
                f"autonomy level '{self._policy.level}' does not allow "
                f"'{command_type}' (requires '{required_level}')"
            )

        if command_id:
            cmd = RunControlCommand(
                command_type=command_type,
                run_id=run_id,
                params=params or {},
                issued_by=issued_by,
                command_id=command_id,
            )
        else:
            cmd = RunControlCommand(
                command_type=command_type,
                run_id=run_id,
                params=params or {},
                issued_by=issued_by,
            )

        with self._lock:
            if cmd.command_id in self._commands:
                raise DuplicateCommandError(f"command '{cmd.command_id}' already exists")
            self._commands[cmd.command_id] = cmd
            self._by_run[run_id].append(cmd.command_id)

        return cmd

    # -- poll ---------------------------------------------------------------

    def poll(self, run_id: str) -> list[RunControlCommand]:
        """Return all ``queued`` commands for *run_id* (worker calls this)."""
        with self._lock:
            ids = self._by_run.get(run_id, [])
            return [
                self._commands[cid]
                for cid in ids
                if self._commands[cid].status == CommandStatus.queued
            ]

    # -- lifecycle transitions -----------------------------------------------

    def accept(self, command_id: str) -> RunControlCommand:
        """Move a command from ``queued`` to ``accepted``."""
        with self._lock:
            cmd = self._get(command_id)
            self._require_status(cmd, CommandStatus.queued, "accept")
            cmd.status = CommandStatus.accepted
            cmd.accepted_at = datetime.now(UTC)
            return cmd

    def apply(self, command_id: str) -> RunControlCommand:
        """Move a command from ``accepted`` to ``applied``."""
        with self._lock:
            cmd = self._get(command_id)
            self._require_status(cmd, CommandStatus.accepted, "apply")
            cmd.status = CommandStatus.applied
            cmd.applied_at = datetime.now(UTC)
            cmd.resolved_at = datetime.now(UTC)
            return cmd

    def reject(self, command_id: str, *, reason: str = "") -> RunControlCommand:
        """Move a command from ``queued`` to ``rejected``."""
        with self._lock:
            cmd = self._get(command_id)
            self._require_status(cmd, CommandStatus.queued, "reject")
            cmd.status = CommandStatus.rejected
            cmd.reason = reason
            cmd.resolved_at = datetime.now(UTC)
            return cmd

    def fail(self, command_id: str, *, reason: str = "") -> RunControlCommand:
        """Move an ``accepted`` command to ``failed``."""
        with self._lock:
            cmd = self._get(command_id)
            self._require_status(cmd, CommandStatus.accepted, "fail")
            cmd.status = CommandStatus.failed
            cmd.reason = reason
            cmd.resolved_at = datetime.now(UTC)
            return cmd

    # -- queries ------------------------------------------------------------

    def get(self, command_id: str) -> RunControlCommand:
        """Return a command by id."""
        with self._lock:
            return self._get(command_id)

    def history(self, run_id: str) -> list[RunControlCommand]:
        """Return all commands for *run_id* in insertion order."""
        with self._lock:
            ids = self._by_run.get(run_id, [])
            return [self._commands[cid] for cid in ids]

    def __len__(self) -> int:
        with self._lock:
            return len(self._commands)

    # -- internals ----------------------------------------------------------

    def _get(self, command_id: str) -> RunControlCommand:
        """Retrieve command or raise ``CommandNotFoundError``."""
        try:
            return self._commands[command_id]
        except KeyError:
            raise CommandNotFoundError(f"command '{command_id}' not found") from None

    @staticmethod
    def _require_status(
        cmd: RunControlCommand,
        expected: CommandStatus,
        action: str,
    ) -> None:
        if cmd.status != expected:
            raise InvalidCommandTransition(
                f"cannot {action} command '{cmd.command_id}': "
                f"status is '{cmd.status.value}', expected '{expected.value}'"
            )


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CommandQueueError(RuntimeError):
    """Base for all command queue errors."""


class CommandPolicyError(CommandQueueError):
    """Raised when autonomy policy blocks a command."""


class DuplicateCommandError(CommandQueueError):
    """Raised on duplicate command_id."""


class CommandNotFoundError(CommandQueueError):
    """Raised when a command_id is not in the queue."""


class InvalidCommandTransition(CommandQueueError):
    """Raised on illegal status transition."""
