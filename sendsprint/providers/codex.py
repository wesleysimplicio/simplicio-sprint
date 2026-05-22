"""Adapter for Codex Cloud (OpenAI microVM, fire-and-forget).

First-class provider. Two-phase environment: setup phase has network and
installs deps; the agent phase runs offline. Env vars persist via
``~/.bashrc`` or vendor environment settings, not via ``export``.
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


class CodexAdapter(ProviderAdapter):
    """Ships tasks to OpenAI's Codex Cloud microVM."""

    name = "codex"

    def __init__(
        self,
        api_key: str | None = None,
        environment_id: str | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self._environment_id = environment_id or os.getenv("CODEX_ENVIRONMENT_ID")

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(cloud=True, network=False, mcp=False)

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        self._require_auth()
        raise ProviderError(
            "codex adapter dispatch is not yet wired to the Codex Cloud API "
            "(tracked under the CODEX sub-issue)"
        )

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        raise ProviderError("codex adapter poll is not yet implemented")

    def collect(self, ticket: DispatchTicket) -> PRResult:
        raise ProviderError("codex adapter collect is not yet implemented")

    def _require_auth(self) -> None:
        if not self._api_key:
            raise ProviderAuthError("OPENAI_API_KEY is not set; cannot dispatch to Codex Cloud")
