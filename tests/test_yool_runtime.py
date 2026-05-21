from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from sendsprint.yool.bus import TupleBus
from sendsprint.yool.catalog_v2 import yool_hash, yool_slots
from sendsprint.yool.dispatcher import Dispatcher
from sendsprint.yool.receipts import ReceiptStore
from sendsprint.yool.runtime import (
    dispatch_yool,
    inspect_run,
    resume_run,
    run_worker_pool,
)
from sendsprint.yool.tuples import TupleLog, emit_tuple
from sendsprint.yool.workers import Worker, WorkerPool


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
        await worker._handle(parent)

        review_stream = bus.subscribe("review")
        child = await asyncio.wait_for(anext(review_stream), timeout=5)
        assert child.parent_id == parent.id
        await review_stream.aclose()
        await bus.close()

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
        first = emit_tuple(yool_id="agent.codex.plan", lane="dev", payload={"n": 1}, run_id="r")
        second = emit_tuple(yool_id="agent.codex.plan", lane="dev", payload={"n": 2}, run_id="r")
        await bus.publish(first)
        await bus.publish(second)
        await task
        await bus.close()

    asyncio.run(scenario())
    assert seen == [1, 2]


def test_worker_records_error_receipt_on_tuple_status(tmp_path: Path) -> None:
    catalog = json.loads(_write_catalog(tmp_path).read_text(encoding="utf-8"))
    bus = TupleBus()
    log = TupleLog("run-err", tmp_path / ".sendsprint" / "tuples")
    store = ReceiptStore(tmp_path / ".sendsprint" / "receipts")

    def executor(_entry, _payload):
        raise RuntimeError("boom")

    dispatcher = Dispatcher(store=store, executor=executor)
    worker = Worker(
        lane="dev",
        bus=bus,
        log=log,
        catalog=catalog,
        dispatcher=dispatcher,
        run_id="run-err",
    )
    pool = WorkerPool()
    pool.add(worker)

    parent = emit_tuple(
        yool_id="agent.codex.plan",
        lane="dev",
        payload={"task": "explode"},
        run_id="run-err",
    )
    log.append(parent)

    run_worker_pool(pool, bus=bus, run_id="run-err", tuple_root=log.root, receipt_root=store.root)

    tuple_state = {item.id: item for item in log.tuples()}[parent.id]
    assert tuple_state.status == "err"
    assert tuple_state.receipt_id is not None

    receipt = store.get(tuple_state.receipt_id)
    assert receipt is not None
    assert receipt.status == "err"
    assert receipt.err == "RuntimeError: boom"


def test_run_worker_pool_replays_pending_tuples_and_returns_stats(tmp_path: Path) -> None:
    catalog = json.loads(_write_catalog(tmp_path).read_text(encoding="utf-8"))
    bus = TupleBus()
    tuple_root = tmp_path / ".sendsprint" / "tuples"
    receipt_root = tmp_path / ".sendsprint" / "receipts"
    log = TupleLog("run-pool", tuple_root)
    store = ReceiptStore(receipt_root)

    def executor(entry, payload):
        return {"handled": entry.yool_id, "payload": payload}

    dispatcher = Dispatcher(store=store, executor=executor)
    worker = Worker(
        lane="dev",
        bus=bus,
        log=log,
        catalog=catalog,
        dispatcher=dispatcher,
        run_id="run-pool",
        follow_up=lambda _t, _o: [("agent.codex.plan", "review", {"child": True})],
    )
    review_worker = Worker(
        lane="review",
        bus=bus,
        log=log,
        catalog=catalog,
        dispatcher=dispatcher,
        run_id="run-pool",
    )
    pool = WorkerPool()
    pool.add(worker)
    pool.add(review_worker)

    parent = emit_tuple(
        yool_id="agent.codex.plan",
        lane="dev",
        payload={"task": 1},
        run_id="run-pool",
    )
    log.append(parent)

    inspected = run_worker_pool(
        pool,
        bus=bus,
        run_id="run-pool",
        tuple_root=tuple_root,
        receipt_root=receipt_root,
    )

    assert inspected["seed_ids"] == [parent.id]
    assert inspected["pending_ids"] == []
    assert inspected["worker_stats"]["dev"]["consumed"] == 1
    assert inspected["worker_stats"]["review"]["consumed"] == 1
    assert len(inspected["receipts"]) == 2


def test_worker_pool_runs_same_lane_tuples_concurrently(tmp_path: Path) -> None:
    catalog = json.loads(_write_catalog(tmp_path).read_text(encoding="utf-8"))
    bus = TupleBus()
    tuple_root = tmp_path / ".sendsprint" / "tuples"
    receipt_root = tmp_path / ".sendsprint" / "receipts"
    log = TupleLog("run-fast", tuple_root)
    store = ReceiptStore(receipt_root)
    lock = threading.Lock()
    active = 0
    max_active = 0

    def executor(entry, payload):
        nonlocal active, max_active
        del payload
        with lock:
            active += 1
            max_active = max(max_active, active)
        try:
            time.sleep(0.05)
            return {"handled": entry.yool_id}
        finally:
            with lock:
                active -= 1

    dispatcher = Dispatcher(store=store, executor=executor)
    worker = Worker(
        lane="dev",
        bus=bus,
        log=log,
        catalog=catalog,
        dispatcher=dispatcher,
        run_id="run-fast",
    )
    pool = WorkerPool(default_concurrency=4)
    pool.add(worker)

    for index in range(4):
        tup = emit_tuple(
            yool_id="agent.codex.plan",
            lane="dev",
            payload={"task": index},
            run_id="run-fast",
        )
        log.append(tup)

    inspected = run_worker_pool(
        pool,
        bus=bus,
        run_id="run-fast",
        tuple_root=tuple_root,
        receipt_root=receipt_root,
    )

    assert inspected["pending_ids"] == []
    assert inspected["worker_stats"]["dev"]["consumed"] == 4
    assert inspected["worker_task_counts"]["dev"] == 4
    assert max_active >= 2


def test_resume_after_kill_replays_pending_tuple(tmp_path: Path) -> None:
    catalog = json.loads(_write_catalog(tmp_path).read_text(encoding="utf-8"))
    tuple_root = tmp_path / ".sendsprint" / "tuples"
    receipt_root = tmp_path / ".sendsprint" / "receipts"
    script = tmp_path / "seed_and_sleep.py"
    script.write_text(
        (
            "import time\n"
            "from pathlib import Path\n"
            "from sendsprint.yool.tuples import TupleLog, emit_tuple\n\n"
            f'tuple_root = Path(r"{tuple_root}")\n'
            "log = TupleLog('run-kill', tuple_root)\n"
            "tup = emit_tuple(\n"
            "    yool_id='agent.codex.plan',\n"
            "    lane='dev',\n"
            "    payload={'task': 'resume'},\n"
            "    run_id='run-kill',\n"
            ")\n"
            "log.append(tup)\n"
            "time.sleep(30)\n"
        ),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in [str(Path.cwd()), env.get("PYTHONPATH", "")] if part
    )
    proc = subprocess.Popen([sys.executable, str(script)], cwd=str(tmp_path), env=env)
    try:
        deadline = time.time() + 10
        log_path = tuple_root / "run-kill.ndjson"
        while time.time() < deadline and not log_path.exists():
            time.sleep(0.1)
        assert log_path.exists()
    finally:
        proc.kill()
        proc.wait(timeout=10)

    replay = resume_run("run-kill", tuple_root=tuple_root)
    assert replay["re_emitted"] == 1

    bus = TupleBus()
    log = TupleLog("run-kill", tuple_root)
    store = ReceiptStore(receipt_root)

    def executor(entry, payload):
        return {"handled": entry.yool_id, "payload": payload}

    dispatcher = Dispatcher(store=store, executor=executor)
    worker = Worker(
        lane="dev",
        bus=bus,
        log=log,
        catalog=catalog,
        dispatcher=dispatcher,
        run_id="run-kill",
    )
    pool = WorkerPool()
    pool.add(worker)

    inspected = run_worker_pool(
        pool,
        bus=bus,
        run_id="run-kill",
        tuple_root=tuple_root,
        receipt_root=receipt_root,
    )

    assert inspected["pending_ids"] == []
    assert inspected["worker_stats"]["dev"]["consumed"] == 1
