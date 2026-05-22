"""ClickUpOperator — reads a sprint (list) from ClickUp.

Scaffold only. ClickUp tasks live inside Lists; a "sprint" is typically a
List filtered by a sprint folder + status. The CLICKUP-INGEST sub-issue will
wire the v2 REST client.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sendsprint.models import Sprint
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)


class ClickUpOperator(BaseOperator):
    """Reads a ClickUp list and returns a :class:`Sprint`.

    Transports:
      - mcp: ClickUp MCP server (when ``MCP_CLICKUP_AVAILABLE=1``).
      - api: ClickUp REST v2 (``CLICKUP_TOKEN`` + ``CLICKUP_LIST_ID`` OR
        ``CLICKUP_FOLDER_ID`` for sprint folders).
      - playwright: scrapes the board view via the shared CDP browser.
    """

    source = "clickup"

    def __init__(
        self,
        token: str | None = None,
        list_id: str | None = None,
        folder_id: str | None = None,
        team_id: str | None = None,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.token: str = token or os.getenv("CLICKUP_TOKEN") or ""
        self.list_id: str = list_id or os.getenv("CLICKUP_LIST_ID") or ""
        self.folder_id: str = folder_id or os.getenv("CLICKUP_FOLDER_ID") or ""
        self.team_id: str = team_id or os.getenv("CLICKUP_TEAM_ID") or ""

    def _api_available(self) -> bool:
        return bool(self.token and (self.list_id or self.folder_id))

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "clickup MCP transport is not yet wired (CLICKUP-INGEST sub-issue)"
        )

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable(
                "CLICKUP_TOKEN and either CLICKUP_LIST_ID or CLICKUP_FOLDER_ID are required"
            )
        raise TransportUnavailable(
            "clickup REST transport is not yet wired (CLICKUP-INGEST sub-issue)"
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "clickup Playwright transport is not yet wired (CLICKUP-INGEST sub-issue)"
        )
