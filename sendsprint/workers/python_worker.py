"""Pure-Python asyncio worker — always-available fallback.

Implements the WorkerCapability contract from contracts.py with:
- asyncio task queue (bounded)
- start / cancel / heartbeat / status / log_tail operations
- CPU nice / memory soft-limit / fan-out concurrency cap
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
import uuid
from collections import deque
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, cast

try:
    import resource
except ImportError:  # Windows
    resource = None  # type: ignore[assignment]

from sendsprint.contracts import (
    CommandType,
    EventType,
    RunCommand,
    RunEvent,
    WorkerCapability,
    WorkerStack,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
DEFAULT_MAX_CONCURRENCY = 4
DEFAULT_QUEUE_SIZE = 64
DEFAULT_CPU_NICE = 10  # os.nice increment (lower priority)
DEFAULT_MEM_LIMIT_MB = 512
DEFAULT_HEARTBEAT_INTERVAL_S = 5
DEFAULT_LOG_TAIL_LINES = 50


class TaskState(StrEnum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


@dataclass
class WorkerTask:
    """Internal bookkeeping for a queued/running task."""

    run_id: str
    command: RunCommand
    state: TaskState = TaskState.queued
    created_at: float = field(default_factory=time.monotonic)
    started_at: float | None = None
    finished_at: float | None = None
    error: str | None = None
    _handle: asyncio.Task[RunEvent] | None = field(default=None, repr=False)


class PythonWorker:
    """Asyncio-based worker implementing the RunCommand/RunEvent protocol.

    This is the ALWAYS-AVAILABLE fallback when no external Go/Rust/Node
    worker binary is present.
    """

    def __init__(
        self,
        *,
        worker_id: str | None = None,
        max_concurrency: int = DEFAULT_MAX_CONCURRENCY,
        queue_size: int = DEFAULT_QUEUE_SIZE,
        cpu_nice: int = DEFAULT_CPU_NICE,
        mem_limit_mb: int = DEFAULT_MEM_LIMIT_MB,
        heartbeat_interval_s: float = DEFAULT_HEARTBEAT_INTERVAL_S,
        executor: Callable[[RunCommand], Coroutine[Any, Any, RunEvent]] | None = None,
    ) -> None:
        self.worker_id = worker_id or f"py-{uuid.uuid4().hex[:8]}"
        self.max_concurrency = max_concurrency
        self.queue_size = queue_size
        self.cpu_nice = cpu_nice
        self.mem_limit_mb = mem_limit_mb
        self.heartbeat_interval_s = heartbeat_interval_s

        self._executor = executor or self._default_executor
        self._tasks: dict[str, WorkerTask] = {}
        self._log_buffer: deque[str] = deque(maxlen=500)
        self._semaphore: asyncio.Semaphore | None = None
        self._started = False
        self._last_heartbeat: float = 0.0

    # -- lifecycle -----------------------------------------------------------

    async def start(self) -> None:
        """Initialise the worker: apply resource limits, create semaphore."""
        if self._started:
            return
        self._apply_resource_limits()
        self._semaphore = asyncio.Semaphore(self.max_concurrency)
        self._started = True
        self._last_heartbeat = time.monotonic()
        self._log(f"worker {self.worker_id} started (concurrency={self.max_concurrency})")

    async def stop(self) -> None:
        """Cancel all in-flight tasks and shut down."""
        for wt in list(self._tasks.values()):
            if wt.state in (TaskState.queued, TaskState.running):
                await self.cancel(wt.run_id)
        self._started = False
        self._log(f"worker {self.worker_id} stopped")

    # -- operations ----------------------------------------------------------

    async def queue(self, command: RunCommand) -> str:
        """Enqueue a command for execution. Returns run_id."""
        if not self._started:
            raise RuntimeError("worker not started")
        if len([t for t in self._tasks.values() if t.state == TaskState.queued]) >= self.queue_size:
            raise RuntimeError(f"queue full ({self.queue_size})")

        run_id = command.run_id
        wt = WorkerTask(run_id=run_id, command=command)
        self._tasks[run_id] = wt
        self._log(f"queued {run_id} ({command.command_type.value})")

        assert self._semaphore is not None
        wt._handle = asyncio.create_task(self._run_task(wt))
        return run_id

    async def cancel(self, run_id: str) -> RunEvent:
        """Cancel a running or queued task."""
        wt = self._tasks.get(run_id)
        if wt is None:
            raise KeyError(f"unknown run_id: {run_id}")
        if wt.state in (TaskState.completed, TaskState.failed, TaskState.cancelled):
            return self._event(run_id, EventType.cancelled, error="already terminal")

        wt.state = TaskState.cancelled
        wt.finished_at = time.monotonic()
        if wt._handle and not wt._handle.done():
            wt._handle.cancel()
        self._log(f"cancelled {run_id}")
        return self._event(run_id, EventType.cancelled)

    def heartbeat(self) -> RunEvent:
        """Return a heartbeat event with worker status summary."""
        self._last_heartbeat = time.monotonic()
        active = [t for t in self._tasks.values() if t.state == TaskState.running]
        queued = [t for t in self._tasks.values() if t.state == TaskState.queued]
        return self._event(
            run_id="__heartbeat__",
            event_type=EventType.heartbeat,
            data={
                "worker_id": self.worker_id,
                "active": len(active),
                "queued": len(queued),
                "total": len(self._tasks),
                "uptime_s": round(time.monotonic() - self._last_heartbeat, 2),
            },
        )

    def status(self, run_id: str | None = None) -> dict[str, Any]:
        """Snapshot of one task or all tasks."""
        if run_id:
            wt = self._tasks.get(run_id)
            if wt is None:
                raise KeyError(f"unknown run_id: {run_id}")
            return self._task_snapshot(wt)
        return {
            "worker_id": self.worker_id,
            "started": self._started,
            "tasks": {rid: self._task_snapshot(wt) for rid, wt in self._tasks.items()},
        }

    def log_tail(self, n: int = DEFAULT_LOG_TAIL_LINES) -> list[str]:
        """Return the last *n* log lines."""
        items = list(self._log_buffer)
        return items[-n:]

    def capability(self) -> WorkerCapability:
        """Return the WorkerCapability descriptor for this worker."""
        return WorkerCapability(
            worker_id=self.worker_id,
            stack=WorkerStack.python,
            supported_commands=list(CommandType),
            max_concurrency=self.max_concurrency,
            metadata={
                "queue_size": self.queue_size,
                "cpu_nice": self.cpu_nice,
                "mem_limit_mb": self.mem_limit_mb,
            },
        )

    # -- internals -----------------------------------------------------------

    async def _run_task(self, wt: WorkerTask) -> RunEvent:
        """Execute a single task under the concurrency semaphore."""
        assert self._semaphore is not None
        async with self._semaphore:
            if wt.state == TaskState.cancelled:
                return self._event(wt.run_id, EventType.cancelled)

            wt.state = TaskState.running
            wt.started_at = time.monotonic()
            self._log(f"started {wt.run_id}")

            try:
                event = await asyncio.wait_for(
                    self._executor(wt.command),
                    timeout=wt.command.timeout_s,
                )
                wt.state = TaskState.completed
                wt.finished_at = time.monotonic()
                self._log(f"completed {wt.run_id}")
                return event
            except asyncio.CancelledError:
                wt.state = TaskState.cancelled
                wt.finished_at = time.monotonic()
                self._log(f"cancelled {wt.run_id}")
                return self._event(wt.run_id, EventType.cancelled)
            except TimeoutError:
                wt.state = TaskState.failed
                wt.error = f"timeout after {wt.command.timeout_s}s"
                wt.finished_at = time.monotonic()
                self._log(f"timeout {wt.run_id}")
                return self._event(wt.run_id, EventType.failed, error=wt.error)
            except Exception as exc:
                wt.state = TaskState.failed
                wt.error = str(exc)
                wt.finished_at = time.monotonic()
                self._log(f"failed {wt.run_id}: {exc}")
                return self._event(wt.run_id, EventType.failed, error=wt.error)

    @staticmethod
    async def _default_executor(command: RunCommand) -> RunEvent:
        """Placeholder executor — returns completed immediately."""
        return RunEvent(
            event_type=EventType.completed,
            run_id=command.run_id,
            source_stack=WorkerStack.python,
            data={"command_type": command.command_type.value, "note": "default executor"},
        )

    def _apply_resource_limits(self) -> None:
        """Best-effort CPU nice + memory soft limit on platforms that support it."""
        if hasattr(os, "nice"):
            try:
                os.nice(self.cpu_nice)
            except (OSError, PermissionError):
                logger.debug("os.nice(%d) skipped (not permitted)", self.cpu_nice)

        if resource is None:
            logger.debug("resource limits skipped (resource module unavailable)")
            return

        try:
            resource_module = cast(Any, resource)
            soft, hard = resource_module.getrlimit(resource_module.RLIMIT_AS)
            new_soft = self.mem_limit_mb * 1024 * 1024
            if hard != resource_module.RLIM_INFINITY and new_soft > hard:
                new_soft = hard
            resource_module.setrlimit(resource_module.RLIMIT_AS, (new_soft, hard))
        except (ValueError, OSError):
            logger.debug("RLIMIT_AS skipped (platform may not support it)")

    def _event(
        self,
        run_id: str,
        event_type: EventType,
        *,
        data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> RunEvent:
        return RunEvent(
            event_type=event_type,
            run_id=run_id,
            source_stack=WorkerStack.python,
            data=data or {},
            error=error,
        )

    def _task_snapshot(self, wt: WorkerTask) -> dict[str, Any]:
        return {
            "run_id": wt.run_id,
            "command_type": wt.command.command_type.value,
            "state": wt.state.value,
            "created_at": wt.created_at,
            "started_at": wt.started_at,
            "finished_at": wt.finished_at,
            "error": wt.error,
        }

    def _log(self, msg: str) -> None:
        ts = datetime.now(UTC).isoformat(timespec="seconds")
        line = f"[{ts}] {msg}"
        self._log_buffer.append(line)
        logger.debug(line)
