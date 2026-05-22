"""LinearOperator — reads a sprint (cycle) from Linear.

Scaffold only. Linear uses GraphQL exclusively for its public API; the real
client will live in the LINEAR-INGEST sub-issue. Auth pre-check is wired so
the dispatcher can short-circuit before any GraphQL roundtrip.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sendsprint.models import Sprint
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)


class LinearOperator(BaseOperator):
    """Reads a Linear team cycle and returns a :class:`Sprint`.

    Transports:
      - mcp: Linear MCP server (when ``MCP_LINEAR_AVAILABLE=1``).
      - api: Linear GraphQL endpoint at ``https://api.linear.app/graphql``
        with ``LINEAR_API_KEY`` and a target ``LINEAR_TEAM_ID``.
      - playwright: scrapes the cycle view via the shared CDP browser.
    """

    source = "linear"

    def __init__(
        self,
        api_key: str | None = None,
        team_id: str | None = None,
        cycle_id: str | None = None,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.api_key: str = api_key or os.getenv("LINEAR_API_KEY") or ""
        self.team_id: str = team_id or os.getenv("LINEAR_TEAM_ID") or ""
        self.cycle_id: str = cycle_id or os.getenv("LINEAR_CYCLE_ID") or ""

    def _api_available(self) -> bool:
        return bool(self.api_key and self.team_id)

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "linear MCP transport is not yet wired (LINEAR-INGEST sub-issue)"
        )

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable(
                "LINEAR_API_KEY and LINEAR_TEAM_ID are required for the GraphQL transport"
            )
        raise TransportUnavailable(
            "linear GraphQL transport is not yet wired (LINEAR-INGEST sub-issue)"
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "linear Playwright transport is not yet wired (LINEAR-INGEST sub-issue)"
        )
