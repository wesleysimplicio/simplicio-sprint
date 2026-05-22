"""Adapter for the local /goal long-running agent overlay.

The /goal flow is SendSprint's universal long-running session pattern:
``PRD.md`` (task source) -> ``PROGRESS.md`` (checkpoints) -> ``GOAL_RESULT.md``
(final report), driven by the local Claude Code CLI (or any equivalent agent
runner). This adapter targets the same air-gapped / non-GitHub projects as
:class:`~sendsprint.providers.local_ralph.LocalRalphAdapter` but uses the
overlay instead of the Ralph loop.

Parallelism still comes from the router: one worktree per task, one agent
process per worktree.

Pre-requisites checked at dispatch time:
    * a local agent CLI on ``$PATH`` (defaults to ``claude``; override with
      ``SENDSPRINT_LOCAL_AGENT_BINARY``).

Spec: ``.specs/v2/cloud-dispatcher.md`` (LOCAL-GOAL sub-issue).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from sendsprint.models import SprintItem
from sendsprint.providers.base import (
    DispatchTicket,
    ProviderAdapter,
    ProviderAuthError,
    ProviderCapabilities,
    ProviderError,
    PRResult,
    RunStatus,
)


class LocalGoalAdapter(ProviderAdapter):
    """Runs the /goal long-running overlay in a local git worktree."""

    name = "local-goal"

    def __init__(
        self,
        repo_path: str | None = None,
        agent_binary: str | None = None,
    ) -> None:
        resolved_repo: str = repo_path or os.getenv("SENDSPRINT_LOCAL_REPO") or "."
        resolved_bin: str = agent_binary or os.getenv("SENDSPRINT_LOCAL_AGENT_BINARY") or "claude"
        self._repo_path = Path(resolved_repo).resolve()
        self._agent_binary = resolved_bin

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(mode="local", dispatchable=True, network=True, mcp=True)

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        self._require_tools()
        raise ProviderError(
            "local-goal adapter dispatch is not yet wired to start the agent process "
            "with PRD.md/PROGRESS.md/GOAL_RESULT.md inside a worktree (tracked under "
            "the LOCAL-GOAL sub-issue)"
        )

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        raise ProviderError("local-goal adapter poll is not yet implemented")

    def collect(self, ticket: DispatchTicket) -> PRResult:
        raise ProviderError("local-goal adapter collect is not yet implemented")

    def _require_tools(self) -> None:
        if shutil.which(self._agent_binary) is None:
            raise ProviderAuthError(
                f"local agent CLI '{self._agent_binary}' not found on $PATH; "
                f"install Claude Code (or another agent runner) or set "
                f"SENDSPRINT_LOCAL_AGENT_BINARY"
            )
