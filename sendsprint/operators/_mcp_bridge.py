"""Host-injected MCP transport seam for sprint operators.

SendSprint runs as an agent (Claude) whose host already has the Atlassian /
Azure DevOps / GitHub MCP servers wired in. The Python operators cannot call
those MCP tools directly, so this module is the seam: the host registers a
*provider* callable per source, and the operators fetch raw payloads through it
when reading a sprint over the ``mcp`` transport. With no provider registered,
:func:`fetch` raises and the operator falls back to its REST API transport.

The provider returns the SAME raw shapes the REST endpoints return, so each
operator reuses its existing ``_sprint_from_*`` mapping with no duplicate code:

- jira:        ``{"sprint": {...}, "issues": [{...}, ...]}``
- azuredevops: ``{"work_items": [{...}, ...]}``  (``value`` / ``workItems`` accepted)
- github:      ``{"issues": [{...}, ...]}``

Register from the host once the MCP data is in hand::

    from sendsprint.operators import _mcp_bridge
    _mcp_bridge.register_provider("jira", lambda sprint_id: {"sprint": ..., "issues": ...})
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from sendsprint.operators.base import TransportUnavailable

logger = logging.getLogger(__name__)

# A provider maps a source query (sprint_id / iteration_path / ...) to a raw
# payload dict mirroring that source's REST response shape.
Provider = Callable[..., dict[str, Any]]

_PROVIDERS: dict[str, Provider] = {}


class MCPProviderUnavailable(TransportUnavailable):
    """Raised when no MCP provider is registered for the requested source."""


def register_provider(source: str, provider: Provider) -> None:
    """Register the host's MCP fetcher for ``source`` (jira/azuredevops/github)."""
    _PROVIDERS[source.lower()] = provider
    logger.info("[mcp] registered provider for %s", source)


def unregister_provider(source: str) -> None:
    """Remove a previously registered provider (no-op if absent)."""
    _PROVIDERS.pop(source.lower(), None)


def clear_providers() -> None:
    """Drop every registered provider. Mainly for tests."""
    _PROVIDERS.clear()


def has_provider(source: str) -> bool:
    """True when a provider is registered for ``source``."""
    return source.lower() in _PROVIDERS


def fetch(source: str, **query: Any) -> dict[str, Any]:
    """Return the raw MCP payload for ``source``.

    Raises :class:`MCPProviderUnavailable` when no provider is registered so the
    operator's ``auto`` transport falls through to its REST API path.
    """
    provider = _PROVIDERS.get(source.lower())
    if provider is None:
        raise MCPProviderUnavailable(f"no MCP provider registered for {source!r}")
    payload = provider(**query)
    if not isinstance(payload, dict):
        raise MCPProviderUnavailable(
            f"{source} MCP provider returned {type(payload).__name__}, expected dict"
        )
    return payload
