"""In-process async tuple bus with named lanes (issue #83)."""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from typing import Any

from .tuples import Tuple

SENTINEL: Any = object()


class TupleBus:
    """Many-lane fan-out queue."""

    def __init__(self, *, maxsize: int = 64) -> None:
        self._maxsize = maxsize
        self._lanes: dict[str, asyncio.Queue[Any]] = {}
        self._closed = False

    def _queue(self, lane: str) -> asyncio.Queue[Any]:
        if lane not in self._lanes:
            self._lanes[lane] = asyncio.Queue(maxsize=self._maxsize)
        return self._lanes[lane]

    @property
    def lanes(self) -> list[str]:
        return sorted(self._lanes.keys())

    async def publish(self, tup: Tuple) -> None:
        if self._closed:
            raise RuntimeError("bus is closed")
        await self._queue(tup.lane).put(tup)

    def publish_nowait(self, tup: Tuple) -> bool:
        if self._closed:
            return False
        try:
            self._queue(tup.lane).put_nowait(tup)
            return True
        except asyncio.QueueFull:
            return False

    async def subscribe(self, lane: str) -> AsyncIterator[Tuple]:
        queue = self._queue(lane)
        while True:
            item = await queue.get()
            try:
                if item is SENTINEL:
                    return
                yield item
            finally:
                queue.task_done()

    async def drain(self) -> None:
        while True:
            queues = list(self._lanes.values())
            for queue in queues:
                await queue.join()
            if len(queues) == len(self._lanes):
                break
        await self.close()

    async def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        for queue in self._lanes.values():
            while True:
                with contextlib.suppress(asyncio.QueueFull):
                    queue.put_nowait(SENTINEL)
                    break
                await asyncio.sleep(0)

    def stats(self) -> dict[str, int]:
        return {lane: q.qsize() for lane, q in self._lanes.items()}
