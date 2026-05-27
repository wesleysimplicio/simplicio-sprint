"""Wrapper around the simplicio-prompt subagent runtime (``kernel/subagent_runtime.py``).

The kernel is not a pip package, so the path to ``subagent_runtime.py`` is taken
from the ``SIMPLICIO_PROMPT_KERNEL`` env var (or passed explicitly). Invocation::

    python <kernel> --provider deepseek --subagents 600 --task "<task>" --json

``--dry-run`` runs offline (no key, no network) for cost preview and CI.
"""

from __future__ import annotations

import json
import logging
import math
import os
import subprocess
import sys
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass, field
from importlib import util as importlib_util
from pathlib import Path
from typing import Any

from sendsprint.models.sprint import SprintItem

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

DEFAULT_PROVIDER = "deepseek"
DEFAULT_SUBAGENTS = 600
DEFAULT_TIMEOUT_S = 600
KERNEL_ENV = "SIMPLICIO_PROMPT_KERNEL"
PROMPT_REPO_ENV = "SIMPLICIO_PROMPT_REPO"
PROMPT_FANOUT_REL = Path("examples/python/prompt_fanout.py")


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
    runtime: str = "subprocess"
    token_usage: dict[str, Any] = field(default_factory=dict)
    samples: list[str] = field(default_factory=list)
    message: str = ""

    def summary(self) -> str:
        if self.status != "ok":
            return self.message or self.status
        runtime = f" via {self.runtime}" if self.runtime else ""
        return (
            f"{self.completed}/{self.requested} subagents on {self.provider}:{self.model} "
            f"{runtime} in {self.elapsed_s:.2f}s (${self.cost_usd:.6f})"
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
        prompt_repo: str | Path | None = None,
        repo: str = "",
        mapper_context: dict[str, Any] | None = None,
        depth: int = 2,
        branching: int | None = None,
        compression_threshold: int | None = None,
        use_tuple_runtime: bool | None = None,
    ) -> None:
        resolved = kernel_path or os.getenv(KERNEL_ENV)
        if not resolved:
            from sendsprint.bootstrap import default_prompt_kernel

            candidate = default_prompt_kernel()
            if candidate.exists():
                resolved = str(candidate)
        self.kernel_path = Path(resolved) if resolved else None
        prompt_resolved = prompt_repo or os.getenv(PROMPT_REPO_ENV)
        self.prompt_repo = Path(prompt_resolved).expanduser() if prompt_resolved else None
        self.python = python
        self.provider = provider
        self.subagents = subagents
        self.dry_run = dry_run
        self.timeout_s = timeout_s
        self._runner = runner
        self._env = env
        self.repo = repo or "repository"
        self.mapper_context = mapper_context or {}
        self.depth = max(1, depth)
        self.branching = branching
        self.compression_threshold = compression_threshold
        self.use_tuple_runtime = use_tuple_runtime

    def is_available(self) -> bool:
        """True when either the tuple adapter or legacy kernel can be located."""
        return self._tuple_adapter_path() is not None or (
            self.kernel_path is not None and self.kernel_path.exists()
        )

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
        self,
        task: str,
        *,
        subagents: int | None = None,
        dry_run: bool | None = None,
        mapper_context: dict[str, Any] | None = None,
    ) -> FanoutResult:
        """Run one fan-out and parse its JSON report into a :class:`FanoutResult`."""
        n = subagents if subagents is not None else self.subagents
        offline = self.dry_run if dry_run is None else dry_run
        context = mapper_context if mapper_context is not None else self.mapper_context
        tuple_path = self._tuple_adapter_path()
        if tuple_path is not None and self.use_tuple_runtime is not False:
            return self._run_tuple(task, requested=n, dry_run=offline, mapper_context=context)

        if self.kernel_path is None or not self.kernel_path.exists():
            return FanoutResult(
                status="skipped",
                requested=n,
                message=(
                    f"simplicio-prompt runtime not found (set {PROMPT_REPO_ENV} to the "
                    f"simplicio-prompt repo or {KERNEL_ENV} to kernel/subagent_runtime.py)"
                ),
            )
        runtime_task = task
        if context:
            encoded_context = json.dumps(context, sort_keys=True)[:4000]
            runtime_task = f"{task}\n\nMapper context:\n{encoded_context}"
        argv = self.argv(runtime_task, subagents=n, dry_run=offline)
        logger.info(
            "fan-out: %d subagents on %s%s", n, self.provider, " (dry-run)" if offline else ""
        )
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

    def brainstorm(
        self,
        item: SprintItem,
        *,
        subagents: int | None = None,
        mapper_context: dict[str, Any] | None = None,
    ) -> FanoutResult:
        """Fan out an edge-case/plan brainstorm for a sprint item."""
        return self.run(_brainstorm_task(item), subagents=subagents, mapper_context=mapper_context)

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
            runtime="subprocess",
            token_usage=usage if isinstance(usage, dict) else {},
            samples=samples[:5],
        )

    def _tuple_adapter_path(self) -> Path | None:
        if self.prompt_repo is None:
            return None
        path = self.prompt_repo / PROMPT_FANOUT_REL
        return path if path.exists() else None

    def _run_tuple(
        self,
        task: str,
        *,
        requested: int,
        dry_run: bool,
        mapper_context: dict[str, Any],
    ) -> FanoutResult:
        adapter_path = self._tuple_adapter_path()
        if adapter_path is None:
            return FanoutResult(
                status="skipped", requested=requested, message="tuple adapter missing"
            )
        try:
            module = self._load_tuple_module(adapter_path)
            adapter_cls = module.PromptFanout
            adapter = adapter_cls(repo=self.repo)
            depth, branching = self._batch_shape(requested)
            _, receipt = adapter.spawn_task(
                task,
                mapper_context=mapper_context,
                lane="analysis",
                depth=depth,
                branching=branching,
                compression_threshold=self.compression_threshold,
            )
            virtual_agents = int(getattr(receipt, "virtual_agents", branching**depth))
            adapter.record_tokens(
                "analysis",
                prompt_tokens=_estimate_tokens(task) + _estimate_tokens(mapper_context),
                completion_tokens=0 if dry_run else max(1, virtual_agents // 16),
                cost_usd=0.0,
                reason="sendsprint.fanout",
            )
            snapshot = adapter.snapshot()
        except Exception as exc:  # noqa: BLE001 - runtime adapters are optional
            logger.warning("tuple fan-out failed: %s", exc)
            return FanoutResult(status="failed", requested=requested, message=str(exc))

        token_usage = snapshot.get("token_usage") if isinstance(snapshot, dict) else {}
        if not isinstance(token_usage, dict):
            token_usage = {}
        cost = _total_cost(token_usage)
        receipt_id = getattr(receipt, "receipt_id", "unknown")
        samples = [
            (
                "batch_spawn "
                f"{receipt_id}: depth={depth}, branching={branching}, "
                f"virtual_agents={virtual_agents}"
            ),
            (
                "tuple snapshot "
                f"active={snapshot.get('active_agents', 0)} total={snapshot.get('total_agents', 0)}"
            ),
        ]
        files = list(mapper_context.get("relevant_files") or [])
        if files:
            file_paths = [
                str(entry.get("path", entry)) if isinstance(entry, dict) else str(entry)
                for entry in files[:4]
            ]
            samples.append(f"mapper files: {', '.join(file_paths)}")
        return FanoutResult(
            status="ok",
            requested=virtual_agents,
            completed=virtual_agents,
            failed=0,
            cost_usd=cost,
            elapsed_s=0.0,
            provider=self.provider,
            model="yool-tuple-hamt",
            runtime="tuple",
            token_usage=token_usage,
            samples=samples,
        )

    def _load_tuple_module(self, adapter_path: Path) -> Any:
        module_name = f"_sendsprint_prompt_fanout_{abs(hash(str(adapter_path)))}"
        spec = importlib_util.spec_from_file_location(module_name, adapter_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load {adapter_path}")
        module = importlib_util.module_from_spec(spec)
        sys.modules[module_name] = module
        repo_root = str(adapter_path.parents[2])
        inserted = False
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
            inserted = True
        try:
            spec.loader.exec_module(module)
        finally:
            if inserted:
                with suppress(ValueError):
                    sys.path.remove(repo_root)
        return module

    def _batch_shape(self, requested: int) -> tuple[int, int]:
        depth = self.depth
        if self.branching is not None:
            return depth, max(1, self.branching)
        branching = max(1, math.ceil(max(1, requested) ** (1 / depth)))
        while branching**depth < requested:
            branching += 1
        return depth, branching


def _brainstorm_task(item: SprintItem) -> str:
    parts = [f"Brainstorm edge cases, risks and an implementation plan for: {item.title}"]
    if item.description:
        parts.append(item.description.strip())
    if item.acceptance_criteria:
        parts.append(f"Acceptance criteria:\n{item.acceptance_criteria.strip()}")
    return "\n\n".join(parts)


def _estimate_tokens(value: object) -> int:
    text = (
        value
        if isinstance(value, str)
        else json.dumps(value or {}, sort_keys=True, default=str)
    )
    return max(1, len(text) // 4)


def _total_cost(token_usage: dict[str, Any]) -> float:
    if "total_cost_usd" in token_usage:
        return float(token_usage.get("total_cost_usd") or 0.0)
    lanes = token_usage.get("lanes") or {}
    if not isinstance(lanes, dict):
        return 0.0
    return float(
        sum(
            float(value.get("cost_usd") or 0.0)
            for value in lanes.values()
            if isinstance(value, dict)
        )
    )
