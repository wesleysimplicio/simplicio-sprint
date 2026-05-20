"""Append-only tuple log + parent-chain DAG walker.

Each tuple is a JSON line in ``.sendsprint/tuples/<run_id>.ndjson``. Writes
are fsync'd per line so a ``kill -9`` cannot lose committed work. The
``parent_id`` field links a tuple to its producer, forming a DAG.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import DEFAULT_TUPLE_ROOT


def utcnow_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def make_run_id(prefix: str = "run") -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    suffix = hashlib.blake2b(
        f"{ts}-{os.getpid()}-{os.urandom(8).hex()}".encode(), digest_size=4
    ).hexdigest()
    return f"{prefix}-{ts}-{suffix}"


def make_tuple_id(
    *,
    yool_id: str,
    lane: str,
    parent_id: str | None,
    payload: Any,
    ts: str,
) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(
        f"{yool_id}|{lane}|{parent_id or ''}|{canonical}|{ts}".encode()
    ).hexdigest()
    return f"sha256:{digest}"


@dataclass
class AgentTerms:
    max_tokens: int = 0
    max_wall_ms: int = 0
    max_cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AgentTerms:
        data = data or {}
        return cls(
            max_tokens=int(data.get("max_tokens", 0)),
            max_wall_ms=int(data.get("max_wall_ms", 0)),
            max_cost_usd=float(data.get("max_cost_usd", 0.0)),
        )


@dataclass
class Tuple:
    id: str
    run_id: str
    yool_id: str
    lane: str
    parent_id: str | None
    payload: Any
    ts: str
    status: str = "emitted"  # emitted | consumed | completed | err | err.budget
    receipt_id: str | None = None
    agent_terms: AgentTerms = field(default_factory=AgentTerms)
    meta: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "run_id": self.run_id,
            "yool_id": self.yool_id,
            "lane": self.lane,
            "parent_id": self.parent_id,
            "payload": self.payload,
            "ts": self.ts,
            "status": self.status,
            "receipt_id": self.receipt_id,
            "agent_terms": self.agent_terms.to_dict(),
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tuple:
        return cls(
            id=data["id"],
            run_id=data["run_id"],
            yool_id=data["yool_id"],
            lane=data["lane"],
            parent_id=data.get("parent_id"),
            payload=data.get("payload"),
            ts=data["ts"],
            status=data.get("status", "emitted"),
            receipt_id=data.get("receipt_id"),
            agent_terms=AgentTerms.from_dict(data.get("agent_terms")),
            meta=dict(data.get("meta") or {}),
        )


def emit_tuple(
    *,
    yool_id: str,
    lane: str,
    payload: Any,
    run_id: str,
    parent_id: str | None = None,
    agent_terms: AgentTerms | None = None,
    meta: dict[str, Any] | None = None,
) -> Tuple:
    ts = utcnow_iso()
    tid = make_tuple_id(yool_id=yool_id, lane=lane, parent_id=parent_id, payload=payload, ts=ts)
    return Tuple(
        id=tid,
        run_id=run_id,
        yool_id=yool_id,
        lane=lane,
        parent_id=parent_id,
        payload=payload,
        ts=ts,
        agent_terms=agent_terms or AgentTerms(),
        meta=meta or {},
    )


class TupleLog:
    """Append-only NDJSON log keyed by ``run_id``."""

    def __init__(self, run_id: str, root: str | Path = DEFAULT_TUPLE_ROOT) -> None:
        self.run_id = run_id
        self.root = Path(root)
        self.path = self.root / f"{run_id}.ndjson"

    def append(self, tup: Tuple) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(tup.to_dict(), sort_keys=True, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as fp:
            fp.write(line + "\n")
            fp.flush()
            os.fsync(fp.fileno())

    def update_status(self, tuple_id: str, status: str, receipt_id: str | None = None) -> None:
        marker = {
            "kind": "status",
            "id": tuple_id,
            "status": status,
            "receipt_id": receipt_id,
            "ts": utcnow_iso(),
            "run_id": self.run_id,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(marker, sort_keys=True, ensure_ascii=False) + "\n")
            fp.flush()
            os.fsync(fp.fileno())

    def iter_raw(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with open(self.path, encoding="utf-8") as fp:
            for line in fp:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue

    def materialise(self) -> dict[str, Tuple]:
        """Replay log → effective tuple state map keyed by tuple id."""
        store: dict[str, Tuple] = {}
        for raw in self.iter_raw():
            kind = raw.get("kind")
            if kind == "status":
                tid = raw.get("id")
                if tid in store:
                    existing = store[tid]
                    existing.status = raw.get("status", existing.status)
                    if raw.get("receipt_id"):
                        existing.receipt_id = raw["receipt_id"]
                continue
            if "id" in raw and "yool_id" in raw:
                tup = Tuple.from_dict(raw)
                store[tup.id] = tup
        return store

    def tuples(self) -> list[Tuple]:
        return list(self.materialise().values())

    def pending(self) -> list[Tuple]:
        return [t for t in self.tuples() if t.status in {"emitted", "consumed"}]

    def completed(self) -> list[Tuple]:
        return [t for t in self.tuples() if t.status == "completed"]


def parent_chain(tuples: Iterable[Tuple], tuple_id: str) -> list[Tuple]:
    by_id = {t.id: t for t in tuples}
    chain: list[Tuple] = []
    cur: Tuple | None = by_id.get(tuple_id)
    while cur is not None:
        chain.append(cur)
        cur = by_id.get(cur.parent_id) if cur.parent_id else None
    return chain


def render_ascii_tree(tuples: Iterable[Tuple]) -> str:
    items = list(tuples)
    by_parent: dict[str | None, list[Tuple]] = {}
    for t in sorted(items, key=lambda x: x.ts):
        by_parent.setdefault(t.parent_id, []).append(t)

    lines: list[str] = []

    def _walk(node: Tuple, prefix: str, last: bool) -> None:
        connector = "└── " if last else "├── "
        label = f"{node.yool_id} [{node.lane}] id={node.id[:14]}… status={node.status}"
        lines.append(f"{prefix}{connector}{label}")
        children = by_parent.get(node.id, [])
        new_prefix = prefix + ("    " if last else "│   ")
        for i, child in enumerate(children):
            _walk(child, new_prefix, i == len(children) - 1)

    roots = by_parent.get(None, [])
    for i, root in enumerate(roots):
        _walk(root, "", i == len(roots) - 1)
    return "\n".join(lines)


def list_runs(root: str | Path = DEFAULT_TUPLE_ROOT) -> list[str]:
    base = Path(root)
    if not base.exists():
        return []
    return sorted(p.stem for p in base.glob("*.ndjson"))
