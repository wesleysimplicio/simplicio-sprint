"""Shared helpers for yool dispatch, inspect, snapshot, and resume surfaces."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import DEFAULT_AGENT_CATALOG_PATH, DEFAULT_RECEIPT_ROOT, DEFAULT_TUPLE_ROOT
from .catalog_v2 import CatalogError, load_catalog, lookup_yool
from .receipts import ReceiptStore
from .tuples import (
    AgentTerms,
    Tuple,
    TupleLog,
    emit_tuple,
    list_runs,
    make_run_id,
    render_ascii_tree,
)


def ensure_catalog(path: str | Path = DEFAULT_AGENT_CATALOG_PATH) -> dict[str, Any]:
    return load_catalog(path)


def dispatch_yool(
    yool_id: str,
    payload: Any,
    *,
    run_id: str | None = None,
    catalog_path: str | Path = DEFAULT_AGENT_CATALOG_PATH,
    tuple_root: str | Path = DEFAULT_TUPLE_ROOT,
    agent_terms: AgentTerms | None = None,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create and append a tuple for a yool using the shared catalog lookup path."""
    catalog = ensure_catalog(catalog_path)
    entry = lookup_yool(catalog, yool_id)
    if entry is None:
        raise CatalogError(f"unknown yool_id: {yool_id}")
    resolved_run_id = run_id or make_run_id("tuple")
    tup = emit_tuple(
        yool_id=yool_id,
        lane=entry.lane or "default",
        payload=payload,
        run_id=resolved_run_id,
        agent_terms=agent_terms,
        meta=meta,
    )
    log = TupleLog(resolved_run_id, tuple_root)
    log.append(tup)
    return tuple_summary(tup)


def resume_run(
    run_id: str,
    *,
    tuple_root: str | Path = DEFAULT_TUPLE_ROOT,
    republish: Callable[[Tuple], None] | None = None,
) -> dict[str, Any]:
    """Requeue pending tuples from an append-only log.

    In the current in-process runtime we treat resume as a deterministic replay of
    pending work descriptions: completed tuples stay untouched, and pending tuples
    are re-published via the provided hook or, lacking one, receive a fresh
    ``emitted`` status marker in the log so a consumer can pick them up later.
    """

    log = TupleLog(run_id, tuple_root)
    pending = log.pending()
    for tup in pending:
        if republish is not None:
            republish(tup)
        log.update_status(tup.id, "emitted")
    return {
        "run_id": run_id,
        "re_emitted": len(pending),
        "pending_ids": [t.id for t in pending],
        "completed_ids": [t.id for t in log.completed()],
    }


def inspect_run(
    run_id: str,
    *,
    tuple_root: str | Path = DEFAULT_TUPLE_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
) -> dict[str, Any]:
    log = TupleLog(run_id, tuple_root)
    tuples = sorted(log.tuples(), key=lambda item: item.ts)
    store = ReceiptStore(receipt_root)
    receipts: list[dict[str, Any]] = []
    per_yool: dict[str, dict[str, float | int]] = {}
    total = {"tokens_in": 0, "tokens_out": 0, "wall_ms": 0, "usd": 0.0}

    for tup in tuples:
        if not tup.receipt_id:
            continue
        receipt = store.get(tup.receipt_id)
        if receipt is None:
            continue
        payload = receipt.to_dict()
        payload["tuple_id"] = tup.id
        receipts.append(payload)
        row = per_yool.setdefault(
            tup.yool_id,
            {"tokens_in": 0, "tokens_out": 0, "wall_ms": 0, "usd": 0.0},
        )
        row["tokens_in"] += receipt.cost.tokens_in
        row["tokens_out"] += receipt.cost.tokens_out
        row["wall_ms"] += receipt.cost.wall_ms
        row["usd"] += receipt.cost.usd
        total["tokens_in"] += receipt.cost.tokens_in
        total["tokens_out"] += receipt.cost.tokens_out
        total["wall_ms"] += receipt.cost.wall_ms
        total["usd"] += receipt.cost.usd

    return {
        "run_id": run_id,
        "tuples": [tuple_summary(tup) for tup in tuples],
        "tree": render_ascii_tree(tuples),
        "pending_ids": [t.id for t in log.pending()],
        "completed_ids": [t.id for t in log.completed()],
        "receipts": receipts,
        "cost": {"per_yool": per_yool, "total": total},
    }


def snapshot(
    *,
    catalog_path: str | Path = DEFAULT_AGENT_CATALOG_PATH,
    tuple_root: str | Path = DEFAULT_TUPLE_ROOT,
    receipt_root: str | Path = DEFAULT_RECEIPT_ROOT,
    limit: int = 5,
) -> dict[str, Any]:
    catalog = ensure_catalog(catalog_path)
    recent_runs = list_runs(tuple_root)[-limit:]
    runs = [
        inspect_run(run_id, tuple_root=tuple_root, receipt_root=receipt_root)
        for run_id in recent_runs
    ]
    return {"catalog": catalog, "recent_runs": runs}


def parse_payload(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"payload must be valid JSON: {exc}") from exc


def tuple_summary(tup: Tuple) -> dict[str, Any]:
    return {
        "id": tup.id,
        "run_id": tup.run_id,
        "yool_id": tup.yool_id,
        "lane": tup.lane,
        "parent_id": tup.parent_id,
        "status": tup.status,
        "receipt_id": tup.receipt_id,
        "payload": tup.payload,
        "agent_terms": tup.agent_terms.to_dict(),
        "meta": tup.meta,
    }
