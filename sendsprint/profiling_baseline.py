"""Runtime profiling baseline for cross-stack acceleration decisions.

Profiles the current Python runtime paths (scan, dedupe, event persistence,
scheduling, validation, evidence writes) and records results as evidence
artifacts.  The measured baselines tell us *where* Go/Rust acceleration is
justified instead of guessing.

Issue: #119 (part of #105, #107, #108)
"""

from __future__ import annotations

import json
import statistics
import time
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Result model
# ---------------------------------------------------------------------------


class ProfileResult(BaseModel):
    """Timing result for a single profiled operation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    operation: str
    duration_ms: float
    iterations: int
    throughput: float = Field(default=0.0, description="ops/sec (iterations / duration_s)")
    memory_delta_mb: float = Field(
        default=0.0, description="Peak RSS delta in MiB during profiling"
    )
    p50_ms: float = 0.0
    p99_ms: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Go/Rust justification thresholds
# ---------------------------------------------------------------------------


class GoRustThresholds(BaseModel):
    """When a Python path exceeds these thresholds, Go/Rust acceleration is
    justified.  Values are per-call median (p50) in milliseconds.

    Conservative defaults based on typical CI and dev-machine latencies.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    scan_ms: float = 100.0
    dedupe_ms: float = 50.0
    event_persist_ms: float = 200.0
    scheduling_ms: float = 150.0
    validation_ms: float = 300.0
    evidence_write_ms: float = 250.0

    def evaluate(self, results: list[ProfileResult]) -> list[dict[str, Any]]:
        """Compare *results* against thresholds.

        Returns a list of dicts: ``{operation, p50_ms, threshold_ms,
        exceeds, recommendation}``.
        """
        mapping = {
            "scan": self.scan_ms,
            "dedupe": self.dedupe_ms,
            "event_persist": self.event_persist_ms,
            "scheduling": self.scheduling_ms,
            "validation": self.validation_ms,
            "evidence_write": self.evidence_write_ms,
        }
        evaluations: list[dict[str, Any]] = []
        for r in results:
            threshold = mapping.get(r.operation)
            if threshold is None:
                continue
            exceeds = r.p50_ms > threshold
            evaluations.append(
                {
                    "operation": r.operation,
                    "p50_ms": round(r.p50_ms, 3),
                    "threshold_ms": threshold,
                    "exceeds": exceeds,
                    "recommendation": (
                        f"Go/Rust acceleration justified for {r.operation}"
                        if exceeds
                        else f"Python adequate for {r.operation}"
                    ),
                }
            )
        return evaluations


# ---------------------------------------------------------------------------
# Profiling helpers
# ---------------------------------------------------------------------------


def _time_iterations(fn: Any, iterations: int) -> tuple[float, list[float], float]:
    """Run *fn* for *iterations*, return (total_ms, per_call_ms_list, memory_delta_mb)."""
    tracemalloc.start()
    snap_before = tracemalloc.take_snapshot()

    per_call: list[float] = []
    t0_total = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        fn()
        per_call.append((time.perf_counter() - t0) * 1000)
    total_ms = (time.perf_counter() - t0_total) * 1000

    snap_after = tracemalloc.take_snapshot()
    tracemalloc.stop()

    # Compute memory delta from top stats.
    stats = snap_after.compare_to(snap_before, "lineno")
    delta_bytes = sum(s.size_diff for s in stats if s.size_diff > 0)
    memory_delta_mb = delta_bytes / (1024 * 1024)

    return total_ms, per_call, memory_delta_mb


def _build_result(
    operation: str,
    iterations: int,
    total_ms: float,
    per_call: list[float],
    memory_delta_mb: float,
) -> ProfileResult:
    duration_s = total_ms / 1000
    throughput = iterations / duration_s if duration_s > 0 else 0.0
    p50 = statistics.median(per_call) if per_call else 0.0
    p99 = (
        per_call[int(len(per_call) * 0.99)]
        if len(per_call) >= 2
        else (per_call[0] if per_call else 0.0)
    )
    return ProfileResult(
        operation=operation,
        duration_ms=round(total_ms, 3),
        iterations=iterations,
        throughput=round(throughput, 2),
        memory_delta_mb=round(memory_delta_mb, 4),
        p50_ms=round(p50, 3),
        p99_ms=round(p99, 3),
    )


# ---------------------------------------------------------------------------
# ProfilingBaseline
# ---------------------------------------------------------------------------


_SAMPLE_DIFF = """\
diff --git a/src/main.py b/src/main.py
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,5 @@
+import os
+import sys
 def main():
     pass
diff --git a/tests/test_main.py b/tests/test_main.py
--- a/tests/test_main.py
+++ b/tests/test_main.py
@@ -1,2 +1,4 @@
+def test_main():
+    assert True
"""

_SAMPLE_ITEMS = ["alpha", "bravo", "charlie", "alpha", "delta", "bravo", "echo"] * 50
_SAMPLE_PAYLOAD = {"task": "PROJ-42", "status": "done", "points": 5, "tags": ["api", "fix"]}


class ProfilingBaseline:
    """Profile the six core Python runtime paths.

    Each ``profile_*`` method returns a :class:`ProfileResult`.
    ``run_all()`` runs every profiler and returns a full list.
    """

    def __init__(self, *, iterations: int = 200, tmp_dir: Path | None = None) -> None:
        self.iterations = iterations
        self._tmp_dir = tmp_dir or Path(__file__).parent.parent / ".sendsprint" / "profiling_tmp"

    # -- individual profilers -----------------------------------------------

    def profile_scan(self) -> ProfileResult:
        """Profile ``fast_scan`` — extract file paths from a diff."""
        from sendsprint.accelerators.python_impl import fast_scan

        total, per_call, mem = _time_iterations(lambda: fast_scan(_SAMPLE_DIFF), self.iterations)
        return _build_result("scan", self.iterations, total, per_call, mem)

    def profile_dedupe(self) -> ProfileResult:
        """Profile ``fast_dedupe`` — deduplicate items."""
        from sendsprint.accelerators.python_impl import fast_dedupe

        total, per_call, mem = _time_iterations(lambda: fast_dedupe(_SAMPLE_ITEMS), self.iterations)
        return _build_result("dedupe", self.iterations, total, per_call, mem)

    def profile_events(self) -> ProfileResult:
        """Profile NDJSON event persistence (write + replay cycle)."""
        import shutil
        import uuid

        from sendsprint.contracts import EventType, RunEvent
        from sendsprint.event_store import EventStore

        run_id = f"profile-{uuid.uuid4().hex[:8]}"
        self._tmp_dir.mkdir(parents=True, exist_ok=True)

        def _persist_cycle() -> None:
            store = EventStore(root=self._tmp_dir, run_id=run_id)
            ev = RunEvent(
                event_type=EventType.progress,
                run_id=run_id,
                data={"step": 1, "status": "ok"},
            )
            store.append(ev)
            store.replay(from_seq=0)

        try:
            total, per_call, mem = _time_iterations(_persist_cycle, self.iterations)
        finally:
            run_dir = self._tmp_dir / ".sendsprint" / "runs"
            if run_dir.exists():
                shutil.rmtree(run_dir, ignore_errors=True)

        return _build_result("event_persist", self.iterations, total, per_call, mem)

    def profile_scheduling(self) -> ProfileResult:
        """Profile task scheduling heuristic (sort + priority assignment)."""

        items = [
            {"key": f"PROJ-{i}", "priority": (i % 5) + 1, "points": (i % 8) + 1} for i in range(100)
        ]

        def _schedule() -> list[dict[str, Any]]:
            return sorted(items, key=lambda x: (x["priority"], -x["points"]))

        total, per_call, mem = _time_iterations(_schedule, self.iterations)
        return _build_result("scheduling", self.iterations, total, per_call, mem)

    def profile_validation(self) -> ProfileResult:
        """Profile validation recipe selection from a tech fingerprint."""
        from sendsprint.tech import TechFingerprint
        from sendsprint.validation_recipes import RecipeSelector

        fp = TechFingerprint(
            repo_path=str(self._tmp_dir),
            techs=["python", "node", "react", "docker"],
            signals={"pyproject.toml": "python", "package.json": "node"},
        )
        selector = RecipeSelector(fp)

        def _validate() -> None:
            selector.select()

        total, per_call, mem = _time_iterations(_validate, self.iterations)
        return _build_result("validation", self.iterations, total, per_call, mem)

    def profile_evidence(self) -> ProfileResult:
        """Profile evidence bundle creation + item addition."""
        import shutil
        import uuid

        from sendsprint.evidence import BundleManager, EvidenceItemType

        self._tmp_dir.mkdir(parents=True, exist_ok=True)
        mgr = BundleManager(base_dir=self._tmp_dir)

        def _evidence_write() -> None:
            rid = f"profile-{uuid.uuid4().hex[:8]}"
            bundle = mgr.create_bundle(rid)
            mgr.add_item(
                bundle,
                EvidenceItemType.log,
                "profiling evidence write test",
                {"source": "profiling_baseline"},
            )
            mgr.finalize(bundle)

        try:
            total, per_call, mem = _time_iterations(_evidence_write, self.iterations)
        finally:
            evidence_dir = self._tmp_dir / ".sendsprint" / "evidence"
            if evidence_dir.exists():
                shutil.rmtree(evidence_dir, ignore_errors=True)

        return _build_result("evidence_write", self.iterations, total, per_call, mem)

    # -- aggregate ----------------------------------------------------------

    def run_all(self) -> list[ProfileResult]:
        """Run all six profilers and return results."""
        return [
            self.profile_scan(),
            self.profile_dedupe(),
            self.profile_events(),
            self.profile_scheduling(),
            self.profile_validation(),
            self.profile_evidence(),
        ]


# ---------------------------------------------------------------------------
# Evidence persistence
# ---------------------------------------------------------------------------


def persist_as_evidence(
    results: list[ProfileResult],
    *,
    base_dir: str | Path = ".",
    run_id: str | None = None,
    thresholds: GoRustThresholds | None = None,
) -> Path:
    """Write profiling results as a JSON evidence artifact.

    Returns the path to the written file.
    """
    from sendsprint.evidence import BundleManager, EvidenceItemType

    run_id = run_id or f"profile-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S')}"
    thresholds = thresholds or GoRustThresholds()
    evaluations = thresholds.evaluate(results)

    payload = {
        "schema_version": "1.0",
        "run_id": run_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "results": [json.loads(r.model_dump_json()) for r in results],
        "evaluations": evaluations,
        "thresholds": json.loads(thresholds.model_dump_json()),
    }

    mgr = BundleManager(base_dir=base_dir)
    bundle = mgr.create_bundle(run_id)
    mgr.add_item(
        bundle,
        EvidenceItemType.log,
        json.dumps(payload, indent=2),
        {"source": "profiling_baseline", "operation_count": len(results)},
    )
    mgr.finalize(bundle)

    # Also write a standalone JSON alongside the bundle for easy attachment.
    output_dir = Path(base_dir).expanduser().resolve() / ".sendsprint" / "profiling"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{run_id}.json"
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    return output_path
