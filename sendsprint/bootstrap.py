"""Keep the external simplicio tools current.

``sendsprint update`` (and, per the runtime profile, the start of ``run`` /
``watch``) pulls the latest simplicio-cli (pip), the simplicio-prompt kernel
(git), and optionally simplicio-mapper (git). Everything here is best-effort: a
stale or missing tool degrades to a skipped/failed :class:`UpdateResult`, never
an aborted run. Network can be disabled with ``SENDSPRINT_NO_UPDATE=1``.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

SIMPLICIO_PROMPT_REPO = "https://github.com/wesleysimplicio/simplicio-prompt"
SIMPLICIO_MAPPER_REPO = "https://github.com/wesleysimplicio/simplicio-mapper"
PROMPT_KERNEL_REL = Path("kernel/subagent_runtime.py")
DEFAULT_TIMEOUT_S = 300


def cache_dir() -> Path:
    """Where SendSprint caches git-cloned tools (override: ``SENDSPRINT_CACHE_DIR``)."""
    return Path(os.environ.get("SENDSPRINT_CACHE_DIR", "~/.cache/sendsprint")).expanduser()


def default_prompt_kernel() -> Path:
    """Conventional path to the simplicio-prompt kernel inside the cache."""
    return cache_dir() / "simplicio-prompt" / PROMPT_KERNEL_REL


@dataclass
class UpdateResult:
    """Outcome of one tool update / check."""

    name: str
    status: str  # "ok" | "skipped" | "failed"
    detail: str = ""

    def line(self) -> str:
        return f"{self.name}: {self.status}" + (f" — {self.detail}" if self.detail else "")


@dataclass
class StartupReport:
    """Aggregated results of an update/startup pass."""

    results: list[UpdateResult] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(r.status != "failed" for r in self.results)


class Updater:
    """Run the tool updates. Subprocess calls go through an injectable runner."""

    def __init__(
        self,
        *,
        runner: Runner = subprocess.run,
        python: str = sys.executable,
        cache: Path | None = None,
        timeout_s: int = DEFAULT_TIMEOUT_S,
    ) -> None:
        self._runner = runner
        self.python = python
        self.cache = Path(cache) if cache is not None else cache_dir()
        self.timeout_s = timeout_s

    def _run(self, argv: list[str]) -> subprocess.CompletedProcess[str]:
        return self._runner(argv, capture_output=True, text=True, timeout=self.timeout_s)

    # -- individual tools ---------------------------------------------------

    def update_simplicio_cli(self) -> UpdateResult:
        try:
            proc = self._run([self.python, "-m", "pip", "install", "-U", "simplicio-cli"])
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            return UpdateResult("simplicio-cli", "failed", str(exc))
        if proc.returncode != 0:
            return UpdateResult("simplicio-cli", "failed", (proc.stderr or "").strip()[:200])
        return UpdateResult("simplicio-cli", "ok", "pip install -U")

    def update_simplicio_prompt(self) -> UpdateResult:
        dest = self.cache / "simplicio-prompt"
        res = self._git_sync("simplicio-prompt", SIMPLICIO_PROMPT_REPO, dest)
        if res.status == "ok":
            kernel = dest / PROMPT_KERNEL_REL
            res.detail = f"{res.detail}; kernel at {kernel}"
            os.environ.setdefault("SIMPLICIO_PROMPT_KERNEL", str(kernel))
        return res

    def update_simplicio_mapper(self) -> UpdateResult:
        dest = self.cache / "simplicio-mapper"
        return self._git_sync("simplicio-mapper", SIMPLICIO_MAPPER_REPO, dest)

    # -- batches ------------------------------------------------------------

    def update_all(
        self, *, cli: bool = True, prompt: bool = True, mapper: bool = True
    ) -> StartupReport:
        report = StartupReport()
        if cli:
            report.results.append(self.update_simplicio_cli())
        if prompt:
            report.results.append(self.update_simplicio_prompt())
        if mapper:
            report.results.append(self.update_simplicio_mapper())
        return report

    def run_startup(self, profile: object) -> StartupReport:
        """Run only the passes enabled by the runtime profile flags."""
        runtime = getattr(profile, "runtime", None)
        report = StartupReport()
        if getattr(runtime, "verify_dependencies_on_start", False):
            report.results.extend(self.verify_dependencies())
        if getattr(runtime, "update_simplicio_prompt_on_start", False):
            report.results.append(self.update_simplicio_prompt())
        if getattr(runtime, "update_llm_project_mapper_on_start", False):
            report.results.append(self.update_simplicio_mapper())
        return report

    def verify_dependencies(self) -> list[UpdateResult]:
        results = [
            _which("simplicio", "not installed (pip install simplicio-cli)"),
            _which("git", "git not found on PATH", fail=True),
        ]
        kernel = Path(os.getenv("SIMPLICIO_PROMPT_KERNEL") or default_prompt_kernel())
        results.append(
            UpdateResult(
                "simplicio-prompt kernel",
                "ok" if kernel.exists() else "skipped",
                str(kernel),
            )
        )
        return results

    # -- internals ----------------------------------------------------------

    def _git_sync(self, name: str, repo_url: str, dest: Path) -> UpdateResult:
        dest = Path(dest)
        try:
            if (dest / ".git").exists():
                proc = self._run(["git", "-C", str(dest), "pull", "--ff-only"])
                action = "pulled"
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                proc = self._run(["git", "clone", "--depth", "1", repo_url, str(dest)])
                action = "cloned"
        except (FileNotFoundError, subprocess.SubprocessError) as exc:
            return UpdateResult(name, "failed", str(exc))
        if proc.returncode != 0:
            return UpdateResult(name, "failed", (proc.stderr or "").strip()[:200])
        return UpdateResult(name, "ok", action)


def _which(binary: str, missing_detail: str, *, fail: bool = False) -> UpdateResult:
    if shutil.which(binary):
        return UpdateResult(binary, "ok", "on PATH")
    return UpdateResult(binary, "failed" if fail else "skipped", missing_detail)
