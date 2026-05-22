"""Registry that turns ``providers.yml`` into a list of :class:`ProviderAdapter`.

The config file lives at the repo root by default. It selects which adapters
the router should consider, in which priority order, and how aggressive the
parallelism should be. Cloud-friendly projects keep the vendor adapters;
air-gapped or non-GitHub projects can run on ``local-ralph`` and ``local-goal``
alone.

Example ``providers.yml`` (mixed)::

    max_parallel: 3
    poll_interval_s: 10
    timeout_s: 1800
    providers:
      - name: claude
      - name: codex
      - name: copilot
      - name: local-ralph
      - name: local-goal
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from sendsprint.providers.base import ProviderAdapter
from sendsprint.providers.claude import ClaudeAdapter
from sendsprint.providers.codex import CodexAdapter
from sendsprint.providers.copilot import CopilotAdapter
from sendsprint.providers.cursor import CursorAdapter
from sendsprint.providers.kiro import KiroAdapter
from sendsprint.providers.local_goal import LocalGoalAdapter
from sendsprint.providers.local_ralph import LocalRalphAdapter
from sendsprint.providers.windsurf import WindsurfAdapter

ADAPTER_CLASSES: dict[str, type[ProviderAdapter]] = {
    "claude": ClaudeAdapter,
    "codex": CodexAdapter,
    "copilot": CopilotAdapter,
    "cursor": CursorAdapter,
    "windsurf": WindsurfAdapter,
    "kiro": KiroAdapter,
    "local-ralph": LocalRalphAdapter,
    "local-goal": LocalGoalAdapter,
}


class ProviderEntry(BaseModel):
    name: str
    options: dict[str, Any] = Field(default_factory=dict)


class ProvidersConfig(BaseModel):
    max_parallel: int = 3
    poll_interval_s: float = 10.0
    timeout_s: float = 1800.0
    providers: list[ProviderEntry] = Field(default_factory=list)


def load_config(path: str | Path = "providers.yml") -> ProvidersConfig:
    """Parse ``providers.yml`` (or any path) into a validated :class:`ProvidersConfig`."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    return ProvidersConfig.model_validate(data)


def build_adapters(config: ProvidersConfig) -> list[ProviderAdapter]:
    """Instantiate every adapter declared in ``config.providers``.

    Unknown provider names are surfaced with a ``ValueError`` rather than
    silently dropped — that makes a typo in ``providers.yml`` obvious.
    """
    adapters: list[ProviderAdapter] = []
    for entry in config.providers:
        cls = ADAPTER_CLASSES.get(entry.name)
        if cls is None:
            raise ValueError(
                f"unknown provider '{entry.name}' in config; "
                f"valid choices: {sorted(ADAPTER_CLASSES)}"
            )
        adapters.append(cls(**entry.options))
    return adapters
