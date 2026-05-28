"""Benchmark sendsprint.core.validate_sprint_plan: Rust vs Python.

Run::

    python bench/validate_sprint_plan.py

Generates synthetic sprints at N = 10, 100, 1_000, 10_000 items and prints
median wall-clock per call for both backends. The Rust backend is only run if
``sendsprint_core`` is importable.
"""

from __future__ import annotations

import json
import os
import statistics
import time
from typing import Any

from sendsprint import core


def build_sprint(n: int, *, with_issues: bool = True) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    for i in range(n):
        item: dict[str, Any] = {
            "id": str(i),
            "key": f"K-{i}",
            "type": "Story" if i % 5 == 0 else "Task",
            "title": f"Item {i}",
            "status": "todo",
            "labels": ["alpha", "beta"] if i % 3 == 0 else ["alpha"],
            "links": [],
            "comments": [],
            "attachments": [],
        }
        if i > 0 and i % 7 != 0:
            item["parent_key"] = f"K-{i - 1}"
        if item["type"] == "Story":
            item["acceptance_criteria"] = "- do the thing"
        if with_issues and i % 47 == 0:
            item["status"] = "alien"
        if with_issues and i % 53 == 0 and i > 0:
            item["parent_key"] = "GHOST"
        if with_issues and i % 97 == 0 and i > 0:
            item["labels"] = ["dup", "dup"]
        items.append(item)
    return {"id": "S-bench", "name": "Bench Sprint", "items": items}


def run(sprint: dict[str, Any], backend: str, iters: int) -> list[float]:
    os.environ["SENDSPRINT_USE_RUST_CORE"] = "1" if backend == "rust" else "0"
    samples: list[float] = []
    payload_bytes = json.dumps(sprint).encode("utf-8")
    # warm up
    for _ in range(3):
        core.validate_sprint_plan(payload_bytes)
    for _ in range(iters):
        t0 = time.perf_counter()
        report = core.validate_sprint_plan(payload_bytes)
        elapsed = time.perf_counter() - t0
        samples.append(elapsed)
        assert report["backend"] == backend
    return samples


def fmt(samples: list[float]) -> str:
    median = statistics.median(samples) * 1_000_000  # µs
    p95 = sorted(samples)[max(0, int(len(samples) * 0.95) - 1)] * 1_000_000
    return f"median={median:>10.1f} µs  p95={p95:>10.1f} µs"


def main() -> int:
    sizes = (10, 100, 1_000, 10_000)
    print(
        f"sendsprint-core benchmark — RUST_AVAILABLE={core.RUST_AVAILABLE}\n"
        f"python: {os.popen('python --version').read().strip()}\n"
    )
    print(f"{'N':>8} {'backend':>8} {'metric':>40}  ratio (python/rust)")
    print("-" * 80)
    for n in sizes:
        sprint = build_sprint(n)
        iters = max(20, 200 // max(1, n // 100))
        py = run(sprint, "python", iters)
        py_med = statistics.median(py)
        print(f"{n:>8} {'python':>8}  {fmt(py)}")
        if core.RUST_AVAILABLE:
            rs = run(sprint, "rust", iters)
            rs_med = statistics.median(rs)
            ratio = py_med / rs_med if rs_med > 0 else float("inf")
            print(f"{n:>8} {'rust':>8}  {fmt(rs)}   {ratio:>5.1f}x")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
