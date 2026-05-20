"""Async lane subscribers (issue #84, spec §9).

A ``Worker`` subscribes to one bus lane, pulls each tuple, dispatches it
through the cache-aware ``Dispatcher``, writes a status marker back to
the tuple log, and emits follow-up tuples produced by the executor.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from typing import Any

from .budgets import BudgetExceeded
from .bus import TupleBus
from .catalog_v2 import YoolEntry, lookup_yool
from .dispatcher import Dispatcher
from .receipts import Receipt, sha256_canonical
from .tuples import Tuple, TupleLog, emit_tuple

LOG = logging.getLogger(__name__)

FollowUp = tuple[str, str, Any]  # (yool_id, lane, payload)
ExecutorFn = Callable[[YoolEntry, Tuple], Any]
AsyncExecutorFn = Callable[[YoolEntry, Tuple], Awaitable[Any]]


@dataclass
class WorkerStats:
    consumed: int = 0
    cached: int = 0
    succeeded: int = 0
    failed: int = 0
    budget_exceeded: int = 0


class Worker:
    """Subscribes to one lane and routes tuples through the dispatcher."""

    def __init__(
        self,
        *,
        lane: str,
        bus: TupleBus,
        log: TupleLog,
        catalog: dict[str, Any],
        dispatcher: Dispatcher,
        run_id: str,
        follow_up: Callable[[Tuple, Any], Iterable[FollowUp]] | None = None,
    ) -> None:
        self.lane = lane
        self.bus = bus
        self.log = log
        self.catalog = catalog
        self.dispatcher = dispatcher
        self.run_id = run_id
        self.follow_up = follow_up or (lambda _t, _o: ())
        self.stats = WorkerStats()

    async def run(self) -> None:
        async for tup in self.bus.subscribe(self.lane):
            await self._handle(tup)

    async def _handle(self, tup: Tuple) -> None:
        self.stats.consumed += 1
        self.log.update_status(tup.id, "consumed")
        entry = lookup_yool(self.catalog, tup.yool_id)
        if entry is None:
            self.log.update_status(tup.id, "err")
            self.stats.failed += 1
            LOG.warning("unknown yool_id %s on lane %s", tup.yool_id, self.lane)
            return
        try:
            result = await asyncio.to_thread(
                self.dispatcher.dispatch,
                entry,
                tup.payload,
                no_cache=self._no_cache(tup),
                agent_terms=tup.agent_terms,
            )
        except BudgetExceeded as exc:
            self.stats.budget_exceeded += 1
            self.log.update_status(
                tup.id,
                "err.budget",
                receipt_id=self._latest_receipt_id(entry.yool_id, tup.payload),
            )
            LOG.warning("budget exceeded on %s: %s", tup.yool_id, exc)
            return
        except Exception as exc:  # noqa: BLE001
            self.stats.failed += 1
            self.log.update_status(
                tup.id,
                "err",
                receipt_id=self._latest_receipt_id(entry.yool_id, tup.payload),
            )
            LOG.exception("worker %s failed on %s: %s", self.lane, tup.yool_id, exc)
            return

        if result.cached:
            self.stats.cached += 1
        self.stats.succeeded += 1
        self.log.update_status(tup.id, "completed", receipt_id=result.receipt.id)

        for child_yool, child_lane, child_payload in self.follow_up(tup, result.output):
            child = emit_tuple(
                yool_id=child_yool,
                lane=child_lane,
                payload=child_payload,
                run_id=self.run_id,
                parent_id=tup.id,
                agent_terms=tup.agent_terms,
            )
            self.log.append(child)
            await self.bus.publish(child)

    def _latest_receipt_id(self, yool_id: str, payload: Any) -> str | None:
        input_id = sha256_canonical(payload)
        matches = [
            receipt
            for receipt in self.dispatcher.store.all()
            if receipt.yool_id == yool_id and receipt.input_id == input_id
        ]
        if not matches:
            return None
        latest = max(matches, key=_receipt_sort_key)
        return latest.id

    def _no_cache(self, tup: Tuple) -> bool:
        if tup.meta.get("no_cache"):
            return True
        if isinstance(tup.payload, dict):
            return bool(tup.payload.get("no_cache"))
        return False


class WorkerPool:
    """Lane-keyed pool that runs each Worker as an asyncio task."""

    def __init__(self) -> None:
        self._workers: dict[str, Worker] = {}
        self._tasks: dict[str, asyncio.Task[None]] = {}

    def add(self, worker: Worker) -> None:
        if worker.lane in self._workers:
            raise ValueError(f"lane already bound: {worker.lane}")
        self._workers[worker.lane] = worker

    def start(self) -> None:
        for lane, worker in self._workers.items():
            self._tasks[lane] = asyncio.create_task(worker.run(), name=f"worker:{lane}")

    async def run_until_idle(self, *, bus: TupleBus, seed: Iterable[Tuple] | None = None) -> None:
        seed = list(seed or ())
        self.start()
        try:
            for tup in seed:
                await bus.publish(tup)
            await bus.drain()
            await self.join()
        finally:
            await self.shutdown()

    async def join(self) -> None:
        if not self._tasks:
            return
        await asyncio.gather(*self._tasks.values(), return_exceptions=True)

    async def shutdown(self) -> None:
        for task in self._tasks.values():
            task.cancel()
        for task in self._tasks.values():
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()

    def stats(self) -> dict[str, WorkerStats]:
        return {lane: w.stats for lane, w in self._workers.items()}


def _receipt_sort_key(receipt: Receipt) -> tuple[str, str, str]:
    return (receipt.ended_at, receipt.started_at, receipt.id)
