"""Tests for the central logging setup."""

from __future__ import annotations

import json
import logging

from sendsprint.logging_setup import PKG_LOGGER, configure


def _flush() -> None:
    for handler in logging.getLogger(PKG_LOGGER).handlers:
        handler.flush()


def test_configure_writes_file_and_captures(tmp_path, monkeypatch):
    monkeypatch.setenv("SENDSPRINT_LOG_DIR", str(tmp_path))
    path = configure(level="DEBUG")
    assert path == tmp_path / "sendsprint.log"
    logging.getLogger("sendsprint.test").info("hello-step")
    _flush()
    assert "hello-step" in path.read_text()


def test_json_lines(tmp_path):
    path = tmp_path / "log.jsonl"
    configure(level="INFO", log_file=path, json_lines=True, console=False)
    logging.getLogger("sendsprint.x").warning("boom")
    _flush()
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    record = json.loads(lines[-1])
    assert record["level"] == "WARNING"
    assert record["msg"] == "boom"
    assert record["logger"] == "sendsprint.x"


def test_idempotent_no_duplicate_handlers(tmp_path):
    path = tmp_path / "a.log"
    configure(log_file=path, console=False)
    configure(log_file=path, console=False)
    assert len(logging.getLogger(PKG_LOGGER).handlers) == 1
