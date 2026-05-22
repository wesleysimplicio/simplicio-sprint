"""HermesOperator — reads a sprint (board) from the Hermes kanban.

Scaffold only. Hermes is the Higgsfield agent host; this operator targets a
hypothetical "Hermes kanban" board surface that exposes work items to
SendSprint. Auth + endpoint shape are placeholders until the HERMES-INGEST
sub-issue confirms the public API.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sendsprint.models import Sprint
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)


class HermesOperator(BaseOperator):
    """Reads a Hermes kanban board and returns a :class:`Sprint`.

    Transports:
      - mcp: Hermes MCP server (when ``MCP_HERMES_AVAILABLE=1``).
      - api: Hermes REST API at ``HERMES_BASE_URL`` with ``HERMES_TOKEN``
        and a target ``HERMES_BOARD_ID``.
      - playwright: scrapes the Hermes kanban UI via the shared CDP browser.

    The exact endpoints + payload shape are placeholders. The HERMES-INGEST
    sub-issue will confirm them against the real product once available.
    """

    source = "hermes"

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        board_id: str | None = None,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.token: str = token or os.getenv("HERMES_TOKEN") or ""
        self.base_url: str = (base_url or os.getenv("HERMES_BASE_URL") or "").rstrip("/")
        self.board_id: str = board_id or os.getenv("HERMES_BOARD_ID") or ""

    def _api_available(self) -> bool:
        return bool(self.token and self.base_url and self.board_id)

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "hermes MCP transport is not yet wired (HERMES-INGEST sub-issue)"
        )

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable(
                "HERMES_TOKEN, HERMES_BASE_URL, and HERMES_BOARD_ID are required"
            )
        raise TransportUnavailable(
            "hermes REST transport is not yet wired (HERMES-INGEST sub-issue)"
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "hermes Playwright transport is not yet wired (HERMES-INGEST sub-issue)"
        )
