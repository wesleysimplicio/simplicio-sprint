"""Wrapper around the ``simplicio-cli`` task executor.

``simplicio-cli`` (https://github.com/wesleysimplicio/simplicio-cli) is a
stateless executor: given one task it generates a diff, applies it with
``git apply``, runs the configured test command and retries up to 3 times.
It does NOT know about sprints, branches, commits or pull requests — all of
that orchestration is SendSprint's job. This module is the single boundary
SendSprint uses to invoke it.

Invocation (per the simplicio-cli README)::

    simplicio task "<description>" \
        --stack <stack> \
        --target <path> \
        --criteria "<acceptance>" \
        --constraints "<rules>"

Configuration is read from the environment by simplicio itself
(``SIMPLICIO_MODEL``, ``SIMPLICIO_BASE_URL``, ``SIMPLICIO_TEST_CMD``); this
wrapper only passes them through.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sendsprint.models.reports import StepReport
from sendsprint.models.sprint import SprintItem

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

DEFAULT_BINARY = "simplicio"
DEFAULT_TIMEOUT_S = 1800
EXECUTE_STEP = 3


class SimplicioNotInstalled(RuntimeError):
    """Raised when the ``simplicio`` binary is not on PATH."""


@dataclass(frozen=True)
class SimplicioTask:
    """A single normalized task ready to hand to ``simplicio task``."""

    description: str
    stack: str | None = None
    target: str | None = None
    criteria: str | None = None
    constraints: str | None = None

    def argv(self, binary: str = DEFAULT_BINARY) -> list[str]:
        argv = [binary, "task", self.description]
        if self.stack:
            argv += ["--stack", self.stack]
        if self.target:
            argv += ["--target", self.target]
        if self.criteria:
            argv += ["--criteria", self.criteria]
        if self.constraints:
            argv += ["--constraints", self.constraints]
        return argv


@dataclass
class SimplicioResult:
    """Outcome of one ``simplicio task`` invocation."""

    status: str  # "ok" | "failed" | "skipped"
    returncode: int | None
    stdout: str = ""
    stderr: str = ""
    message: str = ""
    argv: list[str] = field(default_factory=list)


def _slug(item: SprintItem) -> str:
    return item.key or item.id


class SimplicioExecutor:
    """Invoke ``simplicio task`` inside a repo working tree (e.g. a worktree).

    The executor is intentionally thin. It builds the command, runs it in
    ``repo_path`` and maps the result to a :class:`StepReport`. The diff is
    applied to the working tree by simplicio itself; SendSprint commits it.
    """

    DEFAULT_CONSTRAINTS = (
        "do not break the build; keep existing tests green; touch only what the task requires"
    )

    def __init__(
        self,
        repo_path: str | Path,
        *,
        binary: str = DEFAULT_BINARY,
        timeout_s: int = DEFAULT_TIMEOUT_S,
        runner: Runner = subprocess.run,
        env: dict[str, str] | None = None,
    ) -> None:
        self.repo_path = Path(repo_path)
        self.binary = binary
        self.timeout_s = timeout_s
        self._runner = runner
        self._env = env

    def is_available(self) -> bool:
        """True when the ``simplicio`` binary can be found on PATH."""
        return shutil.which(self.binary) is not None

    def task_from_item(
        self,
        item: SprintItem,
        *,
        stack: str | None = None,
        target: str | None = None,
        constraints: str | None = None,
    ) -> SimplicioTask:
        """Map a :class:`SprintItem` to a :class:`SimplicioTask`.

        Title + description become the instruction; acceptance criteria flow
        into ``--criteria`` so simplicio can self-check its work.
        """
        description = item.title.strip()
        if item.description:
            description = f"{description}\n\n{item.description.strip()}"
        return SimplicioTask(
            description=description,
            stack=stack,
            target=target,
            criteria=item.acceptance_criteria,
            constraints=constraints or self.DEFAULT_CONSTRAINTS,
        )

    def run(self, task: SimplicioTask) -> SimplicioResult:
        """Run one ``simplicio task`` invocation. Never raises on tool failure."""
        argv = task.argv(self.binary)
        if not self.is_available():
            return SimplicioResult(
                status="skipped",
                returncode=None,
                message=f"{self.binary} not installed (pip install simplicio-cli)",
                argv=argv,
            )
        try:
            proc = self._runner(
                argv,
                cwd=str(self.repo_path),
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
                env=self._env,
            )
        except FileNotFoundError:
            return SimplicioResult(
                status="skipped",
                returncode=None,
                message=f"{self.binary} not installed (pip install simplicio-cli)",
                argv=argv,
            )
        except subprocess.TimeoutExpired:
            return SimplicioResult(
                status="failed",
                returncode=None,
                message=f"simplicio task timed out after {self.timeout_s}s",
                argv=argv,
            )
        status = "ok" if proc.returncode == 0 else "failed"
        message = (
            "simplicio applied the diff and tests passed"
            if status == "ok"
            else f"simplicio task failed (exit {proc.returncode})"
        )
        return SimplicioResult(
            status=status,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            message=message,
            argv=argv,
        )

    def run_item(
        self,
        item: SprintItem,
        *,
        stack: str | None = None,
        target: str | None = None,
        repo: str | None = None,
    ) -> StepReport:
        """Execute one sprint item and return a :class:`StepReport`."""
        task = self.task_from_item(item, stack=stack, target=target)
        result = self.run(task)
        return StepReport(
            step=EXECUTE_STEP,
            name=f"execute:{_slug(item)}",
            repo=repo,
            tech=stack,
            status=result.status,  # type: ignore[arg-type]
            message=result.message,
        )

    def revise(
        self,
        feedback: str,
        *,
        stack: str | None = None,
        target: str | None = None,
        repo: str | None = None,
    ) -> StepReport:
        """Re-run simplicio to address PR review feedback on the same tree.

        Used by the PR review loop: actionable reviewer comments become a new
        task with constraints that protect the rest of the work.
        """
        task = SimplicioTask(
            description=f"Address the following pull request review feedback:\n\n{feedback}",
            stack=stack,
            target=target,
            constraints=(
                "address every review comment; do not regress unrelated code; keep tests green"
            ),
        )
        result = self.run(task)
        return StepReport(
            step=EXECUTE_STEP,
            name="revise:pr-feedback",
            repo=repo,
            tech=stack,
            status=result.status,  # type: ignore[arg-type]
            message=result.message,
        )
