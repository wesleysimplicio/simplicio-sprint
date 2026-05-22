"""Cloud-first provider adapters for the SendSprint v2 dispatcher.

Each module in this package wraps a coding-agent vendor cloud behind the
:class:`ProviderAdapter` contract. The router fans tasks out across the
adapters in parallel, polls until each run is done, and collects the
resulting PRs.

See ``.specs/v2/cloud-dispatcher.md`` for the full design.
"""

from sendsprint.providers.base import (
    DispatchTicket,
    ProviderAdapter,
    ProviderAuthError,
    ProviderCapabilities,
    ProviderError,
    ProviderNoCloudError,
    ProviderTimeoutError,
    ProviderVendorBlockedError,
    PRResult,
    RunStatus,
)
from sendsprint.providers.claude import ClaudeAdapter
from sendsprint.providers.codex import CodexAdapter
from sendsprint.providers.copilot import CopilotAdapter
from sendsprint.providers.cursor import CursorAdapter
from sendsprint.providers.kiro import KiroAdapter
from sendsprint.providers.registry import (
    ADAPTER_CLASSES,
    ProviderEntry,
    ProvidersConfig,
    build_adapters,
    load_config,
)
from sendsprint.providers.router import ProviderRouter
from sendsprint.providers.windsurf import WindsurfAdapter

__all__ = [
    "ADAPTER_CLASSES",
    "ClaudeAdapter",
    "CodexAdapter",
    "CopilotAdapter",
    "CursorAdapter",
    "DispatchTicket",
    "KiroAdapter",
    "PRResult",
    "ProviderAdapter",
    "ProviderAuthError",
    "ProviderCapabilities",
    "ProviderEntry",
    "ProviderError",
    "ProviderNoCloudError",
    "ProviderRouter",
    "ProviderTimeoutError",
    "ProviderVendorBlockedError",
    "ProvidersConfig",
    "RunStatus",
    "WindsurfAdapter",
    "build_adapters",
    "load_config",
]
