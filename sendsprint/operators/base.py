"""Base operator abstraction shared by Jira / Azure DevOps / GitHub Issues."""

from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Literal

import httpx

from sendsprint.models import Sprint

logger = logging.getLogger(__name__)

Transport = Literal["mcp", "api", "auto"]


class TransportUnavailable(RuntimeError):
    """Raised when a requested transport cannot be initialised."""


class BaseOperator(ABC):
    """Common contract for sprint-reading operators.

    Concrete operators implement two transports — MCP (live tenant state) and
    REST API — and :meth:`read_sprint` picks one based on ``transport`` (or
    auto-detects, preferring MCP then API).
    """

    source: str = "generic"

    def __init__(self, transport: Transport = "auto", **kwargs: Any) -> None:
        self.transport: Transport = transport
        self._kwargs = kwargs

    def read_sprint(self, **kwargs: Any) -> Sprint:
        if self.transport != "auto":
            logger.info("[%s] reading sprint via %s", self.source, self.transport)
            return self._read_with_transport(self.transport, **kwargs)

        errors: list[str] = []
        for transport in self._available_transports():
            try:
                logger.info("[%s] reading sprint via %s", self.source, transport)
                return self._read_with_transport(transport, **kwargs)
            except (TransportUnavailable, httpx.HTTPError, RuntimeError, ValueError) as exc:
                errors.append(f"{transport}: {exc}")
                logger.warning("[%s] %s transport failed: %s", self.source, transport, exc)
                continue
        detail = "; ".join(errors) if errors else "no transports available"
        raise TransportUnavailable(f"{self.source} could not read sprint: {detail}")

    def _available_transports(self) -> list[Literal["mcp", "api"]]:
        transports: list[Literal["mcp", "api"]] = []
        if self._mcp_available():
            transports.append("mcp")
        transports.append("api")
        return transports

    def _read_with_transport(self, transport: str, **kwargs: Any) -> Sprint:
        if transport == "mcp":
            return self._read_via_mcp(**kwargs)
        return self._read_via_api(**kwargs)

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
