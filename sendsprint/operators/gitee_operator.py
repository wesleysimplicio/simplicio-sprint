"""GiteeOperator — reads a sprint (milestone) from Gitee.

Scaffold only: Gitee mirrors the GitHub issue model closely (REST v5). Auth
pre-check is wired; the transport bodies raise ``TransportUnavailable``
until the GITEE-INGEST sub-issue lands.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sendsprint.models import Sprint
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)


class GiteeOperator(BaseOperator):
    """Reads a Gitee repo milestone and returns a :class:`Sprint`.

    Transports:
      - mcp: Gitee MCP (when ``MCP_GITEE_AVAILABLE=1``).
      - api: Gitee REST API v5 (``GITEE_TOKEN`` + ``GITEE_OWNER`` + ``GITEE_REPO``).
      - playwright: scrapes the issues page via the shared CDP browser.
    """

    source = "gitee"

    def __init__(
        self,
        token: str | None = None,
        owner: str | None = None,
        repo: str | None = None,
        base_url: str | None = None,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.token: str = token or os.getenv("GITEE_TOKEN") or ""
        self.owner: str = owner or os.getenv("GITEE_OWNER") or ""
        self.repo: str = repo or os.getenv("GITEE_REPO") or ""
        self.base_url: str = (
            base_url or os.getenv("GITEE_BASE_URL") or "https://gitee.com/api/v5"
        ).rstrip("/")

    def _api_available(self) -> bool:
        return bool(self.token and self.owner and self.repo)

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable("gitee MCP transport is not yet wired (GITEE-INGEST sub-issue)")

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable(
                "GITEE_TOKEN, GITEE_OWNER, and GITEE_REPO are required for the API transport"
            )
        raise TransportUnavailable("gitee API transport is not yet wired (GITEE-INGEST sub-issue)")

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "gitee Playwright transport is not yet wired (GITEE-INGEST sub-issue)"
        )
