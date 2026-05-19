from __future__ import annotations

import asyncio
import contextlib
import json
from pathlib import Path

from sendsprint.yool.bus import TupleBus
from sendsprint.yool.catalog_v2 import yool_hash, yool_slots
from sendsprint.yool.dispatcher import Dispatcher
from sendsprint.yool.receipts import ReceiptStore
from sendsprint.yool.runtime import dispatch_yool, inspect_run, resume_run
from sendsprint.yool.tuples import TupleLog, emit_tuple
from sendsprint.yool.workers import Worker


def _write_catalog(tmp_path: Path, yool_id: str = "agent.codex.plan") -> Path:
    h = yool_hash(yool_id)
    path = tmp_path / ".catalog" / "agents.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "meta": {"count": 1},
                "flat": {
                    yool_id: {
                        "hash": f"{h:030b}",
                        "hash_hex": f"{h:08x}",
                        "slots": yool_slots(h),
                        "tuple": {
                            "authority": "codex",
                            "lane": "dev",
                            "description": "Plan work",
                            "guardrails": {
                                "cpu_quota_pct": 60,
                                "disk_quota_mb": 100,
                                "timeout_s": 300,
                            },
                        },
                    }
                },
                "trie": {},
            }
        ),
        encoding="utf-8",
    )
    return path


def test_dispatch_inspect_and_resume_roundtrip(tmp_path: Path) -> None:
    catalog = _write_catalog(tmp_path)
    tuple_root = tmp_path / ".sendsprint" / "tuples"

    result = dispatch_yool(
        "agent.codex.plan",
        {"story": "APP-9"},
        catalog_path=catalog,
        tuple_root=tuple_root,
    )

    inspected = inspect_run(result["run_id"], tuple_root=tuple_root)
    assert inspected["tuples"][0]["yool_id"] == "agent.codex.plan"
    assert inspected["pending_ids"] == [result["id"]]

    resumed = resume_run(result["run_id"], tuple_root=tuple_root)
    assert resumed["re_emitted"] == 1
    assert resumed["pending_ids"] == [result["id"]]


def test_worker_consumes_lane_and_emits_child_tuple(tmp_path: Path) -> None:
    catalog = json.loads(_write_catalog(tmp_path).read_text(encoding="utf-8"))
    bus = TupleBus()
    log = TupleLog("run-1", tmp_path / ".sendsprint" / "tuples")
    store = ReceiptStore(tmp_path / ".sendsprint" / "receipts")

    def executor(entry, payload):
        return {"handled": entry.yool_id, "payload": payload}

    dispatcher = Dispatcher(store=store, executor=executor)
    worker = Worker(
        lane="dev",
        bus=bus,
        log=log,
        catalog=catalog,
        dispatcher=dispatcher,
        run_id="run-1",
        follow_up=lambda _t, _o: [("agent.codex.plan", "review", {"child": True})],
    )
    parent = emit_tuple(
        yool_id="agent.codex.plan",
        lane="dev",
        payload={"task": 1},
        run_id="run-1",
    )
    log.append(parent)

    async def scenario() -> None:
        task = asyncio.create_task(worker.run())

        async def drain_review() -> None:
            async for tup in bus.subscribe("review"):
                assert tup.parent_id == parent.id
                return

        review_task = asyncio.create_task(drain_review())
        await bus.publish(parent)
        await review_task
        await bus.drain()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task

    asyncio.run(scenario())

    tuples = {item.id: item for item in log.tuples()}
    assert tuples[parent.id].status == "completed"
    assert any(item.parent_id == parent.id for item in tuples.values())


def test_tuple_bus_preserves_order_within_lane() -> None:
    bus = TupleBus()
    seen: list[int] = []

    async def scenario() -> None:
        async def consumer() -> None:
            async for tup in bus.subscribe("dev"):
                seen.append(tup.payload["n"])
                if len(seen) == 2:
                    return

        task = asyncio.create_task(consumer())
        first = emit_tuple(
            yool_id="agent.codex.plan", lane="dev", payload={"n": 1}, run_id="r"
        )
        second = emit_tuple(
            yool_id="agent.codex.plan", lane="dev", payload={"n": 2}, run_id="r"
        )
        await bus.publish(first)
        await bus.publish(second)
        await task
        await bus.close()

    asyncio.run(scenario())
    assert seen == [1, 2]
