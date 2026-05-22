"""Adapter for GitHub Copilot Workspace (assign issue -> @copilot).

First-class provider, the most GitHub-native of the three. Dispatch creates
or assigns an issue to ``@copilot``; Copilot opens the PR in GitHub Actions.
The :class:`CopilotAdapter` therefore needs only a GitHub token with
``repo`` scope plus the target ``owner/repo``.
"""

from __future__ import annotations

import os

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


class CopilotAdapter(ProviderAdapter):
    """Ships tasks to GitHub Copilot via issue assignment."""

    name = "copilot"

    def __init__(
        self,
        github_token: str | None = None,
        repository: str | None = None,
    ) -> None:
        self._token = github_token or os.getenv("GITHUB_TOKEN", "")
        self._repository = repository or os.getenv("COPILOT_TARGET_REPO")

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(cloud=True, network=True, mcp=False)

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        self._require_auth()
        if not self._repository:
            raise ProviderError("COPILOT_TARGET_REPO is not set; cannot dispatch to Copilot")
        raise ProviderError(
            "copilot adapter dispatch is not yet wired to the GitHub issue assignment "
            "flow (tracked under the COPILOT sub-issue)"
        )

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        raise ProviderError("copilot adapter poll is not yet implemented")

    def collect(self, ticket: DispatchTicket) -> PRResult:
        raise ProviderError("copilot adapter collect is not yet implemented")

    def _require_auth(self) -> None:
        if not self._token:
            raise ProviderAuthError("GITHUB_TOKEN is not set; cannot assign issues to @copilot")
