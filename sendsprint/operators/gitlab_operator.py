"""GitLabOperator — reads a sprint (iteration / milestone) from GitLab.

Scaffold only: the auth pre-check is wired, the transport bodies raise
``TransportUnavailable("not yet wired")`` until the GITLAB-INGEST sub-issue
lands. See ``.specs/v2/cloud-dispatcher.md``.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sendsprint.models import Sprint
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)


class GitLabOperator(BaseOperator):
    """Reads a GitLab project iteration/milestone and returns a :class:`Sprint`.

    Transports:
      - mcp: GitLab MCP server (when ``MCP_GITLAB_AVAILABLE=1``).
      - api: GitLab REST API v4 (``GITLAB_BASE_URL`` + ``GITLAB_TOKEN`` + ``GITLAB_PROJECT``).
      - playwright: scrapes the GitLab issue board via the shared CDP browser.
    """

    source = "gitlab"

    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        project: str | None = None,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.token: str = token or os.getenv("GITLAB_TOKEN") or ""
        self.base_url: str = (
            base_url or os.getenv("GITLAB_BASE_URL") or "https://gitlab.com"
        ).rstrip("/")
        self.project: str = project or os.getenv("GITLAB_PROJECT") or ""

    def _api_available(self) -> bool:
        return bool(self.token and self.project)

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "gitlab MCP transport is not yet wired (GITLAB-INGEST sub-issue)"
        )

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable(
                "GITLAB_TOKEN and GITLAB_PROJECT are required for the API transport"
            )
        raise TransportUnavailable(
            "gitlab API transport is not yet wired (GITLAB-INGEST sub-issue)"
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "gitlab Playwright transport is not yet wired (GITLAB-INGEST sub-issue)"
        )
