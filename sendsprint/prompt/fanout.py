"""Wrapper around the simplicio-prompt subagent runtime (``kernel/subagent_runtime.py``).

The kernel is not a pip package, so the path to ``subagent_runtime.py`` is taken
from the ``SIMPLICIO_PROMPT_KERNEL`` env var (or passed explicitly). Invocation::

    python <kernel> --provider deepseek --subagents 600 --task "<task>" --json

``--dry-run`` runs offline (no key, no network) for cost preview and CI.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sendsprint.models.sprint import SprintItem

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

DEFAULT_PROVIDER = "deepseek"
DEFAULT_SUBAGENTS = 600
DEFAULT_TIMEOUT_S = 600
KERNEL_ENV = "SIMPLICIO_PROMPT_KERNEL"


@dataclass
class FanoutResult:
    """Aggregated outcome of one fan-out across N subagents."""

    status: str  # "ok" | "skipped" | "failed"
    requested: int = 0
    completed: int = 0
    failed: int = 0
    cost_usd: float = 0.0
    elapsed_s: float = 0.0
    provider: str = ""
    model: str = ""
    samples: list[str] = field(default_factory=list)
    message: str = ""

    def summary(self) -> str:
        if self.status != "ok":
            return self.message or self.status
        return (
            f"{self.completed}/{self.requested} subagents on {self.provider}:{self.model} "
            f"in {self.elapsed_s:.2f}s (${self.cost_usd:.6f})"
        )


class PromptFanout:
    """Fan a task out to N simplicio-prompt subagents. Never raises on tool failure."""

    def __init__(
        self,
        *,
        kernel_path: str | Path | None = None,
        python: str = sys.executable,
        provider: str = DEFAULT_PROVIDER,
        subagents: int = DEFAULT_SUBAGENTS,
        dry_run: bool = False,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        runner: Runner = subprocess.run,
        env: dict[str, str] | None = None,
    ) -> None:
        resolved = kernel_path or os.getenv(KERNEL_ENV)
        self.kernel_path = Path(resolved) if resolved else None
        self.python = python
        self.provider = provider
        self.subagents = subagents
        self.dry_run = dry_run
        self.timeout_s = timeout_s
        self._runner = runner
        self._env = env

    def is_available(self) -> bool:
        """True when the simplicio-prompt kernel can be located on disk."""
        return self.kernel_path is not None and self.kernel_path.exists()

    def argv(self, task: str, *, subagents: int, dry_run: bool) -> list[str]:
        argv = [
            self.python,
            str(self.kernel_path),
            "--provider",
            self.provider,
            "--subagents",
            str(subagents),
            "--task",
            task,
            "--json",
        ]
        if dry_run:
            argv.append("--dry-run")
        return argv

    def run(
        self, task: str, *, subagents: int | None = None, dry_run: bool | None = None
    ) -> FanoutResult:
        """Run one fan-out and parse its JSON report into a :class:`FanoutResult`."""
        n = subagents if subagents is not None else self.subagents
        offline = self.dry_run if dry_run is None else dry_run
        if not self.is_available():
            return FanoutResult(
                status="skipped",
                requested=n,
                message=(
                    f"simplicio-prompt kernel not found (set {KERNEL_ENV} to "
                    "kernel/subagent_runtime.py)"
                ),
            )
        argv = self.argv(task, subagents=n, dry_run=offline)
        try:
            proc = self._runner(
                argv, capture_output=True, text=True, timeout=self.timeout_s, env=self._env
            )
        except FileNotFoundError:
            return FanoutResult(status="skipped", requested=n, message=f"{self.python} not found")
        except subprocess.TimeoutExpired:
            return FanoutResult(
                status="failed", requested=n, message=f"fan-out timed out after {self.timeout_s}s"
            )
        if proc.returncode != 0:
            return FanoutResult(
                status="failed",
                requested=n,
                message=f"fan-out exited {proc.returncode}: {(proc.stderr or '').strip()[:200]}",
            )
        return self._parse(proc.stdout or "", requested=n)

    def brainstorm(self, item: SprintItem, *, subagents: int | None = None) -> FanoutResult:
        """Fan out an edge-case/plan brainstorm for a sprint item."""
        return self.run(_brainstorm_task(item), subagents=subagents)

    def _parse(self, stdout: str, *, requested: int) -> FanoutResult:
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return FanoutResult(
                status="failed", requested=requested, message="could not parse fan-out JSON"
            )
        usage = data.get("usage") or {}
        samples = [
            r.get("text", "")
            for r in data.get("results", [])
            if isinstance(r, dict) and r.get("ok") and r.get("text")
        ]
        return FanoutResult(
            status="ok",
            requested=int(data.get("requested", requested)),
            completed=int(data.get("completed", 0)),
            failed=int(data.get("failed", 0)),
            cost_usd=float(usage.get("cost_usd", 0.0)),
            elapsed_s=float(data.get("elapsed_s", 0.0)),
            provider=str(data.get("provider", self.provider)),
            model=str(data.get("model", "")),
            samples=samples[:5],
        )


def _brainstorm_task(item: SprintItem) -> str:
    parts = [f"Brainstorm edge cases, risks and an implementation plan for: {item.title}"]
    if item.description:
        parts.append(item.description.strip())
    if item.acceptance_criteria:
        parts.append(f"Acceptance criteria:\n{item.acceptance_criteria.strip()}")
    return "\n\n".join(parts)
