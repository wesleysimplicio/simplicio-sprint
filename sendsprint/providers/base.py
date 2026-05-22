"""ProviderAdapter contract for the SendSprint v2 cloud-first dispatcher.

A provider adapter ships a normalized :class:`~sendsprint.models.SprintItem`
to a coding-agent vendor cloud, polls until the run is done, and collects the
resulting PR. Adapters are independent of the router and the ingestion layer;
the router fans tasks out across whichever adapters declare ``cloud=True``.

Spec: ``.specs/v2/cloud-dispatcher.md`` (IFACE sub-issue).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from sendsprint.models import SprintItem

RunStatus = Literal["queued", "running", "done", "failed", "cancelled"]


class ProviderCapabilities(BaseModel):
    """Self-declared capabilities of a provider adapter.

    The router consults this to decide whether to dispatch to the provider
    (``cloud`` must be True) and to understand the runtime environment
    (network access, MCP availability).
    """

    cloud: bool = Field(
        description="True when the vendor exposes a real external trigger usable from CI."
    )
    network: bool = Field(
        default=True,
        description="True when the agent has outbound network during the run phase.",
    )
    mcp: bool = Field(
        default=False,
        description="True when the container can reach the SendSprint MCP servers.",
    )
    fallback: str | None = Field(
        default=None,
        description="Name of the fallback provider when this one declares cloud=False.",
    )


class DispatchTicket(BaseModel):
    """Receipt returned by :meth:`ProviderAdapter.dispatch`."""

    run_id: str
    provider: str
    item_key: str
    dispatched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, object] = Field(
        default_factory=dict,
        description="Vendor-specific payload kept for debugging (request ids, urls).",
    )


class PRResult(BaseModel):
    """Outcome of a completed dispatch."""

    run_id: str
    provider: str
    item_key: str
    status: RunStatus
    pr_url: str | None = None
    branch: str | None = None
    evidence_urls: list[str] = Field(default_factory=list)
    error: str | None = None


class ProviderError(RuntimeError):
    """Base class for adapter errors. Subclasses map to standardized failure modes."""


class ProviderAuthError(ProviderError):
    """Vendor rejected the credentials or the credential is missing."""


class ProviderTimeoutError(ProviderError):
    """Polling exceeded the configured wall-clock budget."""


class ProviderNoCloudError(ProviderError):
    """Adapter has no external cloud trigger; the router should skip or fall back."""


class ProviderVendorBlockedError(ProviderError):
    """Vendor closed an API or removed a workflow that the adapter relied on."""


class ProviderAdapter(ABC):
    """Common contract every cloud provider adapter implements.

    Concrete subclasses live next to this module (one per vendor). They are
    instantiated by :class:`sendsprint.providers.router.ProviderRouter`
    after :mod:`sendsprint.providers.registry` loads ``providers.yml``.

    The contract is deliberately small: dispatch a normalized task, poll a
    run, collect a PR. Anything more (multi-step prompting, retries,
    container customization) is the adapter's private concern.
    """

    name: str = "generic"

    @abstractmethod
    def dispatch(self, item: SprintItem) -> DispatchTicket:
        """Ship the task to the vendor cloud and return an opaque run id.

        The adapter is responsible for converting the normalized task into
        whatever the vendor accepts (issue body, routine payload, microVM
        env). The returned :class:`DispatchTicket` is what the router holds
        on to between calls to :meth:`poll` and :meth:`collect`.
        """

    @abstractmethod
    def poll(self, ticket: DispatchTicket) -> RunStatus:
        """Return the current status of the run identified by ``ticket``."""

    @abstractmethod
    def collect(self, ticket: DispatchTicket) -> PRResult:
        """Fetch the final PR result. Only valid when :meth:`poll` returns ``done``."""

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        """Static description of what this adapter can do."""
