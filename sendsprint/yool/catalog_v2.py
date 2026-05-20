"""Load and lookup spec-shaped HAMT catalog (`.catalog/agents.json`).

Read path complements ``scripts/build_agent_catalog.py``. Lookup walks the
trie ``slots[0..MAX_LEVELS-1]`` for O(log n) (~O(1) at branching=32) access.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import DEFAULT_AGENT_CATALOG_PATH

BITS_PER_LEVEL = 5
BRANCH = 1 << BITS_PER_LEVEL
MAX_LEVELS = 6
HASH_BITS = BITS_PER_LEVEL * MAX_LEVELS


def yool_hash(yool_id: str) -> int:
    digest = hashlib.blake2b(yool_id.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & ((1 << HASH_BITS) - 1)


def slot_at(h: int, level: int) -> int:
    shift = (MAX_LEVELS - 1 - level) * BITS_PER_LEVEL
    return (h >> shift) & (BRANCH - 1)


def yool_slots(h: int) -> list[int]:
    return [slot_at(h, lvl) for lvl in range(MAX_LEVELS)]


@dataclass(frozen=True)
class YoolEntry:
    yool_id: str
    hash_bits: str
    hash_hex: str
    slots: tuple[int, ...]
    tuple: dict[str, Any]

    @property
    def authority(self) -> str:
        return str(self.tuple.get("authority", ""))

    @property
    def lane(self) -> str:
        return str(self.tuple.get("lane", ""))

    @property
    def guardrails(self) -> dict[str, Any]:
        return dict(self.tuple.get("guardrails", {}))


class CatalogError(RuntimeError):
    """Raised when the catalog file is missing or malformed."""


def load_catalog(path: str | Path = DEFAULT_AGENT_CATALOG_PATH) -> dict[str, Any]:
    target = Path(path)
    if not target.exists():
        raise CatalogError(
            f"catalog not found at {target}; run `python scripts/build_agent_catalog.py` first"
        )
    return json.loads(target.read_text(encoding="utf-8"))


def _entry_from_flat(yool_id: str, payload: dict[str, Any]) -> YoolEntry:
    return YoolEntry(
        yool_id=yool_id,
        hash_bits=str(payload.get("hash", "")),
        hash_hex=str(payload.get("hash_hex", "")),
        slots=tuple(int(s) for s in payload.get("slots", [])),
        tuple=dict(payload.get("tuple", {})),
    )


def list_yools(catalog: dict[str, Any]) -> list[YoolEntry]:
    flat = catalog.get("flat") or {}
    return [_entry_from_flat(k, v) for k, v in sorted(flat.items())]


def find_yools(catalog: dict[str, Any], query: str) -> list[YoolEntry]:
    q = query.lower()
    return [e for e in list_yools(catalog) if q in e.yool_id.lower()]


def _walk_trie(node: Any, h: int, level: int = 0) -> dict[str, Any] | None:
    kind = node.get("kind")
    if kind == "leaf":
        return node
    if kind == "collision":
        return node
    if kind == "node":
        if level >= MAX_LEVELS:
            return None
        slot = slot_at(h, level)
        children = node.get("children") or {}
        child = children.get(str(slot))
        if child is None:
            return None
        return _walk_trie(child, h, level + 1)
    return None


def lookup_yool(catalog: dict[str, Any], yool_id: str) -> YoolEntry | None:
    """O(log_32 n) HAMT walk via slots. Falls back to flat for safety."""
    trie = catalog.get("trie")
    flat = catalog.get("flat") or {}
    if isinstance(trie, dict):
        h = yool_hash(yool_id)
        leaf = _walk_trie(trie, h, 0)
        if leaf is not None:
            if leaf.get("kind") == "leaf" and leaf.get("key") == yool_id:
                payload = flat.get(yool_id, {})
                return _entry_from_flat(yool_id, payload) if payload else None
            if leaf.get("kind") == "collision":
                for sub in leaf.get("leaves") or []:
                    if sub.get("key") == yool_id:
                        payload = flat.get(yool_id, {})
                        return _entry_from_flat(yool_id, payload) if payload else None
    payload = flat.get(yool_id)
    if payload is None:
        return None
    return _entry_from_flat(yool_id, payload)


def yools_by_lane(catalog: dict[str, Any], lane: str) -> list[YoolEntry]:
    return [e for e in list_yools(catalog) if e.lane == lane]


def yools_by_authority(catalog: dict[str, Any], authority: str) -> list[YoolEntry]:
    return [e for e in list_yools(catalog) if e.authority == authority]


def to_table_rows(entries: Iterable[YoolEntry]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for e in entries:
        g = e.guardrails
        rows.append(
            {
                "yool_id": e.yool_id,
                "authority": e.authority,
                "lane": e.lane,
                "cpu%": str(g.get("cpu_quota_pct", "")),
                "disk_mb": str(g.get("disk_quota_mb", "")),
                "timeout_s": str(g.get("timeout_s", "")),
                "description": str(e.tuple.get("description", "")),
            }
        )
    return rows
