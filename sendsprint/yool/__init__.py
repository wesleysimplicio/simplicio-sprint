"""yool/tuple/HAMT primitives for SendSprint.

Vendored spec: https://github.com/wesleysimplicio/yool-tuple-hamt (v0.2).

Modules
-------
- ``catalog_v2``  Load + lookup spec-shaped HAMT catalog (`.catalog/agents.json`).
- ``receipts``    Content-addressable receipt store (`.sendsprint/receipts/...`).
- ``tuples``      Append-only tuple log with parent_id DAG.
- ``bus``         In-process async tuple bus with named lanes.
- ``budgets``     ``agent_terms`` budget enforcement.
- ``dispatcher``  Cache-aware sync dispatcher.
- ``workers``     Async lane subscribers (one per yool/capability).
"""

from __future__ import annotations

DEFAULT_AGENT_CATALOG_PATH = ".catalog/agents.json"
DEFAULT_RECEIPT_ROOT = ".sendsprint/receipts"
DEFAULT_TUPLE_ROOT = ".sendsprint/tuples"

__all__ = [
    "DEFAULT_AGENT_CATALOG_PATH",
    "DEFAULT_RECEIPT_ROOT",
    "DEFAULT_TUPLE_ROOT",
    "contracts",
]
