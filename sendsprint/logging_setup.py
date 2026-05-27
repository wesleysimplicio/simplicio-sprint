"""Central logging — capture every step of a run to console + a file.

All SendSprint modules log under the ``sendsprint`` logger tree
(``logging.getLogger(__name__)``), so configuring that one parent here captures
everything: operator transport, simplicio invocations, each delivery step, the
fan-out, tool updates and errors. The file handler records at DEBUG (full
detail); the console mirrors at the chosen level. ``--log-json`` emits JSON lines
for ingestion.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

PKG_LOGGER = "sendsprint"
_FILE_FORMAT = "%(asctime)s %(levelname)-7s %(name)s | %(message)s"


def log_dir() -> Path:
    """Where run logs live (override: ``SENDSPRINT_LOG_DIR``)."""
    return Path(os.environ.get("SENDSPRINT_LOG_DIR", "~/.local/state/sendsprint/logs")).expanduser()


class JsonLineFormatter(logging.Formatter):
    """One JSON object per log record, with any step/item/status extras."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in ("step", "item", "status", "repo"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def _coerce_level(level: int | str) -> int:
    if isinstance(level, int):
        return level
    return getattr(logging, str(level).upper(), logging.INFO)


def configure(
    *,
    level: int | str = logging.INFO,
    log_file: str | Path | None = None,
    json_lines: bool = False,
    console: bool = True,
) -> Path:
    """Configure the ``sendsprint`` logger. Idempotent; returns the log file path."""
    resolved_level = _coerce_level(level)
    logger = logging.getLogger(PKG_LOGGER)
    logger.setLevel(logging.DEBUG)  # handlers gate their own level
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()

    path = Path(log_file) if log_file else log_dir() / "sendsprint.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(path, maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        JsonLineFormatter() if json_lines else logging.Formatter(_FILE_FORMAT)
    )
    logger.addHandler(file_handler)

    if console:
        stream = logging.StreamHandler(sys.stderr)
        stream.setLevel(resolved_level)
        stream.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(stream)

    logger.debug("logging configured (level=%s) -> %s", logging.getLevelName(resolved_level), path)
    return path
