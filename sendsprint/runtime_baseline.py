"""Runtime profiling baseline before optional Go/Rust split work."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.scheduler import AgentFanoutPolicy, HostResourceSnapshot
from sendsprint.tech import detect_tech
from sendsprint.templates import select_validation_template


class RuntimeBenchmarkCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    elapsed_ms: float = Field(ge=0)
    operations: int = Field(ge=0)
    metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class RuntimeBenchmarkReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo_path: str
    generated_at: str
    cases: list[RuntimeBenchmarkCase]
    thresholds: dict[str, str]
    evidence_path: str | None = None


def run_runtime_baseline(
    repo_path: str | Path,
    *,
    output: str | Path | None = None,
    max_files: int = 2_000,
) -> RuntimeBenchmarkReport:
    """Run a small, cross-platform baseline and optionally write JSON evidence."""
    repo = Path(repo_path).expanduser().resolve()
    files = _limited_files(repo, max_files=max_files)
    cases = [
        _time_case("scan.files", lambda: _scan_files(files), operations=len(files)),
        _time_case("dedupe.hash", lambda: _hash_files(repo, files), operations=len(files)),
        _time_case("scheduling.fanout", _fanout_decision, operations=1),
        _time_case("validation.selection", lambda: _validation_selection(repo), operations=1),
        _time_case("evidence.write", _evidence_write, operations=1),
    ]
    report = RuntimeBenchmarkReport(
        repo_path=str(repo),
        generated_at=datetime.now(UTC).isoformat(),
        cases=cases,
        thresholds={
            "go_worker": (
                "consider only after queue/watchdog/fanout paths exceed "
                "local responsiveness budget"
            ),
            "rust_accelerator": (
                "consider only after scan/dedupe/cache paths have benchmark evidence"
            ),
            "fallback": "Python implementation remains canonical unless parity tests pass",
        },
    )
    if output is not None:
        target = Path(output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report.model_dump_json(indent=2) + "\n", encoding="utf-8")
        report = report.model_copy(update={"evidence_path": str(target)})
    return report


def _time_case(
    name: str,
    fn: Callable[[], dict[str, str | int | float | bool | None]],
    *,
    operations: int,
) -> RuntimeBenchmarkCase:
    started = time.perf_counter()
    metadata = fn()
    elapsed_ms = round((time.perf_counter() - started) * 1000, 3)
    return RuntimeBenchmarkCase(
        name=name,
        elapsed_ms=elapsed_ms,
        operations=operations,
        metadata=metadata,
    )


def _limited_files(repo: Path, *, max_files: int) -> list[Path]:
    ignored = {".git", ".ruff_cache", ".pytest_cache", "node_modules", "__pycache__"}
    files: list[Path] = []
    for path in repo.rglob("*"):
        if any(part in ignored for part in path.parts):
            continue
        if path.is_file():
            files.append(path)
            if len(files) >= max_files:
                break
    return files


def _scan_files(files: list[Path]) -> dict[str, int]:
    total_bytes = sum(path.stat().st_size for path in files if path.exists())
    return {"files": len(files), "bytes": total_bytes}


def _hash_files(repo: Path, files: list[Path]) -> dict[str, str | int]:
    digest = hashlib.sha256()
    for path in files:
        rel = path.relative_to(repo).as_posix()
        digest.update(rel.encode("utf-8"))
        digest.update(str(path.stat().st_size if path.exists() else 0).encode("ascii"))
    return {"files": len(files), "digest": digest.hexdigest()}


def _fanout_decision() -> dict[str, str | int | float | bool | None]:
    snapshot = HostResourceSnapshot.current()
    receipt = AgentFanoutPolicy(requested_agents=5).decision_for(snapshot)
    return {
        "allowed_agents": receipt.allowed_agents,
        "limiting_factor": receipt.limiting_factor,
        "cpu_idle_percent": snapshot.cpu_idle_percent,
        "available_memory_mb": snapshot.available_memory_mb,
    }


def _validation_selection(repo: Path) -> dict[str, str | int]:
    fingerprint = detect_tech(repo)
    template = select_validation_template(fingerprint, repo)
    return {
        "template": template.name,
        "tech_count": len(fingerprint.techs),
        "role_count": len(fingerprint.roles),
    }


def _evidence_write() -> dict[str, int]:
    with TemporaryDirectory(prefix="sendsprint-baseline-") as tmp:
        path = Path(tmp) / "baseline-evidence.json"
        path.write_text(json.dumps({"ok": True}), encoding="utf-8")
        return {"bytes": path.stat().st_size}
