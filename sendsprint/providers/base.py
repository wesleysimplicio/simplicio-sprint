"""ProviderAdapter contract for the SendSprint v2 dispatcher (cloud + local).

A provider adapter ships a normalized :class:`~sendsprint.models.SprintItem`
to an execution surface (a vendor cloud, a local worktree-driven loop, or a
GitHub Actions runner), polls until the run is done, and collects the
resulting PR. Adapters are independent of the router and the ingestion layer;
the router fans tasks out across whichever adapters declare ``dispatchable=True``.

Modes:
    * ``cloud``         — work runs on a vendor-managed VM (Claude / Codex / Cursor / ...)
    * ``local``         — work runs locally in a git worktree via ``/ralph`` or ``/goal``
    * ``github-action`` — work runs on GitHub Actions (Copilot issue assignment)

Air-gapped or non-GitHub projects rely on ``local`` adapters; cloud-friendly
projects use ``cloud`` (or ``github-action``) ones. The router does not care:
parallelism is uniform across modes.

Spec: ``.specs/v2/cloud-dispatcher.md`` (IFACE sub-issue).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

from sendsprint.models import SprintItem

RunStatus = Literal["queued", "running", "done", "failed", "cancelled"]
DispatchMode = Literal["cloud", "local", "github-action"]


class ProviderCapabilities(BaseModel):
    """Self-declared capabilities of a provider adapter.

    The router consults this to decide whether to dispatch to the provider
    (``dispatchable`` must be True) and to understand the runtime environment
    (mode, network access, MCP availability).
    """

    mode: DispatchMode = Field(
        description=(
            "Execution surface the adapter targets: 'cloud' for vendor-managed VMs, "
            "'local' for in-repo worktree loops (/ralph, /goal), or 'github-action' "
            "for GitHub Actions runners."
        ),
    )
    dispatchable: bool = Field(
        description=(
            "True when the adapter is wired to actually execute work right now. "
            "Spike adapters declare False so the router falls back instead of dispatching."
        ),
    )
    network: bool = Field(
        default=True,
        description="True when the agent has outbound network during the run phase.",
    )
    mcp: bool = Field(
        default=False,
        description="True when the runtime can reach the SendSprint MCP servers.",
    )
    fallback: str | None = Field(
        default=None,
        description="Name of the fallback provider when this one declares dispatchable=False.",
    )


class DispatchTicket(BaseModel):
    """Receipt returned by :meth:`ProviderAdapter.dispatch`."""

    run_id: str
    provider: str
    item_key: str
    dispatched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw: dict[str, object] = Field(
        default_factory=dict,
        description="Vendor-specific payload kept for debugging (request ids, urls, pids).",
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


class ProviderNotDispatchableError(ProviderError):
    """Adapter has no usable execution path; the router should skip or fall back."""


class ProviderVendorBlockedError(ProviderError):
    """Vendor closed an API or removed a workflow that the adapter relied on."""


# Backwards-compatible alias (kept until external consumers migrate).
ProviderNoCloudError = ProviderNotDispatchableError


class ProviderAdapter(ABC):
    """Common contract every provider adapter implements (cloud, local, or actions).

    Concrete subclasses live next to this module (one per vendor / local loop).
    They are instantiated by :class:`sendsprint.providers.router.ProviderRouter`
    after :mod:`sendsprint.providers.registry` loads ``providers.yml``.

    The contract is deliberately small: dispatch a normalized task, poll a
    run, collect a PR. Anything more (multi-step prompting, retries,
    container or worktree customization) is the adapter's private concern.
    """

    name: str = "generic"

    @abstractmethod
    def dispatch(self, item: SprintItem) -> DispatchTicket:
        """Ship the task to the execution surface and return an opaque run id.

        The adapter is responsible for converting the normalized task into
        whatever the surface accepts (issue body, routine payload, microVM
        env, worktree task.md). The returned :class:`DispatchTicket` is what
        the router holds on to between calls to :meth:`poll` and :meth:`collect`.
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
