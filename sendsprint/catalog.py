"""HAMT-backed agent capability catalog.

Wraps :mod:`sendsprint.agent_registry` with content-addressed lookup as
defined by the yool/tuple/HAMT spec (vendored at
``docs/YOOL_TUPLE_HAMT.md``). Each capability becomes a ``yool``:

    agent.<provider_key>.<capability_key>

Entries carry the mandatory guardrails from spec §11 (Victor's note):
``cpu_quota_pct`` and ``disk_quota_mb``. Catalog persists to
``.catalog/hamt.json`` as canonical JSON.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .agent_registry import (
    AgentCapability,
    AgentProvider,
    AgentRegistry,
    default_agent_registry,
)

BITS_PER_LEVEL = 5
BRANCH = 1 << BITS_PER_LEVEL  # 32
MAX_LEVELS = 6
HASH_BITS = BITS_PER_LEVEL * MAX_LEVELS  # 30
HASH_MASK = (1 << HASH_BITS) - 1

NodeKind = Literal["leaf", "branch"]


class CatalogEntry(BaseModel):
    """One yool entry inside the HAMT."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    yool_id: str
    provider_key: str
    capability_key: str
    description: str
    cost_profile: str
    parallel_safe: bool
    requires_clean_worktree: bool
    cpu_quota_pct: int = 60
    disk_quota_mb: int = 100
    timeout_s: int = 300


class CatalogNode(BaseModel):
    """HAMT node — either a leaf bucket or an internal branch."""

    model_config = ConfigDict(extra="forbid")

    kind: NodeKind
    entries: list[CatalogEntry] = Field(default_factory=list)
    children: dict[int, CatalogNode] = Field(default_factory=dict)


CatalogNode.model_rebuild()


def hash_yool(yool_id: str) -> int:
    """blake2b-64 truncated to 30 bits per spec §3."""
    digest = hashlib.blake2b(yool_id.encode("utf-8"), digest_size=8).digest()
    return int.from_bytes(digest, "big") & HASH_MASK


def _index_at_level(h: int, level: int) -> int:
    return (h >> (BITS_PER_LEVEL * level)) & (BRANCH - 1)


def _insert(node: CatalogNode, entry: CatalogEntry, level: int) -> CatalogNode:
    if level >= MAX_LEVELS:
        return CatalogNode(
            kind="leaf",
            entries=[*[e for e in node.entries if e.yool_id != entry.yool_id], entry],
        )
    if node.kind == "leaf":
        if not node.entries:
            return CatalogNode(kind="leaf", entries=[entry])
        if any(e.yool_id == entry.yool_id for e in node.entries):
            return CatalogNode(
                kind="leaf",
                entries=[entry if e.yool_id == entry.yool_id else e for e in node.entries],
            )
        promoted = CatalogNode(kind="branch")
        for existing in node.entries:
            promoted = _insert(promoted, existing, level)
        return _insert(promoted, entry, level)
    idx = _index_at_level(hash_yool(entry.yool_id), level)
    child = node.children.get(idx, CatalogNode(kind="leaf"))
    new_child = _insert(child, entry, level + 1)
    new_children = {**node.children, idx: new_child}
    return CatalogNode(kind="branch", entries=[], children=new_children)


def _lookup(node: CatalogNode, yool_id: str, h: int, level: int) -> CatalogEntry | None:
    if node.kind == "leaf":
        for entry in node.entries:
            if entry.yool_id == yool_id:
                return entry
        return None
    if level >= MAX_LEVELS:
        return None
    idx = _index_at_level(h, level)
    child = node.children.get(idx)
    if child is None:
        return None
    return _lookup(child, yool_id, h, level + 1)


def entry_from_capability(
    provider: AgentProvider,
    capability: AgentCapability,
    *,
    cpu_quota_pct: int = 60,
    disk_quota_mb: int = 100,
    timeout_s: int = 300,
) -> CatalogEntry:
    return CatalogEntry(
        yool_id=f"agent.{provider.key}.{capability.key}",
        provider_key=provider.key,
        capability_key=capability.key,
        description=capability.description,
        cost_profile=capability.cost_profile,
        parallel_safe=capability.parallel_safe,
        requires_clean_worktree=capability.requires_clean_worktree,
        cpu_quota_pct=cpu_quota_pct,
        disk_quota_mb=disk_quota_mb,
        timeout_s=timeout_s,
    )


def build_agent_catalog(registry: AgentRegistry | None = None) -> CatalogNode:
    """Build a HAMT catalog from a registry (default registry if None)."""
    registry = registry if registry is not None else default_agent_registry()
    root = CatalogNode(kind="branch")
    for provider in registry.providers:
        for cap in provider.capabilities:
            root = _insert(root, entry_from_capability(provider, cap), 0)
    return root


def lookup_yool(catalog: CatalogNode, yool_id: str) -> CatalogEntry | None:
    return _lookup(catalog, yool_id, hash_yool(yool_id), 0)


def list_entries(catalog: CatalogNode) -> list[CatalogEntry]:
    out: list[CatalogEntry] = []

    def _walk(node: CatalogNode) -> None:
        if node.kind == "leaf":
            out.extend(node.entries)
            return
        for _, child in sorted(node.children.items()):
            _walk(child)

    _walk(catalog)
    return sorted(out, key=lambda e: e.yool_id)


def find_entries(catalog: CatalogNode, query: str) -> list[CatalogEntry]:
    q = query.lower()
    return [e for e in list_entries(catalog) if q in e.yool_id.lower()]


def to_canonical_json(catalog: CatalogNode) -> str:
    return json.dumps(
        catalog.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def save_catalog(catalog: CatalogNode, path: Path | str) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(to_canonical_json(catalog) + "\n", encoding="utf-8")
    return target


def load_catalog(path: Path | str) -> CatalogNode:
    raw = Path(path).read_text(encoding="utf-8")
    return CatalogNode.model_validate(json.loads(raw))


DEFAULT_CATALOG_PATH = Path(".catalog/hamt.json")
