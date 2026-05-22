"""TrelloOperator — reads a sprint (board / list) from Trello.

Scaffold only. Trello's "sprint" maps to a board (or a specific List inside
a board); the TRELLO-INGEST sub-issue will wire the REST client with
key+token auth.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sendsprint.models import Sprint
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)


class TrelloOperator(BaseOperator):
    """Reads a Trello board (or list) and returns a :class:`Sprint`.

    Transports:
      - mcp: Trello MCP server (when ``MCP_TRELLO_AVAILABLE=1``).
      - api: Trello REST API 1 with ``TRELLO_API_KEY`` + ``TRELLO_API_TOKEN``
        and a target ``TRELLO_BOARD_ID`` (or ``TRELLO_LIST_ID``).
      - playwright: scrapes the board UI via the shared CDP browser.
    """

    source = "trello"

    def __init__(
        self,
        api_key: str | None = None,
        api_token: str | None = None,
        board_id: str | None = None,
        list_id: str | None = None,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.api_key: str = api_key or os.getenv("TRELLO_API_KEY") or ""
        self.api_token: str = api_token or os.getenv("TRELLO_API_TOKEN") or ""
        self.board_id: str = board_id or os.getenv("TRELLO_BOARD_ID") or ""
        self.list_id: str = list_id or os.getenv("TRELLO_LIST_ID") or ""

    def _api_available(self) -> bool:
        return bool(self.api_key and self.api_token and (self.board_id or self.list_id))

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "trello MCP transport is not yet wired (TRELLO-INGEST sub-issue)"
        )

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable(
                "TRELLO_API_KEY, TRELLO_API_TOKEN, and a board or list id are required"
            )
        raise TransportUnavailable(
            "trello REST transport is not yet wired (TRELLO-INGEST sub-issue)"
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "trello Playwright transport is not yet wired (TRELLO-INGEST sub-issue)"
        )
