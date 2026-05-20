"""Resource telemetry and fan-out decision receipts.

Captures logical CPUs, memory, CPU pressure/idle sampling, and records
fan-out policy decisions as explainable receipts persisted in evidence.

Graceful degradation: works without psutil on all platforms including
Windows.  Falls back to os/platform builtins when pressure metrics are
unavailable.

Implements issue #118.
"""

from __future__ import annotations

import json
import os
import platform
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ResourceSnapshot(BaseModel):
    """Point-in-time host resource reading."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    cpu_count: int
    memory_total_mb: int
    memory_available_mb: int
    cpu_pressure: float | None = None  # 0.0–1.0 load ratio, None = unavailable
    fallback_used: str | None = None  # e.g. "os_only", "loadavg"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LimitingFactor(StrEnum):
    """Why the fan-out was capped."""

    memory = "memory"
    cpu = "cpu"
    requested = "requested"
    unknown_telemetry = "unknown_telemetry"
    none = "none"  # no cap applied


class FanOutDecision(BaseModel):
    """Explainable receipt for a fan-out policy decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_agents: int
    allowed_agents: int
    limiting_factor: LimitingFactor
    thresholds: dict[str, Any] = Field(default_factory=dict)
    snapshot: ResourceSnapshot | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def summary(self) -> str:
        """Human-readable one-liner for CLI/log output."""
        if self.limiting_factor == LimitingFactor.none:
            return (
                f"fan-out: {self.allowed_agents}/{self.requested_agents} agents (no limit applied)"
            )
        return (
            f"fan-out: {self.allowed_agents}/{self.requested_agents} agents "
            f"(limited by {self.limiting_factor.value}, "
            f"thresholds={json.dumps(self.thresholds, default=str)})"
        )


# ---------------------------------------------------------------------------
# Snapshot capture
# ---------------------------------------------------------------------------

# Default per-agent memory reserve (MB).
_DEFAULT_AGENT_RESERVE_MB = 512

# Default CPU pressure ceiling (fraction of logical CPUs).
_DEFAULT_CPU_PRESSURE_CEIL = 0.85


def _read_memory() -> tuple[int, int]:
    """Return (total_mb, available_mb). Best-effort, cross-platform."""
    try:
        import psutil  # type: ignore[import-untyped]

        vm = psutil.virtual_memory()
        return int(vm.total / (1024 * 1024)), int(vm.available / (1024 * 1024))
    except (ImportError, Exception):
        pass

    # Linux fallback: /proc/meminfo
    try:
        info: dict[str, int] = {}
        with open("/proc/meminfo") as fh:
            for line in fh:
                parts = line.split()
                if len(parts) >= 2 and parts[0].rstrip(":") in (
                    "MemTotal",
                    "MemAvailable",
                ):
                    info[parts[0].rstrip(":")] = int(parts[1]) // 1024  # kB→MB
        if "MemTotal" in info and "MemAvailable" in info:
            return info["MemTotal"], info["MemAvailable"]
    except (OSError, ValueError):
        pass

    # macOS fallback: sysctl
    if platform.system() == "Darwin":
        try:
            import subprocess

            out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, timeout=5)
            total_mb = int(out.strip()) // (1024 * 1024)
            # No reliable free-memory sysctl; report total as available
            return total_mb, total_mb
        except (OSError, subprocess.SubprocessError, ValueError):
            pass

    return 0, 0


def _read_cpu_pressure() -> tuple[float | None, str | None]:
    """Return (pressure_ratio, fallback_name).

    pressure_ratio is a 0–1 float (fraction of CPU capacity used).
    Returns (None, "os_only") when measurement is impossible.
    """
    # Try psutil first
    try:
        import psutil  # type: ignore[import-untyped]

        pct = psutil.cpu_percent(interval=0.1)
        return round(pct / 100.0, 4), None
    except (ImportError, Exception):
        pass

    # Unix loadavg (Linux, macOS, BSDs)
    try:
        load1, _, _ = cast(Any, os).getloadavg()
        cpus = os.cpu_count() or 1
        return round(min(load1 / cpus, 1.0), 4), "loadavg"
    except (OSError, AttributeError):
        pass

    return None, "os_only"


def capture_snapshot() -> ResourceSnapshot:
    """Capture a point-in-time resource snapshot."""
    cpu_count = os.cpu_count() or 1
    total_mb, avail_mb = _read_memory()
    pressure, fallback = _read_cpu_pressure()
    return ResourceSnapshot(
        cpu_count=cpu_count,
        memory_total_mb=total_mb,
        memory_available_mb=avail_mb,
        cpu_pressure=pressure,
        fallback_used=fallback,
    )


# ---------------------------------------------------------------------------
# Fan-out policy
# ---------------------------------------------------------------------------


def decide_fanout(
    requested: int,
    snapshot: ResourceSnapshot | None = None,
    *,
    agent_reserve_mb: int = _DEFAULT_AGENT_RESERVE_MB,
    cpu_pressure_ceil: float = _DEFAULT_CPU_PRESSURE_CEIL,
) -> FanOutDecision:
    """Decide how many agents to allow and why.

    Priority: memory cap → CPU pressure cap → requested count.
    If snapshot is None (telemetry unavailable), allows the full request
    with ``limiting_factor=unknown_telemetry``.
    """
    if snapshot is None:
        return FanOutDecision(
            requested_agents=requested,
            allowed_agents=requested,
            limiting_factor=LimitingFactor.unknown_telemetry,
            thresholds={"note": "resource telemetry unavailable"},
        )

    thresholds: dict[str, Any] = {
        "agent_reserve_mb": agent_reserve_mb,
        "cpu_pressure_ceil": cpu_pressure_ceil,
    }

    # Memory cap
    if snapshot.memory_available_mb > 0 and agent_reserve_mb > 0:
        mem_max = snapshot.memory_available_mb // agent_reserve_mb
    else:
        mem_max = requested

    # CPU cap
    if snapshot.cpu_pressure is not None and cpu_pressure_ceil < 1.0:
        headroom = max(0.0, 1.0 - snapshot.cpu_pressure)
        cpu_slots = snapshot.cpu_count * headroom
        cpu_max = max(1, int(cpu_slots))
    else:
        cpu_max = requested

    allowed = min(requested, mem_max, cpu_max)
    allowed = max(allowed, 0)

    if allowed < requested and mem_max <= cpu_max:
        factor = LimitingFactor.memory
        thresholds["memory_available_mb"] = snapshot.memory_available_mb
        thresholds["mem_max_agents"] = mem_max
    elif allowed < requested:
        factor = LimitingFactor.cpu
        thresholds["cpu_pressure"] = snapshot.cpu_pressure
        thresholds["cpu_max_agents"] = cpu_max
    else:
        factor = LimitingFactor.none

    return FanOutDecision(
        requested_agents=requested,
        allowed_agents=allowed,
        limiting_factor=factor,
        thresholds=thresholds,
        snapshot=snapshot,
    )


# ---------------------------------------------------------------------------
# Evidence persistence
# ---------------------------------------------------------------------------


class ResourceTelemetry:
    """High-level facade for resource telemetry + evidence integration."""

    def __init__(self, evidence_dir: str | Path = ".sendsprint/evidence") -> None:
        self._evidence_dir = Path(evidence_dir)

    def capture_snapshot(self) -> ResourceSnapshot:
        return capture_snapshot()

    def record_fanout_decision(
        self,
        requested: int,
        snapshot: ResourceSnapshot | None = None,
        **kwargs: Any,
    ) -> FanOutDecision:
        if snapshot is None:
            snapshot = self.capture_snapshot()
        return decide_fanout(requested, snapshot, **kwargs)

    def persist_to_evidence(
        self,
        run_id: str,
        decision: FanOutDecision,
    ) -> Path:
        """Write the decision receipt as JSON inside the evidence bundle dir."""
        bundle_dir = self._evidence_dir / run_id
        bundle_dir.mkdir(parents=True, exist_ok=True)
        path = bundle_dir / "resource-telemetry.json"
        payload = {
            "schema_version": "1.0",
            "run_id": run_id,
            "decision": json.loads(decision.model_dump_json()),
        }
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        return path
