"""Pure-Python implementations of accelerator hot paths.

These are the **always-available** fallbacks.  Every function here has an
identical contract to its Rust counterpart so that callers never need to
know which backend is active.

Issue: #108
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# ---------------------------------------------------------------------------
# Diff-file regex (same as diff_verifier but isolated to avoid circular dep)
# ---------------------------------------------------------------------------

_DIFF_FILE_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)


# ---------------------------------------------------------------------------
# fast_scan — extract changed file paths from a unified diff
# ---------------------------------------------------------------------------


def fast_scan(diff_text: str) -> list[str]:
    """Return deduplicated list of file paths touched by *diff_text*."""
    seen: set[str] = set()
    result: list[str] = []
    for match in _DIFF_FILE_RE.finditer(diff_text):
        path = match.group(2)
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


# ---------------------------------------------------------------------------
# fast_diff — count added lines per file from a unified diff
# ---------------------------------------------------------------------------


def fast_diff(diff_text: str) -> dict[str, int]:
    """Return ``{filepath: added_line_count}`` from a unified diff."""
    counts: dict[str, int] = {}
    current_file: str | None = None
    for line in diff_text.splitlines():
        file_match = _DIFF_FILE_RE.match(line)
        if file_match:
            current_file = file_match.group(2)
            counts.setdefault(current_file, 0)
            continue
        if current_file is not None and line.startswith("+") and not line.startswith("+++"):
            counts[current_file] = counts.get(current_file, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# fast_dedupe — deduplicate items by content hash
# ---------------------------------------------------------------------------


def fast_dedupe(items: list[str]) -> list[str]:
    """Return *items* with duplicates removed, preserving first-seen order."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ---------------------------------------------------------------------------
# fast_receipt_hash — canonical SHA-256 of a JSON-serialisable payload
# ---------------------------------------------------------------------------


def fast_receipt_hash(payload: Any) -> str:
    """Stable ``sha256:<hex>`` hash of any JSON-serialisable *payload*.

    Identical to :func:`sendsprint.yool.receipts.sha256_canonical` but kept
    here to avoid import coupling.
    """
    text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
