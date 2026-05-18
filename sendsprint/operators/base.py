"""Base operator abstraction shared by Jira / Azure DevOps."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Literal

from sendsprint.models import Sprint

logger = logging.getLogger(__name__)

Transport = Literal["mcp", "api", "playwright", "auto"]


class TransportUnavailable(RuntimeError):
    """Raised when a requested transport cannot be initialised."""


class BaseOperator(ABC):
    """Common contract for sprint-reading operators.

    Concrete operators implement three transports - MCP, REST API, Playwright -
    and read_sprint picks one based on transport (or auto-detects).
    """

    source: str = "generic"

    def __init__(self, transport: Transport = "auto", **kwargs: Any) -> None:
        self.transport: Transport = transport
        self._kwargs = kwargs

    def read_sprint(self, **kwargs: Any) -> Sprint:
        chosen = self._resolve_transport()
        logger.info("[%s] reading sprint via %s", self.source, chosen)
        if chosen == "mcp":
            return self._read_via_mcp(**kwargs)
        if chosen == "api":
            return self._read_via_api(**kwargs)
        return self._read_via_playwright(**kwargs)

    def _resolve_transport(self) -> Literal["mcp", "api", "playwright"]:
        if self.transport != "auto":
            return self.transport  # type: ignore[return-value]
        if self._mcp_available():
            return "mcp"
        if self._api_available():
            return "api"
        return "playwright"

    def _mcp_available(self) -> bool:
        return os.getenv(f"MCP_{self.source.upper()}_AVAILABLE") == "1"

    def update_status(self, item_key: str, status: str, comment: str | None = None) -> None:
        """Update the remote ticket status and optionally attach a comment."""
        raise TransportUnavailable(f"{self.source} status updates are not available")

    @abstractmethod
    def _api_available(self) -> bool: ...

    @abstractmethod
    def _read_via_mcp(self, **kwargs: Any) -> Sprint: ...

    @abstractmethod
    def _read_via_api(self, **kwargs: Any) -> Sprint: ...

    @abstractmethod
    def _read_via_playwright(self, **kwargs: Any) -> Sprint: ...
