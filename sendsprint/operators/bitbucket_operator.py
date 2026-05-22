"""BitbucketOperator — reads a sprint (issues query) from Bitbucket.

Scaffold only: auth pre-check is wired, transport bodies raise
``TransportUnavailable("not yet wired")`` until the BITBUCKET-INGEST sub-issue
lands. Bitbucket Cloud uses workspace + repo addressing; Bitbucket Server has
a different REST surface (handled by an optional ``server`` flag here).
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sendsprint.models import Sprint
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)


class BitbucketOperator(BaseOperator):
    """Reads issues from a Bitbucket workspace/repo and returns a :class:`Sprint`.

    Transports:
      - mcp: Bitbucket MCP (when ``MCP_BITBUCKET_AVAILABLE=1``).
      - api: Bitbucket Cloud REST v2 OR Bitbucket Server REST v1 (selected by
        ``server`` flag), authenticated via app password or PAT.
      - playwright: scrapes the issues view through the shared CDP browser.
    """

    source = "bitbucket"

    def __init__(
        self,
        workspace: str | None = None,
        repo: str | None = None,
        username: str | None = None,
        app_password: str | None = None,
        base_url: str | None = None,
        server: bool = False,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.workspace: str = workspace or os.getenv("BITBUCKET_WORKSPACE") or ""
        self.repo: str = repo or os.getenv("BITBUCKET_REPO") or ""
        self.username: str = username or os.getenv("BITBUCKET_USERNAME") or ""
        self.app_password: str = app_password or os.getenv("BITBUCKET_APP_PASSWORD") or ""
        default_base = "https://api.bitbucket.org/2.0" if not server else ""
        self.base_url: str = (base_url or os.getenv("BITBUCKET_BASE_URL") or default_base).rstrip(
            "/"
        )
        self.server = server

    def _api_available(self) -> bool:
        return bool(self.workspace and self.repo and self.username and self.app_password)

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "bitbucket MCP transport is not yet wired (BITBUCKET-INGEST sub-issue)"
        )

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable(
                "BITBUCKET_WORKSPACE / REPO / USERNAME / APP_PASSWORD are required"
            )
        raise TransportUnavailable(
            "bitbucket API transport is not yet wired (BITBUCKET-INGEST sub-issue)"
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "bitbucket Playwright transport is not yet wired (BITBUCKET-INGEST sub-issue)"
        )
