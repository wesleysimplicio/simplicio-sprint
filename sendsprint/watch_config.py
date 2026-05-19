"""Configuration helpers for the opt-in polling watcher."""

from __future__ import annotations

from sendsprint.models.workspace import WatchConfig


def parse_interval_minutes(value: str | int | None, default: int = 15) -> int:
    """Parse CLI interval values such as ``15``, ``15m`` or ``1h`` into minutes."""
    if value is None:
        return default
    if isinstance(value, int):
        if value < 1:
            raise ValueError("interval must be at least 1 minute")
        return value
    raw = value.strip().lower()
    if not raw:
        return default
    multiplier = 1
    if raw.endswith("m"):
        raw = raw[:-1]
    elif raw.endswith("h"):
        raw = raw[:-1]
        multiplier = 60
    minutes = int(raw) * multiplier
    if minutes < 1:
        raise ValueError("interval must be at least 1 minute")
    return minutes


__all__ = ["WatchConfig", "parse_interval_minutes"]
