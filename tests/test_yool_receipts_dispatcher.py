from __future__ import annotations

from pathlib import Path

import pytest

from sendsprint.yool.budgets import BudgetExceeded
from sendsprint.yool.catalog_v2 import YoolEntry
from sendsprint.yool.dispatcher import Dispatcher
from sendsprint.yool.receipts import (
    Receipt,
    ReceiptCost,
    ReceiptStore,
    sha256_canonical,
    write_ok_receipt,
)
from sendsprint.yool.tuples import AgentTerms


def make_entry(yool_id: str = "agent.dev.python.v1") -> YoolEntry:
    return YoolEntry(
        yool_id=yool_id,
        hash_bits="0",
        hash_hex="0",
        slots=(0, 0, 0, 0, 0, 0),
        tuple={"authority": "agent", "lane": "dev"},
    )


def test_sha256_canonical_is_deterministic_for_mapping_order() -> None:
    assert sha256_canonical({"a": 1, "b": 2}) == sha256_canonical({"b": 2, "a": 1})


def test_receipt_store_put_get_and_idempotent_rewrite(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path)
    receipt = Receipt(
        id=f"sha256:{'1' * 64}",
        yool_id="agent.dev.python.v1",
        input_id=f"sha256:{'2' * 64}",
        output_id=f"sha256:{'3' * 64}",
        output_payload={"status": "ok"},
        started_at="2026-05-19T19:00:00.000000Z",
        ended_at="2026-05-19T19:00:01.000000Z",
    )

    assert store.put(receipt) == receipt.id
    assert store.put(receipt) == receipt.id

    loaded = store.get(receipt.id)
    assert loaded is not None
    assert loaded.to_dict() == receipt.to_dict()


def test_receipt_store_find_by_input_hit_and_miss(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path)
    payload = {"ticket": 79}
    ok_receipt = write_ok_receipt(
        store,
        yool_id="agent.dev.python.v1",
        input_payload=payload,
        output_payload={"status": "ok"},
        started_at="2026-05-19T19:05:00.000000Z",
        ended_at="2026-05-19T19:05:01.000000Z",
    )

    found = store.find_by_input("agent.dev.python.v1", sha256_canonical(payload))
    assert found is not None
    assert found.id == ok_receipt.id
    assert store.find_by_input("agent.dev.python.v1", sha256_canonical({"ticket": 80})) is None
    assert store.find_by_input("agent.review.python.v1", sha256_canonical(payload)) is None


def test_receipt_store_find_by_input_prefers_latest_success_after_reload(tmp_path: Path) -> None:
    input_id = sha256_canonical({"ticket": 80})
    old_receipt = Receipt(
        id=f"sha256:{'0' * 64}",
        yool_id="agent.dev.python.v1",
        input_id=input_id,
        output_id=f"sha256:{'4' * 64}",
        output_payload={"version": "old"},
        started_at="2026-05-19T19:10:00.000000Z",
        ended_at="2026-05-19T19:10:01.000000Z",
    )
    new_receipt = Receipt(
        id=f"sha256:{'f' * 64}",
        yool_id="agent.dev.python.v1",
        input_id=input_id,
        output_id=f"sha256:{'5' * 64}",
        output_payload={"version": "new"},
        started_at="2026-05-19T19:11:00.000000Z",
        ended_at="2026-05-19T19:11:01.000000Z",
    )

    store = ReceiptStore(tmp_path)
    store.put(old_receipt)
    store.put(new_receipt)

    reloaded = ReceiptStore(tmp_path)
    found = reloaded.find_by_input("agent.dev.python.v1", input_id)
    assert found is not None
    assert found.id == new_receipt.id


def test_dispatcher_cache_miss_then_hit_avoids_second_executor_call(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path)
    entry = make_entry()
    calls: list[dict[str, int]] = []

    def executor(_entry: YoolEntry, payload: dict[str, int]) -> dict[str, int]:
        calls.append(payload)
        return {"doubled": payload["value"] * 2}

    dispatcher = Dispatcher(store=store, executor=executor)

    first = dispatcher.dispatch(entry, {"value": 21})
    second = dispatcher.dispatch(entry, {"value": 21})

    assert first.cached is False
    assert first.output == {"doubled": 42}
    assert second.cached is True
    assert second.receipt.id == first.receipt.id
    assert second.output == {"doubled": 42}
    assert calls == [{"value": 21}]


def test_dispatcher_no_cache_bypasses_lookup_and_writes_new_receipt(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path)
    entry = make_entry()
    calls: list[dict[str, int]] = []

    def executor(_entry: YoolEntry, payload: dict[str, int]) -> dict[str, int]:
        calls.append(payload)
        return {"doubled": payload["value"] * 2}

    dispatcher = Dispatcher(store=store, executor=executor)

    first = dispatcher.dispatch(entry, {"value": 7})
    second = dispatcher.dispatch(entry, {"value": 7}, no_cache=True)

    assert first.cached is False
    assert second.cached is False
    assert second.receipt.id != first.receipt.id
    assert calls == [{"value": 7}, {"value": 7}]


def test_dispatcher_payload_change_invalidates_cache(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path)
    entry = make_entry()
    calls: list[dict[str, int]] = []

    def executor(_entry: YoolEntry, payload: dict[str, int]) -> dict[str, int]:
        calls.append(payload)
        return {"doubled": payload["value"] * 2}

    dispatcher = Dispatcher(store=store, executor=executor)

    first = dispatcher.dispatch(entry, {"value": 3})
    second = dispatcher.dispatch(entry, {"value": 4})

    assert first.cached is False
    assert second.cached is False
    assert first.input_id != second.input_id
    assert calls == [{"value": 3}, {"value": 4}]


def test_dispatcher_marks_budget_exceeded_as_err_budget(tmp_path: Path) -> None:
    store = ReceiptStore(tmp_path)
    entry = make_entry()

    def executor(_entry: YoolEntry, payload: dict[str, int]) -> tuple[dict[str, int], ReceiptCost]:
        return {"echo": payload["value"]}, ReceiptCost(
            tokens_in=8, tokens_out=8, wall_ms=10, usd=0.25
        )

    dispatcher = Dispatcher(store=store, executor=executor, executor_returns_cost=True)

    with pytest.raises(BudgetExceeded):
        dispatcher.dispatch(
            entry,
            {"value": 1},
            agent_terms=AgentTerms(max_tokens=10, max_wall_ms=100, max_cost_usd=1.0),
        )

    receipts = list(store.all())
    assert receipts[0].status == "err.budget"
