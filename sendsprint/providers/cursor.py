"""Adapter for Cursor Background Agents (best-effort spike).

Cursor Background Agents run on an Ubuntu VM with network ON and respect
``.cursor/Dockerfile``, but the external trigger surface is IDE-bound. Until
the CURSOR spike confirms a usable API/CLI the adapter declares ``cloud=False``
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


class CursorAdapter(ProviderAdapter):
    """Spike adapter for Cursor; declared cloud-incapable until trigger is confirmed."""

    name = "cursor"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(cloud=False, network=True, mcp=False, fallback="claude")

    def dispatch(self, item: SprintItem) -> DispatchTicket:
        raise ProviderNoCloudError(
            "cursor has no confirmed external cloud trigger; route via the fallback "
            "provider declared in capabilities"
        )

    def poll(self, ticket: DispatchTicket) -> RunStatus:
        raise ProviderNoCloudError("cursor adapter has no cloud trigger to poll")

    def collect(self, ticket: DispatchTicket) -> PRResult:
        raise ProviderNoCloudError("cursor adapter has no cloud trigger to collect from")
