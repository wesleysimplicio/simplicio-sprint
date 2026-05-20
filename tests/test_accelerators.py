"""Tests for sendsprint.accelerators (#108).

Covers pure-Python hot paths, RustBridge fallback behavior, resolver,
and parity with existing receipt hashing in sendsprint.yool.receipts.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from sendsprint.accelerators import python_impl, resolve_accelerator
from sendsprint.accelerators.resolver import BenchmarkResult, benchmark
from sendsprint.accelerators.rust_bridge import (
    RustBridge,
    detect_rust_accelerator,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_DIFF = """\
diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,5 @@
 import os
+import sys
+import json
 def main():
     pass
diff --git a/tests/test_main.py b/tests/test_main.py
--- a/tests/test_main.py
+++ b/tests/test_main.py
@@ -1,2 +1,4 @@
 def test_main():
+    assert True
+    assert 1 == 1
     pass
diff --git a/src/main.py b/src/utils.py
--- /dev/null
+++ b/src/utils.py
@@ -0,0 +1,3 @@
+def bar():
+    return 42
+
"""

SAMPLE_ITEMS = ["alpha", "beta", "gamma", "alpha", "delta", "beta", "epsilon"]
SAMPLE_PAYLOAD = {"action": "test", "count": 7, "nested": {"ok": True}}


# ===================================================================
# python_impl tests
# ===================================================================


class TestFastScan:
    def test_basic(self):
        result = python_impl.fast_scan(SAMPLE_DIFF)
        assert result == ["src/main.py", "tests/test_main.py", "src/utils.py"]

    def test_dedup(self):
        # src/main.py appears in two diff headers — should appear once
        result = python_impl.fast_scan(SAMPLE_DIFF)
        assert result.count("src/main.py") == 1

    def test_empty(self):
        assert python_impl.fast_scan("") == []

    def test_no_diff_markers(self):
        assert python_impl.fast_scan("just some random text\nno diffs here") == []


class TestFastDiff:
    def test_basic(self):
        result = python_impl.fast_diff(SAMPLE_DIFF)
        assert result["src/main.py"] == 2  # +import sys, +import json
        assert result["tests/test_main.py"] == 2  # +assert True, +assert 1==1
        assert result["src/utils.py"] == 3  # 3 new lines

    def test_empty(self):
        assert python_impl.fast_diff("") == {}

    def test_no_additions(self):
        diff = "diff --git a/foo.py b/foo.py\n-removed line\n"
        result = python_impl.fast_diff(diff)
        assert result.get("foo.py", 0) == 0


class TestFastDedupe:
    def test_basic(self):
        result = python_impl.fast_dedupe(SAMPLE_ITEMS)
        assert result == ["alpha", "beta", "gamma", "delta", "epsilon"]

    def test_preserves_order(self):
        result = python_impl.fast_dedupe(["c", "b", "a", "b", "c"])
        assert result == ["c", "b", "a"]

    def test_empty(self):
        assert python_impl.fast_dedupe([]) == []

    def test_all_unique(self):
        items = ["x", "y", "z"]
        assert python_impl.fast_dedupe(items) == items

    def test_all_same(self):
        assert python_impl.fast_dedupe(["a", "a", "a"]) == ["a"]


class TestFastReceiptHash:
    def test_deterministic(self):
        h1 = python_impl.fast_receipt_hash(SAMPLE_PAYLOAD)
        h2 = python_impl.fast_receipt_hash(SAMPLE_PAYLOAD)
        assert h1 == h2

    def test_prefix(self):
        h = python_impl.fast_receipt_hash({"k": 1})
        assert h.startswith("sha256:")

    def test_hex_length(self):
        h = python_impl.fast_receipt_hash({"k": 1})
        hex_part = h.split(":", 1)[1]
        assert len(hex_part) == 64

    def test_key_order_irrelevant(self):
        h1 = python_impl.fast_receipt_hash({"a": 1, "b": 2})
        h2 = python_impl.fast_receipt_hash({"b": 2, "a": 1})
        assert h1 == h2

    def test_different_payload_different_hash(self):
        h1 = python_impl.fast_receipt_hash({"x": 1})
        h2 = python_impl.fast_receipt_hash({"x": 2})
        assert h1 != h2

    def test_parity_with_yool_receipts(self):
        """Ensure identical output to sendsprint.yool.receipts.sha256_canonical."""
        from sendsprint.yool.receipts import sha256_canonical

        for payload in [
            SAMPLE_PAYLOAD,
            {"a": 1},
            [1, 2, 3],
            "hello",
            42,
            None,
        ]:
            assert python_impl.fast_receipt_hash(payload) == sha256_canonical(payload)


# ===================================================================
# RustBridge tests (no real binary — pure fallback)
# ===================================================================


class TestRustBridgeFallback:
    """RustBridge(None) must behave identically to python_impl."""

    def setup_method(self):
        self.bridge = RustBridge(None)

    def test_backend_name(self):
        assert self.bridge.backend_name == "python"

    def test_is_rust_false(self):
        assert self.bridge.is_rust is False

    def test_fast_scan(self):
        assert self.bridge.fast_scan(SAMPLE_DIFF) == python_impl.fast_scan(SAMPLE_DIFF)

    def test_fast_diff(self):
        assert self.bridge.fast_diff(SAMPLE_DIFF) == python_impl.fast_diff(SAMPLE_DIFF)

    def test_fast_dedupe(self):
        assert self.bridge.fast_dedupe(SAMPLE_ITEMS) == python_impl.fast_dedupe(SAMPLE_ITEMS)

    def test_fast_receipt_hash(self):
        assert self.bridge.fast_receipt_hash(SAMPLE_PAYLOAD) == python_impl.fast_receipt_hash(
            SAMPLE_PAYLOAD
        )


class TestRustBridgeWithMockedBinary:
    """Simulate a working Rust binary via mocked subprocess."""

    def test_fast_scan_uses_rust_output(self):
        bridge = RustBridge("/fake/sendsprint-accel")
        with patch("sendsprint.accelerators.rust_bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='["a.py","b.py"]', stderr="")
            result = bridge.fast_scan("ignored")
            assert result == ["a.py", "b.py"]
            mock_run.assert_called_once()

    def test_fast_scan_falls_back_on_bad_json(self):
        bridge = RustBridge("/fake/sendsprint-accel")
        with patch("sendsprint.accelerators.rust_bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="not json", stderr="")
            result = bridge.fast_scan(SAMPLE_DIFF)
            assert result == python_impl.fast_scan(SAMPLE_DIFF)

    def test_fast_scan_falls_back_on_nonzero_rc(self):
        bridge = RustBridge("/fake/sendsprint-accel")
        with patch("sendsprint.accelerators.rust_bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="boom")
            result = bridge.fast_scan(SAMPLE_DIFF)
            assert result == python_impl.fast_scan(SAMPLE_DIFF)

    def test_fast_scan_falls_back_on_timeout(self):
        import subprocess as sp

        bridge = RustBridge("/fake/sendsprint-accel")
        with patch("sendsprint.accelerators.rust_bridge.subprocess.run") as mock_run:
            mock_run.side_effect = sp.TimeoutExpired(cmd="x", timeout=30)
            result = bridge.fast_scan(SAMPLE_DIFF)
            assert result == python_impl.fast_scan(SAMPLE_DIFF)

    def test_fast_receipt_hash_uses_rust_output(self):
        bridge = RustBridge("/fake/sendsprint-accel")
        fake_hash = "sha256:abc123"
        with patch("sendsprint.accelerators.rust_bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=f"{fake_hash}\n", stderr="")
            result = bridge.fast_receipt_hash({"x": 1})
            assert result == fake_hash

    def test_fast_diff_uses_rust_output(self):
        bridge = RustBridge("/fake/sendsprint-accel")
        with patch("sendsprint.accelerators.rust_bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='{"foo.py":5}', stderr="")
            result = bridge.fast_diff("ignored")
            assert result == {"foo.py": 5}

    def test_fast_dedupe_uses_rust_output(self):
        bridge = RustBridge("/fake/sendsprint-accel")
        with patch("sendsprint.accelerators.rust_bridge.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout='["a","b"]', stderr="")
            result = bridge.fast_dedupe(["a", "b", "a"])
            assert result == ["a", "b"]


# ===================================================================
# detect_rust_accelerator
# ===================================================================


class TestDetectRustAccelerator:
    def test_returns_none_when_missing(self):
        with patch("sendsprint.accelerators.rust_bridge.shutil.which", return_value=None):
            assert detect_rust_accelerator() is None

    def test_returns_path_when_found(self):
        with patch(
            "sendsprint.accelerators.rust_bridge.shutil.which",
            return_value="/usr/local/bin/sendsprint-accel",
        ):
            assert detect_rust_accelerator() == "/usr/local/bin/sendsprint-accel"


# ===================================================================
# resolver
# ===================================================================


class TestResolveAccelerator:
    def test_returns_rust_bridge(self):
        accel = resolve_accelerator()
        assert isinstance(accel, RustBridge)

    def test_fallback_when_no_binary(self):
        with patch(
            "sendsprint.accelerators.resolver.detect_rust_accelerator",
            return_value=None,
        ):
            accel = resolve_accelerator()
            assert accel.backend_name == "python"
            assert accel.is_rust is False


# ===================================================================
# BenchmarkResult
# ===================================================================


class TestBenchmarkResult:
    def test_speedup(self):
        r = BenchmarkResult("test", python_ms=100.0, rust_ms=10.0)
        assert r.speedup == pytest.approx(10.0)

    def test_speedup_zero_rust(self):
        r = BenchmarkResult("test", python_ms=100.0, rust_ms=0.0)
        assert r.speedup == 0.0

    def test_repr(self):
        r = BenchmarkResult("scan", python_ms=50.0, rust_ms=25.0)
        assert "scan" in repr(r)
        assert "2.0x" in repr(r)


class TestBenchmark:
    def test_returns_four_results(self):
        results = benchmark(SAMPLE_DIFF, iterations=2)
        assert len(results) == 4
        names = [r.name for r in results]
        assert "fast_scan" in names
        assert "fast_diff" in names
        assert "fast_dedupe" in names
        assert "fast_receipt_hash" in names

    def test_all_positive_times(self):
        results = benchmark(SAMPLE_DIFF, iterations=5)
        for r in results:
            assert r.python_ms > 0
            assert r.rust_ms > 0
