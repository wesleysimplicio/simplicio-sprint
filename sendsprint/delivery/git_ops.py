"""Commit and push helpers used after simplicio applies a diff.

simplicio-cli only edits the working tree; SendSprint stages, commits and
pushes. Push uses bounded exponential backoff so transient network errors in a
cloud runner don't abort a delivery.
"""

from __future__ import annotations

import logging
import subprocess
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]


class GitError(RuntimeError):
    pass


class GitOps:
    """Thin git wrapper scoped to one working tree (a worktree)."""

    def __init__(
        self,
        work_dir: str | Path,
        *,
        runner: Runner = subprocess.run,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.work_dir = Path(work_dir)
        self._runner = runner
        self._sleep = sleep

    def has_changes(self) -> bool:
        result = self._run(["git", "status", "--porcelain"])
        return bool(result.stdout.strip())

    def commit_all(self, message: str) -> bool:
        """Stage everything and commit. Returns False when there is nothing to commit."""
        if not self.has_changes():
            return False
        self._run(["git", "add", "-A"])
        self._run(["git", "commit", "-m", message])
        return True

    def current_branch(self) -> str:
        return self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()

    def push(self, branch: str | None = None, *, remote: str = "origin", retries: int = 4) -> None:
        """Push the branch with exponential backoff (2s, 4s, 8s, 16s)."""
        target = branch or self.current_branch()
        delay = 2.0
        last: Exception | None = None
        for attempt in range(retries):
            try:
                self._run(["git", "push", "-u", remote, target])
                return
            except GitError as exc:
                last = exc
                logger.warning("push attempt %d failed: %s", attempt + 1, exc)
                if attempt < retries - 1:
                    self._sleep(delay)
                    delay *= 2
        raise GitError(f"git push failed after {retries} attempts: {last}")

    def _run(self, cmd: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return self._runner(
                cmd,
                cwd=str(self.work_dir),
                capture_output=True,
                text=True,
                check=True,
                timeout=120,
            )
        except subprocess.CalledProcessError as exc:
            raise GitError(f"git failed: {' '.join(cmd)}\n{exc.stderr}") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"git timed out: {' '.join(cmd)}") from exc
