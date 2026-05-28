"""Fast JSON helpers backed by orjson when available."""

from __future__ import annotations

import json as _json
from collections.abc import Callable
from typing import Any

try:  # pragma: no cover - exercised when the dependency is installed.
    import orjson as _orjson
except ImportError:  # pragma: no cover - keeps source checkouts usable before install.
    _orjson = None  # type: ignore[assignment]

DefaultFn = Callable[[Any], Any]
USING_ORJSON = _orjson is not None


def dumps_json(
    value: Any,
    *,
    sort_keys: bool = False,
    indent: int | None = None,
    append_newline: bool = False,
    default: DefaultFn | None = str,
) -> str:
    """Serialize ``value`` to UTF-8 JSON text.

    ``orjson`` is used on installed environments; stdlib JSON remains as a safe
    fallback for editable checkouts that have not installed dependencies yet.
    """
    if _orjson is not None:
        option = 0
        if sort_keys:
            option |= _orjson.OPT_SORT_KEYS
        if indent is not None:
            option |= _orjson.OPT_INDENT_2
        if append_newline:
            option |= _orjson.OPT_APPEND_NEWLINE
        return _orjson.dumps(value, option=option, default=default).decode("utf-8")

    text = _json.dumps(
        value,
        sort_keys=sort_keys,
        indent=indent,
        default=default,
        ensure_ascii=False,
    )
    return f"{text}\n" if append_newline and not text.endswith("\n") else text


def dumps_json_bytes(
    value: Any,
    *,
    sort_keys: bool = False,
    default: DefaultFn | None = str,
) -> bytes:
    """Serialize ``value`` directly to UTF-8 JSON bytes."""
    if _orjson is not None:
        option = _orjson.OPT_SORT_KEYS if sort_keys else 0
        return _orjson.dumps(value, option=option, default=default)
    return dumps_json(value, sort_keys=sort_keys, default=default).encode("utf-8")


def loads_json(value: str | bytes | bytearray) -> Any:
    """Deserialize JSON from text or bytes."""
    if _orjson is not None:
        return _orjson.loads(value)
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8")
    return _json.loads(value)
