"""Adapter for Claude routines / managed-agents API.

First-class provider (vendor exposes a real external trigger via the
Anthropic API). The actual dispatch/poll/collect implementation will land in
the CLAUDE sub-issue; until then the adapter declares its capabilities and
raises a clear :class:`ProviderError` when an unwired path is exercised.
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


class ClaudeAdapter(ProviderAdapter):
    """Ships tasks to Anthropic's managed agent infrastructure."""

    name = "claude"

    def __init__(
        self,
        api_key: str | None = None,
        environment_id: str | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self._environment_id = environment_id or os.getenv("CLAUDE_ROUTINE_ENV_ID")

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(cloud=True, network=True, mcp=False)

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        self._require_auth()
        raise ProviderError(
            "claude adapter dispatch is not yet wired to the Anthropic managed-agents "
            "API (tracked under the CLAUDE sub-issue)"
        )

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        raise ProviderError("claude adapter poll is not yet implemented")

    def collect(self, ticket: DispatchTicket) -> PRResult:
        raise ProviderError("claude adapter collect is not yet implemented")

    def _require_auth(self) -> None:
        if not self._api_key:
            raise ProviderAuthError(
                "ANTHROPIC_API_KEY is not set; cannot dispatch to the Claude cloud"
            )
