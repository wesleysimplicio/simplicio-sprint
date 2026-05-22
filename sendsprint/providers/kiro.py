"""Adapter for Kiro (spike).

Kiro (AWS) is spec-driven and IDE-bound; no clean external cloud trigger is
known. Until the KIRO spike documents one the adapter declares
``cloud=False`` and the router falls back to Codex.
"""

from __future__ import annotations

from sendsprint.models import SprintItem
from sendsprint.providers.base import (
    DispatchTicket,
    ProviderAdapter,
    ProviderCapabilities,
    ProviderNoCloudError,
    PRResult,
    RunStatus,
)


class KiroAdapter(ProviderAdapter):
    """Spike adapter for Kiro; declared cloud-incapable until trigger is confirmed."""

    name = "kiro"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(cloud=False, network=True, mcp=False, fallback="codex")

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        raise ProviderNoCloudError(
            "kiro has no confirmed external cloud trigger; route via the fallback "
            "provider declared in capabilities"
        )

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        raise ProviderNoCloudError("kiro adapter has no cloud trigger to poll")

    def collect(self, ticket: DispatchTicket) -> PRResult:
        raise ProviderNoCloudError("kiro adapter has no cloud trigger to collect from")
