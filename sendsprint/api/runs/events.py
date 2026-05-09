"""In-memory event broker for live run streams.

Runs publish events into a per-run asyncio.Queue. SSE handlers consume from
that queue and forward to the mobile client. Background workers in a thread
push via ``publish_threadsafe`` since SprintFlow is sync.
"""

from __future__ import annotations

import asyncio
from typing import Any

_loop: asyncio.AbstractEventLoop | None = None
_queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


def queue_for(run_id: str) -> asyncio.Queue[dict[str, Any]]:
    q = _queues.get(run_id)
    if q is None:
        q = asyncio.Queue()
        _queues[run_id] = q
    return q


async def publish(run_id: str, event: dict[str, Any]) -> None:
    await queue_for(run_id).put(event)


def publish_threadsafe(run_id: str, event: dict[str, Any]) -> None:
    if _loop is None:
        return
    asyncio.run_coroutine_threadsafe(publish(run_id, event), _loop)


async def drain(run_id: str) -> dict[str, Any]:
    return await queue_for(run_id).get()


def close(run_id: str) -> None:
    _queues.pop(run_id, None)
