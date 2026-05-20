"""Content-addressable receipt store.

Receipts are the merkle chain of work — never deleted, only artifact
bodies (the materialized outputs) get GC'd. Stored as one JSON file per
receipt under ``.sendsprint/receipts/<sha256[:2]>/<sha256>.json``.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import DEFAULT_RECEIPT_ROOT

ReceiptStatus = str  # "ok" | "err" | "err.budget"


def utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def sha256_canonical(payload: Any) -> str:
    """Stable hash of any JSON-serialisable payload."""
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


@dataclass
class ReceiptCost:
    tokens_in: int = 0
    tokens_out: int = 0
    wall_ms: int = 0
    usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Receipt:
    id: str
    yool_id: str
    input_id: str
    output_id: str | None
    output_payload: Any | None
    started_at: str
    ended_at: str
    cost: ReceiptCost = field(default_factory=ReceiptCost)
    status: ReceiptStatus = "ok"
    err: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "yool_id": self.yool_id,
            "input_id": self.input_id,
            "output_id": self.output_id,
            "output_payload": self.output_payload,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "cost": self.cost.to_dict(),
            "status": self.status,
            "err": self.err,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Receipt:
        cost = ReceiptCost(**(data.get("cost") or {}))
        return cls(
            id=data["id"],
            yool_id=data["yool_id"],
            input_id=data["input_id"],
            output_id=data.get("output_id"),
            output_payload=data.get("output_payload"),
            started_at=data["started_at"],
            ended_at=data["ended_at"],
            cost=cost,
            status=data.get("status", "ok"),
            err=data.get("err"),
        )


def make_receipt_id(*, yool_id: str, input_id: str, output_id: str | None, started_at: str) -> str:
    digest = hashlib.sha256(
        f"{yool_id}|{input_id}|{output_id or ''}|{started_at}".encode()
    ).hexdigest()
    return f"sha256:{digest}"


def _strip_prefix(receipt_id: str) -> str:
    return receipt_id.split(":", 1)[1] if ":" in receipt_id else receipt_id


def _atomic_write(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(target.parent), prefix=".tmp.", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fp:
            fp.write(text)
            fp.flush()
            os.fsync(fp.fileno())
        os.replace(tmp, target)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


class ReceiptStore:
    """Content-addressable JSON receipt store."""

    def __init__(self, root: str | Path = DEFAULT_RECEIPT_ROOT) -> None:
        self.root = Path(root)
        self._index: dict[tuple[str, str], str] = {}
        self._index_loaded = False

    def _path(self, receipt_id: str) -> Path:
        hex_id = _strip_prefix(receipt_id)
        return self.root / hex_id[:2] / f"{hex_id}.json"

    def put(self, receipt: Receipt) -> str:
        target = self._path(receipt.id)
        _atomic_write(
            target,
            json.dumps(receipt.to_dict(), sort_keys=True, ensure_ascii=False),
        )
        if receipt.status == "ok":
            self._index[(receipt.yool_id, receipt.input_id)] = receipt.id
        return receipt.id

    def get(self, receipt_id: str) -> Receipt | None:
        target = self._path(receipt_id)
        if not target.exists():
            return None
        return Receipt.from_dict(json.loads(target.read_text(encoding="utf-8")))

    def find_by_input(self, yool_id: str, input_id: str) -> Receipt | None:
        self._ensure_index()
        rid = self._index.get((yool_id, input_id))
        if rid is None:
            return None
        return self.get(rid)

    def all(self) -> Iterator[Receipt]:
        if not self.root.exists():
            return
        for path in sorted(self.root.rglob("*.json")):
            try:
                yield Receipt.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, KeyError):
                continue

    def _ensure_index(self) -> None:
        if self._index_loaded:
            return
        winners: dict[tuple[str, str], Receipt] = {}
        for r in self.all():
            if r.status == "ok":
                key = (r.yool_id, r.input_id)
                cur = winners.get(key)
                if cur is None or _receipt_sort_key(cur) < _receipt_sort_key(r):
                    winners[key] = r
        self._index = {key: receipt.id for key, receipt in winners.items()}
        self._index_loaded = True

    def invalidate_index(self) -> None:
        self._index.clear()
        self._index_loaded = False


def write_ok_receipt(
    store: ReceiptStore,
    *,
    yool_id: str,
    input_payload: Any,
    output_payload: Any,
    started_at: str,
    ended_at: str,
    cost: ReceiptCost | None = None,
) -> Receipt:
    input_id = sha256_canonical(input_payload)
    output_id = sha256_canonical(output_payload)
    rid = make_receipt_id(
        yool_id=yool_id, input_id=input_id, output_id=output_id, started_at=started_at
    )
    receipt = Receipt(
        id=rid,
        yool_id=yool_id,
        input_id=input_id,
        output_id=output_id,
        output_payload=output_payload,
        started_at=started_at,
        ended_at=ended_at,
        cost=cost or ReceiptCost(),
        status="ok",
        err=None,
    )
    store.put(receipt)
    return receipt


def write_err_receipt(
    store: ReceiptStore,
    *,
    yool_id: str,
    input_payload: Any,
    started_at: str,
    ended_at: str,
    err: str,
    status: ReceiptStatus = "err",
    cost: ReceiptCost | None = None,
) -> Receipt:
    input_id = sha256_canonical(input_payload)
    rid = make_receipt_id(yool_id=yool_id, input_id=input_id, output_id=None, started_at=started_at)
    receipt = Receipt(
        id=rid,
        yool_id=yool_id,
        input_id=input_id,
        output_id=None,
        output_payload=None,
        started_at=started_at,
        ended_at=ended_at,
        cost=cost or ReceiptCost(),
        status=status,
        err=err,
    )
    store.put(receipt)
    return receipt


def _receipt_sort_key(receipt: Receipt) -> tuple[str, str, str]:
    return (receipt.ended_at, receipt.started_at, receipt.id)
