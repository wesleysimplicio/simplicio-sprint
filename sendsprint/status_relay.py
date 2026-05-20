"""Tri-agent status relay for Claude, Codex, and Hermes during active loops.

Emits structured run events, exposes read-only snapshots, and formats
status answers per agent (Claude: markdown, Codex: structured JSON,
Hermes: concise plain text).  Control commands are queued safely so
the worker loop is never blocked by status queries.

See: https://github.com/wesleysimplicio/SendSprint/issues/111
"""

from __future__ import annotations

import json
import threading
from collections import deque
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.contracts import EventType, RunEvent

# ---------------------------------------------------------------------------
# Run event emitter
# ---------------------------------------------------------------------------

AgentName = Literal["claude", "codex", "hermes"]


class RunEventEmitter:
    """Thread-safe emitter that appends RunEvents to a shared log."""

    def __init__(self, run_id: str, max_history: int = 500) -> None:
        self.run_id = run_id
        self._lock = threading.Lock()
        self._events: deque[RunEvent] = deque(maxlen=max_history)

    def emit(self, event_type: EventType | str, data: dict[str, Any] | None = None) -> RunEvent:
        """Create and store a RunEvent, returning it for optional chaining."""
        if isinstance(event_type, str):
            event_type = EventType(event_type)
        event = RunEvent(
            event_type=event_type,
            run_id=self.run_id,
            data=data or {},
        )
        with self._lock:
            self._events.append(event)
        return event

    def history(self, limit: int = 50) -> list[RunEvent]:
        """Return the most recent *limit* events (newest last)."""
        with self._lock:
            items = list(self._events)
        return items[-limit:]

    def __len__(self) -> int:
        with self._lock:
            return len(self._events)


# ---------------------------------------------------------------------------
# Read-only snapshot model
# ---------------------------------------------------------------------------


class RunSnapshot(BaseModel):
    """Point-in-time read-only view of a run's status."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    current_action: str = "idle"
    failures: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_step: str = ""
    active_agents: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    pr_links: list[str] = Field(default_factory=list)
    last_command: str = ""
    last_evidence: str = ""
    event_count: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Queued control commands
# ---------------------------------------------------------------------------

ControlAction = Literal["pause", "resume", "cancel", "change_autonomy", "reprioritize", "approve", "reject"]


class ControlCommand(BaseModel):
    """Explicit operator mutation queued for safe consumption by the worker."""

    model_config = ConfigDict(extra="forbid")

    action: ControlAction
    issued_by: AgentName
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# StatusRelay — core orchestrator
# ---------------------------------------------------------------------------


class StatusRelay:
    """Non-blocking relay between the worker loop and conversational agents.

    * ``update_snapshot`` — called by the worker to publish state.
    * ``get_snapshot``    — read-only, safe to call from any agent thread.
    * ``format_for_*``    — agent-specific formatters.
    * ``enqueue_command`` / ``drain_commands`` — safe command queue.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._snapshots: dict[str, RunSnapshot] = {}
        self._command_queue: deque[ControlCommand] = deque(maxlen=200)

    # -- snapshot management ------------------------------------------------

    def update_snapshot(self, snapshot: RunSnapshot) -> None:
        """Publish or replace the snapshot for a given run_id."""
        with self._lock:
            self._snapshots[snapshot.run_id] = snapshot

    def get_snapshot(self, run_id: str) -> RunSnapshot | None:
        """Return the latest snapshot for *run_id*, or None."""
        with self._lock:
            return self._snapshots.get(run_id)

    def list_runs(self) -> list[str]:
        """Return all tracked run IDs."""
        with self._lock:
            return list(self._snapshots.keys())

    # -- command queue ------------------------------------------------------

    def enqueue_command(self, command: ControlCommand) -> None:
        """Queue a control command for the worker to consume."""
        with self._lock:
            self._command_queue.append(command)

    def drain_commands(self) -> list[ControlCommand]:
        """Pop all queued commands (worker calls this each tick)."""
        with self._lock:
            cmds = list(self._command_queue)
            self._command_queue.clear()
        return cmds

    def pending_commands(self) -> int:
        """Number of commands waiting."""
        with self._lock:
            return len(self._command_queue)

    # -- agent formatters ---------------------------------------------------

    def format_for_claude(self, run_id: str) -> str:
        """Markdown-formatted status for Claude (rich, readable)."""
        snap = self.get_snapshot(run_id)
        if snap is None:
            return f"No active run found for `{run_id}`."

        lines = [
            f"## Run `{snap.run_id}`",
            "",
            f"**Current action:** {snap.current_action}",
            f"**Next step:** {snap.next_step or 'N/A'}",
            f"**Active agents:** {', '.join(snap.active_agents) or 'none'}",
            f"**Events emitted:** {snap.event_count}",
            f"**Last command:** {snap.last_command or 'N/A'}",
            f"**Last evidence:** {snap.last_evidence or 'N/A'}",
        ]

        if snap.blockers:
            lines.append("")
            lines.append("### Blockers")
            for b in snap.blockers:
                lines.append(f"- {b}")

        if snap.failures:
            lines.append("")
            lines.append("### Failures")
            for f in snap.failures:
                lines.append(f"- {f}")

        if snap.pr_links:
            lines.append("")
            lines.append("### Open PRs")
            for pr in snap.pr_links:
                lines.append(f"- {pr}")

        if snap.evidence_refs:
            lines.append("")
            lines.append("### Evidence")
            for ref in snap.evidence_refs[:5]:
                lines.append(f"- {ref}")
            if len(snap.evidence_refs) > 5:
                lines.append(f"- … and {len(snap.evidence_refs) - 5} more")

        return "\n".join(lines)

    def format_for_codex(self, run_id: str) -> str:
        """Structured JSON status for Codex (machine-parseable)."""
        snap = self.get_snapshot(run_id)
        if snap is None:
            return json.dumps({"error": "no_active_run", "run_id": run_id})

        payload = {
            "run_id": snap.run_id,
            "current_action": snap.current_action,
            "next_step": snap.next_step,
            "active_agents": snap.active_agents,
            "event_count": snap.event_count,
            "last_command": snap.last_command,
            "last_evidence": snap.last_evidence,
            "blockers": snap.blockers,
            "failures": snap.failures,
            "pr_links": snap.pr_links,
            "evidence_refs": snap.evidence_refs[:10],
            "evidence_total": len(snap.evidence_refs),
            "updated_at": snap.updated_at.isoformat(),
        }
        return json.dumps(payload, indent=2)

    def format_for_hermes(self, run_id: str) -> str:
        """Concise plain-text status for Hermes (minimal, action-oriented)."""
        snap = self.get_snapshot(run_id)
        if snap is None:
            return f"[{run_id}] no active run"

        parts = [f"[{snap.run_id}] {snap.current_action}"]

        if snap.next_step:
            parts.append(f"next: {snap.next_step}")

        if snap.blockers:
            parts.append(f"BLOCKED: {'; '.join(snap.blockers)}")

        if snap.failures:
            parts.append(f"failures: {len(snap.failures)}")

        if snap.pr_links:
            parts.append(f"PRs: {len(snap.pr_links)}")

        if snap.active_agents:
            parts.append(f"agents: {','.join(snap.active_agents)}")

        return " | ".join(parts)
