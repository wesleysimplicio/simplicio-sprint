"""SlackOperator — turns Slack messages tagged as tasks into a sprint.

Scaffold only. Slack is not a tracker, but teams routinely use it that way:
messages with a specific emoji (default ``:rocket:``) or in a designated
channel become work items. The SLACK-INGEST sub-issue will wire the bot
token + conversations API client.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from sendsprint.models import Sprint
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable

logger = logging.getLogger(__name__)


class SlackOperator(BaseOperator):
    """Reads tagged Slack messages and returns a :class:`Sprint`.

    Transports:
      - mcp: Slack MCP server (when ``MCP_SLACK_AVAILABLE=1``).
      - api: Slack Web API (``SLACK_BOT_TOKEN`` + target ``SLACK_CHANNEL_ID``)
        filtering messages by ``SLACK_TASK_EMOJI`` (defaults to ``rocket``).
      - playwright: scrapes a Slack workspace view via the shared CDP browser
        (best-effort; primarily a developer fallback).
    """

    source = "slack"

    def __init__(
        self,
        bot_token: str | None = None,
        channel_id: str | None = None,
        task_emoji: str | None = None,
        transport: Transport = "auto",
        **kwargs: Any,
    ) -> None:
        super().__init__(transport=transport, **kwargs)
        self.bot_token: str = bot_token or os.getenv("SLACK_BOT_TOKEN") or ""
        self.channel_id: str = channel_id or os.getenv("SLACK_CHANNEL_ID") or ""
        self.task_emoji: str = task_emoji or os.getenv("SLACK_TASK_EMOJI") or "rocket"

    def _api_available(self) -> bool:
        return bool(self.bot_token and self.channel_id)

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable("slack MCP transport is not yet wired (SLACK-INGEST sub-issue)")

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        if not self._api_available():
            raise TransportUnavailable(
                "SLACK_BOT_TOKEN and SLACK_CHANNEL_ID are required for the Web API transport"
            )
        raise TransportUnavailable(
            "slack Web API transport is not yet wired (SLACK-INGEST sub-issue)"
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise TransportUnavailable(
            "slack Playwright transport is not yet wired (SLACK-INGEST sub-issue)"
        )
