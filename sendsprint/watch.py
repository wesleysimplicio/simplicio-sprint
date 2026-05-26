"""Unattended trigger: finish the cards assigned to me, without babysitting.

This is the piece that removes the human from the loop. A scheduled run (cron,
GitHub Action, or a Claude Code on the web scheduled trigger) calls
:meth:`Watcher.run_once`; a long-lived session calls :meth:`Watcher.loop`.
Either way it reads the sprint scoped to the operator (``--scope mine``),
delivers every card it hasn't delivered yet, and records the keys so the next
pass skips them.
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from pathlib import Path

from sendsprint.flow import SprintFlow
from sendsprint.models import RunReport

logger = logging.getLogger(__name__)


class Watcher:
    """Poll a source and deliver newly assigned cards through a SprintFlow."""

    def __init__(
        self,
        flow: SprintFlow,
        *,
        state_path: str | Path = ".sendsprint/runs/watch-state.json",
        interval_minutes: int = 15,
        max_per_cycle: int = 1,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.flow = flow
        self.state_path = Path(state_path)
        self.interval_minutes = interval_minutes
        self.max_per_cycle = max_per_cycle
        self._sleep = sleep

    def run_once(self, **read_kwargs: object) -> RunReport:
        """One pass: deliver up to ``max_per_cycle`` not-yet-delivered cards."""
        delivered = self._load_delivered()
        sprint = self.flow.operator.read_sprint(**read_kwargs)
        if self.flow.scope is not None:
            from sendsprint.scope import apply_scope

            sprint = apply_scope(sprint, self.flow.scope)

        pending = [i for i in sprint.items if i.key not in delivered][: self.max_per_cycle]
        report = RunReport(
            workspace=self.flow.target.name,
            sprint_name=sprint.name,
            sprint_id=sprint.id,
            scope_mode=(self.flow.scope.mode if self.flow.scope else "all"),
            user=(self.flow.scope.user_email if self.flow.scope else None),
        )
        for item in pending:
            outcome = self.flow.deliver_item(item)
            report.steps.extend(outcome.steps)
            if outcome.pr is not None:
                report.prs.append(outcome.pr)  # type: ignore[arg-type]
            delivered.add(item.key)
        self._save_delivered(delivered)
        report.failed = any(s.status == "failed" for s in report.steps)
        report.summary = f"watch cycle: delivered {len(pending)} card(s)"
        return report

    def loop(self, **read_kwargs: object) -> None:
        """Run forever, one cycle per ``interval_minutes``."""
        while True:
            try:
                report = self.run_once(**read_kwargs)
                logger.info("%s", report.summary)
            except Exception as exc:  # noqa: BLE001 - keep the watcher alive
                logger.error("watch cycle failed: %s", exc)
            self._sleep(self.interval_minutes * 60)

    def _load_delivered(self) -> set[str]:
        if not self.state_path.exists():
            return set()
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            return set(data.get("delivered", []))
        except (ValueError, OSError):
            return set()

    def _save_delivered(self, delivered: set[str]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps({"delivered": sorted(delivered)}, indent=2), encoding="utf-8"
        )
