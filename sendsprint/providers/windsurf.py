"""Adapter for Windsurf Cascade (spike).

Cascade is IDE-first; external cloud triggers are likely nonexistent. Until
the WIND spike documents a viable path the adapter declares ``cloud=False``
and the router falls back to Claude.
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


class WindsurfAdapter(ProviderAdapter):
    """Spike adapter for Windsurf; declared cloud-incapable until trigger is confirmed."""

    name = "windsurf"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            mode="cloud", dispatchable=False, network=True, mcp=False, fallback="claude"
        )

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        raise ProviderNoCloudError(
            "windsurf has no confirmed external cloud trigger; route via the fallback "
            "provider declared in capabilities"
        )

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        raise ProviderNoCloudError("windsurf adapter has no cloud trigger to poll")

    def collect(self, ticket: DispatchTicket) -> PRResult:
        raise ProviderNoCloudError("windsurf adapter has no cloud trigger to collect from")
