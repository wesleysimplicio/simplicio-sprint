"""Bridge to the optional Rust accelerator CLI binary.

When ``sendsprint-accel`` is found on ``$PATH`` the :class:`RustBridge`
delegates hot-path calls to it via ``subprocess.run``.  If the binary is
missing or a call fails, the bridge transparently falls back to the pure-
Python implementations in :mod:`sendsprint.accelerators.python_impl`.

Issue: #108
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from typing import Any

from sendsprint.accelerators import python_impl

logger = logging.getLogger(__name__)

RUST_BINARY = "sendsprint-accel"


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def detect_rust_accelerator() -> str | None:
    """Return the absolute path to the Rust binary, or ``None``."""
    return shutil.which(RUST_BINARY)


# ---------------------------------------------------------------------------
# RustBridge
# ---------------------------------------------------------------------------


class RustBridge:
    """Wraps subprocess calls to the Rust binary with Python fallback.

    Parameters
    ----------
    binary_path:
        Absolute path to ``sendsprint-accel``.  When *None*, every call
        falls back to :mod:`python_impl`.
    timeout:
        Maximum seconds to wait for a single subprocess invocation.
    """

    def __init__(
        self,
        binary_path: str | None = None,
        *,
        timeout: float = 30.0,
    ) -> None:
        self.binary_path = binary_path
        self.timeout = timeout
        self._available = binary_path is not None

    @property
    def is_rust(self) -> bool:
        """True when the Rust binary is wired up."""
        return self._available

    @property
    def backend_name(self) -> str:
        return "rust" if self._available else "python"

    # -- helpers -----------------------------------------------------------

    def _run(self, subcommand: str, stdin_text: str) -> str | None:
        """Run ``sendsprint-accel <subcommand>`` with *stdin_text* piped in.

        Returns stdout on success, ``None`` on any failure (logged).
        """
        if not self._available or self.binary_path is None:
            return None
        try:
            result = subprocess.run(
                [self.binary_path, subcommand],
                input=stdin_text,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            if result.returncode == 0:
                return result.stdout
            logger.warning(
                "rust accelerator %s failed (rc=%d): %s",
                subcommand,
                result.returncode,
                result.stderr[:200],
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.warning("rust accelerator %s error: %s", subcommand, exc)
        return None

    # -- public API (same contract as python_impl) -------------------------

    def fast_scan(self, diff_text: str) -> list[str]:
        out = self._run("scan", diff_text)
        if out is not None:
            try:
                parsed = json.loads(out)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return python_impl.fast_scan(diff_text)

    def fast_diff(self, diff_text: str) -> dict[str, int]:
        out = self._run("diff", diff_text)
        if out is not None:
            try:
                parsed = json.loads(out)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
        return python_impl.fast_diff(diff_text)

    def fast_dedupe(self, items: list[str]) -> list[str]:
        out = self._run("dedupe", json.dumps(items))
        if out is not None:
            try:
                parsed = json.loads(out)
                if isinstance(parsed, list):
                    return parsed
            except json.JSONDecodeError:
                pass
        return python_impl.fast_dedupe(items)

    def fast_receipt_hash(self, payload: Any) -> str:
        stdin_text = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        out = self._run("receipt-hash", stdin_text)
        if out is not None:
            stripped = out.strip()
            if stripped.startswith("sha256:"):
                return stripped
        return python_impl.fast_receipt_hash(payload)
