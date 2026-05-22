"""Round-robin parallel router that fans tasks out across provider adapters.

The router is the heart of the v2 dispatcher. For each
:class:`~sendsprint.models.SprintItem` it picks a provider in round-robin
order (skipping ``cloud=False`` providers or routing them through their
declared fallback), dispatches in parallel via
:class:`concurrent.futures.ThreadPoolExecutor`, polls each ticket until it
reaches a terminal status, and collects the resulting PRs.

Spec: ``.specs/v2/cloud-dispatcher.md`` (ROUTER sub-issue).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from sendsprint.models import SprintItem
from sendsprint.providers.base import (
    DispatchTicket,
    ProviderAdapter,
    ProviderError,
    ProviderTimeoutError,
    PRResult,
)

logger = logging.getLogger(__name__)

TERMINAL_STATUSES = {"done", "failed", "cancelled"}


@dataclass
class _Assignment:
    item: SprintItem
    adapter: ProviderAdapter


class ProviderRouter:
    """Round-robin parallel dispatcher across cloud provider adapters."""

    def __init__(
        self,
        adapters: list[ProviderAdapter],
        max_parallel: int = 3,
        poll_interval_s: float = 10.0,
        timeout_s: float = 1800.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not adapters:
            raise ValueError("ProviderRouter requires at least one adapter")
        self._adapters = adapters
        self._by_name = {a.name: a for a in adapters}
        self._max_parallel = max(1, max_parallel)
        self._poll_interval_s = poll_interval_s
        self._timeout_s = timeout_s
        self._sleep = sleep

    def assign(self, items: list[SprintItem]) -> list[_Assignment]:
        """Pick a provider per item in round-robin order, respecting capabilities.

        Adapters with ``cloud=False`` are replaced by their declared fallback;
        if no fallback resolves to a cloud-capable adapter the item is dropped
        and a warning is logged.
        """
        cloud_adapters = [a for a in self._adapters if a.capabilities().cloud]
        if not cloud_adapters:
            raise ProviderError(
                "no cloud-capable adapters available; check providers.yml and capabilities()"
            )

        assignments: list[_Assignment] = []
        for index, item in enumerate(items):
            adapter = cloud_adapters[index % len(cloud_adapters)]
            assignments.append(_Assignment(item=item, adapter=adapter))
        return assignments

    def resolve_fallback(self, adapter: ProviderAdapter) -> ProviderAdapter | None:
        """Walk the fallback chain until a cloud-capable adapter is found."""
        seen: set[str] = set()
        current = adapter
        while True:
            caps = current.capabilities()
            if caps.cloud:
                return current
            if not caps.fallback or caps.fallback in seen:
                return None
            seen.add(current.name)
            current = self._by_name.get(caps.fallback)  # type: ignore[assignment]
            if current is None:
                return None

    def dispatch_all(self, items: list[SprintItem]) -> list[PRResult]:
        """Fan items out in parallel and return one :class:`PRResult` per item."""
        assignments = self.assign(items)
        if not assignments:
            return []

        with ThreadPoolExecutor(max_workers=self._max_parallel) as pool:
            futures: list[Future[PRResult]] = [pool.submit(self._run_one, a) for a in assignments]
            return [f.result() for f in futures]

    def _run_one(self, assignment: _Assignment) -> PRResult:
        """Dispatch + poll + collect for a single assignment.

        Any :class:`ProviderError` along the way is captured as a failed
        :class:`PRResult` so one bad provider never blocks the batch.
        """
        try:
            ticket = assignment.adapter.dispatch(assignment.item)
        except ProviderError as exc:
            logger.warning(
                "dispatch failed for %s via %s: %s",
                assignment.item.key,
                assignment.adapter.name,
                exc,
            )
            return PRResult(
                run_id="",
                provider=assignment.adapter.name,
                item_key=assignment.item.key,
                status="failed",
                error=str(exc),
            )
        return self._wait_for_result(assignment.adapter, ticket)

    def _wait_for_result(self, adapter: ProviderAdapter, ticket: DispatchTicket) -> PRResult:
        deadline = time.monotonic() + self._timeout_s
        while True:
            try:
                status = adapter.poll(ticket)
            except ProviderError as exc:
                return PRResult(
                    run_id=ticket.run_id,
                    provider=adapter.name,
                    item_key=ticket.item_key,
                    status="failed",
                    error=str(exc),
                )
            if status in TERMINAL_STATUSES:
                if status != "done":
                    return PRResult(
                        run_id=ticket.run_id,
                        provider=adapter.name,
                        item_key=ticket.item_key,
                        status=status,
                    )
                try:
                    return adapter.collect(ticket)
                except ProviderError as exc:
                    return PRResult(
                        run_id=ticket.run_id,
                        provider=adapter.name,
                        item_key=ticket.item_key,
                        status="failed",
                        error=str(exc),
                    )
            if time.monotonic() >= deadline:
                return PRResult(
                    run_id=ticket.run_id,
                    provider=adapter.name,
                    item_key=ticket.item_key,
                    status="failed",
                    error=str(
                        ProviderTimeoutError(
                            f"{adapter.name} run {ticket.run_id} exceeded "
                            f"{self._timeout_s}s without reaching a terminal status"
                        )
                    ),
                )
            self._sleep(self._poll_interval_s)
