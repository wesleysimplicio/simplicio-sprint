"""Adapter for the local Ralph autonomous loop (``/ralph``).

Targets projects that cannot use vendor clouds or GitHub Actions (air-gapped,
on-prem, private repos on Bitbucket/GitLab). Dispatch runs the ``ralph`` CLI
in a parallel git worktree per :class:`~sendsprint.models.SprintItem`; the
loop drives ``read -> plan -> execute -> lint -> unit -> e2e -> fix -> repeat``
against the task file until DoD exits.

The router keeps doing parallel dispatch — parallelism comes from running
multiple worktrees concurrently, not from any cloud fan-out.

Pre-requisites checked at dispatch time:
    * ``ralph`` CLI on ``$PATH`` (the project pins
      https://github.com/frankbria/ralph-claude-code).
    * ``.ralph/config.toml`` exists in the target repo.

Spec: ``.specs/v2/cloud-dispatcher.md`` (LOCAL-RALPH sub-issue).
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


class LocalRalphAdapter(ProviderAdapter):
    """Runs the Ralph autonomous loop in a local git worktree."""

    name = "local-ralph"

    def __init__(
        self,
        repo_path: str | None = None,
        ralph_binary: str | None = None,
        config_path: str | None = None,
    ) -> None:
        resolved_repo: str = repo_path or os.getenv("SENDSPRINT_LOCAL_REPO") or "."
        resolved_bin: str = ralph_binary or os.getenv("RALPH_BINARY") or "ralph"
        self._repo_path = Path(resolved_repo).resolve()
        self._ralph_binary = resolved_bin
        self._config_path = Path(config_path or ".ralph/config.toml")

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(mode="local", dispatchable=True, network=True, mcp=True)

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        self._require_tools()
        raise ProviderError(
            "local-ralph adapter dispatch is not yet wired to spawn the ralph subprocess "
            "inside a fresh worktree (tracked under the LOCAL-RALPH sub-issue)"
        )

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        raise ProviderError("local-ralph adapter poll is not yet implemented")

    def collect(self, ticket: DispatchTicket) -> PRResult:
        raise ProviderError("local-ralph adapter collect is not yet implemented")

    def _require_tools(self) -> None:
        if shutil.which(self._ralph_binary) is None:
            raise ProviderAuthError(
                f"ralph CLI '{self._ralph_binary}' not found on $PATH; "
                f"install https://github.com/frankbria/ralph-claude-code or set RALPH_BINARY"
            )
        config_full = self._repo_path / self._config_path
        if not config_full.is_file():
            raise ProviderAuthError(
                f"ralph config '{config_full}' is missing; "
                f"local-ralph requires the project to be Ralph-ready"
            )
