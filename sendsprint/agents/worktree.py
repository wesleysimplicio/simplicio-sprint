"""Git worktree manager for parallel agent branches."""

from __future__ import annotations

import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class WorktreeError(RuntimeError):
    pass


class WorktreeManager:
    """Create / remove git worktrees so agents work in parallel branches."""

    def __init__(self, repo_path: str | Path) -> None:
        self.repo = Path(repo_path).resolve()
        if not (self.repo / ".git").exists():
            raise WorktreeError(f"not a git repo: {self.repo}")

    def create(self, branch: str, *, base: str = "HEAD") -> Path:
        wt_dir = self.worktree_dir(branch)
        if wt_dir.exists():
            logger.info("worktree already exists: %s", wt_dir)
            return wt_dir
        self._run(["git", "worktree", "add", "-b", branch, str(wt_dir), base])
        logger.info("created worktree %s on branch %s", wt_dir, branch)
        return wt_dir

    def remove(self, branch: str) -> None:
        wt_dir = self.worktree_dir(branch)
        if not wt_dir.exists():
            return
        self._run(["git", "worktree", "remove", str(wt_dir), "--force"])
        logger.info("removed worktree %s", wt_dir)

    def list_worktrees(self) -> list[str]:
        result = self._run(["git", "worktree", "list", "--porcelain"])
        return [
            str(Path(line.split(" ", 1)[1]).resolve())
            for line in result.stdout.splitlines()
            if line.startswith("worktree ")
        ]

    def current_branch(self, wt_dir: Path | None = None) -> str:
        cwd = str(wt_dir) if wt_dir else str(self.repo)
        result = self._run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        return result.stdout.strip()

    def worktree_dir(self, branch: str) -> Path:
        """Return the deterministic worktree path for a branch."""
        safe_branch = re.sub(r"[^A-Za-z0-9._-]+", "-", branch).strip("-") or "branch"
        return self.repo.parent / f"{self.repo.name}-wt-{safe_branch}"

    def _run(self, cmd: list[str], *, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                cmd,
                cwd=cwd or str(self.repo),
                capture_output=True,
                text=True,
                check=True,
                timeout=60,
            )
        except subprocess.CalledProcessError as exc:
            raise WorktreeError(
                f"git command failed: {' '.join(cmd)}\nstderr: {exc.stderr}"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise WorktreeError(f"git command timed out: {' '.join(cmd)}") from exc
