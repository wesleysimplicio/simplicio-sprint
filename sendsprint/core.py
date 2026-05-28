"""Optional Rust-backed kernels (sendsprint-core) with Python fallback.

The Rust extension is opt-in. It is loaded when both:

1. The ``sendsprint_core`` wheel is importable (built from ``crates/sendsprint-core``).
2. The ``SENDSPRINT_USE_RUST_CORE`` env var is not set to a falsy value
   (``0``/``false``/``no``/``off``).

If either is false, the pure-Python fallback runs and produces the same report
shape. Callers therefore never need to branch on availability — they call
:func:`validate_sprint_plan` and get a dict back.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from typing import Any

try:  # pragma: no cover - presence depends on wheel install
    import sendsprint_core as _rust_core
except ImportError:  # pragma: no cover - Python-only environments
    _rust_core = None

RUST_AVAILABLE = _rust_core is not None

_VALID_STATUSES = {
    "todo", "to do", "open", "ready", "backlog",
    "doing", "in progress", "in review", "review", "active", "started",
    "done", "closed", "resolved", "completed",
    "blocked", "on hold",
    "em andamento", "em revisão", "em revisao", "fechado", "concluído", "concluida",
    "en progreso", "cerrado", "terminado",
}


def _env_flag(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off"}


def use_rust() -> bool:
    """Return whether the Rust validator will be used for the next call."""
    return RUST_AVAILABLE and _env_flag("SENDSPRINT_USE_RUST_CORE", True)


def backend() -> str:
    """Return the backend name (``"rust"`` or ``"python"``) for diagnostics."""
    return "rust" if use_rust() else "python"


def validate_sprint_plan(sprint: Any) -> dict[str, Any]:
    """Validate a sprint and return a structured report.

    ``sprint`` may be:

    - a :class:`sendsprint.models.sprint.Sprint` (we call ``.model_dump()``),
    - a ``dict`` with the same shape,
    - JSON ``bytes``, or
    - a JSON ``str``.

    The return shape is::

        {
          "sprint_id": str,
          "sprint_name": str,
          "item_count": int,
          "ok": bool,
          "error_count": int,
          "warning_count": int,
          "info_count": int,
          "findings": [
            {"severity": str, "code": str,
             "item_key": str | None, "message": str},
            ...
          ],
          "backend": "rust" | "python",
        }
    """
    payload_bytes, payload_dict = _normalize(sprint)

    if use_rust():
        report = _rust_core.validate_sprint_plan_bytes(payload_bytes)
        report["backend"] = "rust"
        return report

    report = _python_validate(payload_dict)
    report["backend"] = "python"
    return report


def _normalize(sprint: Any) -> tuple[bytes, dict[str, Any]]:
    if isinstance(sprint, bytes):
        return sprint, json.loads(sprint.decode("utf-8"))
    if isinstance(sprint, str):
        data = json.loads(sprint)
        return sprint.encode("utf-8"), data
    if hasattr(sprint, "model_dump"):
        data = sprint.model_dump(mode="json")
    elif isinstance(sprint, dict):
        data = sprint
    else:
        raise TypeError(
            f"unsupported sprint payload: {type(sprint).__name__}"
        )
    return json.dumps(data, default=str).encode("utf-8"), data


def _python_validate(sprint: dict[str, Any]) -> dict[str, Any]:
    items: list[dict[str, Any]] = list(sprint.get("items") or [])
    findings: list[dict[str, Any]] = []

    by_key: dict[str, dict[str, Any]] = {}
    duplicates: set[str] = set()
    for item in items:
        key = item.get("key") or ""
        if not key:
            findings.append(
                _finding(
                    "error",
                    "missing_key",
                    None,
                    f"item with id={item.get('id')!r} has empty key",
                )
            )
            continue
        if key in by_key:
            duplicates.add(key)
        else:
            by_key[key] = item

    for key in duplicates:
        findings.append(_finding("error", "duplicate_key", key, f"duplicate item key: {key}"))

    for item in items:
        key = item.get("key") or ""
        if not key:
            continue

        parent = item.get("parent_key")
        if parent:
            if parent == key:
                findings.append(
                    _finding("error", "self_parent", key, f"item {key} is its own parent")
                )
            elif parent not in by_key:
                findings.append(
                    _finding(
                        "warning",
                        "orphan_parent",
                        key,
                        f"parent_key {parent} not present in sprint",
                    )
                )

        points = item.get("story_points")
        if points is not None:
            try:
                value = float(points)
            except (TypeError, ValueError):
                findings.append(
                    _finding(
                        "error",
                        "invalid_story_points",
                        key,
                        f"story_points {points!r} must be a non-negative number",
                    )
                )
            else:
                if value < 0 or value != value or value in (float("inf"), float("-inf")):
                    findings.append(
                        _finding(
                            "error",
                            "invalid_story_points",
                            key,
                            f"story_points {value} must be a non-negative number",
                        )
                    )

        status = (item.get("status") or "").strip()
        if status and status.lower() not in _VALID_STATUSES:
            findings.append(
                _finding("warning", "unknown_status", key, f"unrecognized status: {status}")
            )

        for link in item.get("links") or []:
            target = link.get("target_key") or ""
            link_type = link.get("type") or ""
            if not target:
                findings.append(
                    _finding(
                        "warning",
                        "empty_link_target",
                        key,
                        f"link type={link_type} has empty target_key",
                    )
                )
            elif target not in by_key and target != key:
                findings.append(
                    _finding(
                        "info",
                        "external_link",
                        key,
                        f"link target {target} not in this sprint",
                    )
                )

        if item.get("type") == "Story":
            ac = item.get("acceptance_criteria")
            if ac is None or not str(ac).strip():
                findings.append(
                    _finding(
                        "warning",
                        "missing_acceptance_criteria",
                        key,
                        f"Story {key} has no acceptance_criteria",
                    )
                )

        labels = item.get("labels") or []
        seen: set[str] = set()
        for label in labels:
            if label in seen:
                findings.append(
                    _finding(
                        "info",
                        "duplicate_label",
                        key,
                        f"duplicate label on {key}: {label}",
                    )
                )
            else:
                seen.add(label)

    _detect_cycles(items, by_key, findings)

    errors = sum(1 for f in findings if f["severity"] == "error")
    warnings = sum(1 for f in findings if f["severity"] == "warning")
    infos = sum(1 for f in findings if f["severity"] == "info")

    return {
        "sprint_id": sprint.get("id") or "",
        "sprint_name": sprint.get("name") or "",
        "item_count": len(items),
        "ok": errors == 0,
        "error_count": errors,
        "warning_count": warnings,
        "info_count": infos,
        "findings": findings,
    }


def _finding(
    severity: str, code: str, item_key: str | None, message: str
) -> dict[str, Any]:
    return {
        "severity": severity,
        "code": code,
        "item_key": item_key,
        "message": message,
    }


def _detect_cycles(
    items: Iterable[dict[str, Any]],
    by_key: dict[str, dict[str, Any]],
    findings: list[dict[str, Any]],
) -> None:
    UNVISITED, VISITING, DONE = 0, 1, 2
    state: dict[str, int] = {item["key"]: UNVISITED for item in items if item.get("key")}
    reported: set[str] = set()

    for start in items:
        key = start.get("key") or ""
        if not key or state.get(key) != UNVISITED:
            continue
        path: list[str] = []
        cursor: str | None = key
        while True:
            if cursor is None:
                for k in path:
                    state[k] = DONE
                break
            mark = state.get(cursor, DONE)
            if mark == DONE:
                for k in path:
                    state[k] = DONE
                break
            if mark == VISITING:
                idx = path.index(cursor)
                cycle = path[idx:] + [cursor]
                signature = "->".join(cycle)
                if signature not in reported:
                    reported.add(signature)
                    findings.append(
                        _finding(
                            "error",
                            "parent_cycle",
                            cursor,
                            f"parent_key cycle detected: {signature}",
                        )
                    )
                for k in path:
                    state[k] = DONE
                break
            state[cursor] = VISITING
            path.append(cursor)
            parent = by_key.get(cursor, {}).get("parent_key")
            cursor = parent if parent and parent != cursor else None


__all__ = [
    "RUST_AVAILABLE",
    "backend",
    "use_rust",
    "validate_sprint_plan",
]
