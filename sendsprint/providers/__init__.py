"""Provider adapters for the SendSprint v2 dispatcher (cloud + local).

Each module wraps an execution surface behind the :class:`ProviderAdapter`
contract — vendor clouds (Claude / Codex / Cursor / Windsurf / Kiro),
GitHub Actions (Copilot), or local git-worktree loops driven by ``/ralph``
and ``/goal``. The router fans tasks out across whichever adapters declare
``dispatchable=True`` in their capabilities, in parallel, regardless of
mode. Air-gapped projects can run on local adapters only.

See ``.specs/v2/cloud-dispatcher.md`` for the full design.
"""

from sendsprint.providers.base import (
    DispatchMode,
    DispatchTicket,
    ProviderAdapter,
    ProviderAuthError,
    ProviderCapabilities,
    ProviderError,
    ProviderNoCloudError,
    ProviderNotDispatchableError,
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
from sendsprint.providers.local_goal import LocalGoalAdapter
from sendsprint.providers.local_ralph import LocalRalphAdapter
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
    "DispatchMode",
    "DispatchTicket",
    "KiroAdapter",
    "LocalGoalAdapter",
    "LocalRalphAdapter",
    "PRResult",
    "ProviderAdapter",
    "ProviderAuthError",
    "ProviderCapabilities",
    "ProviderEntry",
    "ProviderError",
    "ProviderNoCloudError",
    "ProviderNotDispatchableError",
    "ProviderRouter",
    "ProviderTimeoutError",
    "ProviderVendorBlockedError",
    "ProvidersConfig",
    "RunStatus",
    "WindsurfAdapter",
    "build_adapters",
    "load_config",
]
