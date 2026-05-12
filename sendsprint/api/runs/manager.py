"""In-memory run registry + threaded executor for the web API.

We can't run SprintFlow inside FastAPI's event loop (it's sync + does heavy
subprocess work), so each run gets a worker thread. The thread publishes
StepReports + evidence paths into the events queue (events.publish_threadsafe).
"""

from __future__ import annotations

import threading
import uuid
from datetime import datetime
from pathlib import Path

from sendsprint.api.runs import events
from sendsprint.api.schemas import RunStatus, StartRunRequest

_runs: dict[str, RunStatus] = {}
_threads: dict[str, threading.Thread] = {}


def list_runs() -> list[RunStatus]:
    return list(_runs.values())


def get_run(run_id: str) -> RunStatus | None:
    return _runs.get(run_id)


def start_run(req: StartRunRequest) -> RunStatus:
    run_id = uuid.uuid4().hex[:12]
    status = RunStatus(
        run_id=run_id,
        state="queued",
        sprint_id=req.sprint_id,
        provider=req.provider,
        started_at=datetime.utcnow().isoformat(),
    )
    _runs[run_id] = status
    t = threading.Thread(
        target=_worker,
        args=(run_id, req),
        name=f"run-{run_id}",
        daemon=True,
    )
    _threads[run_id] = t
    t.start()
    return status


def _worker(run_id: str, req: StartRunRequest) -> None:
    """Thread entry point. Runs SprintFlow with publishing hooks."""
    status = _runs[run_id]
    status.state = "running"
    events.publish_threadsafe(
        run_id, {"type": "log", "message": f"starting run for sprint {req.sprint_id}"}
    )

    try:
        from sendsprint.api.runs.bridge import run_with_events

        report = run_with_events(run_id, req)
        status.state = "failed" if report.get("failed") else "done"
        status.failed = bool(report.get("failed"))
        status.summary = report.get("summary")
        status.pr_url = report.get("pr_url")
        status.finished_at = datetime.utcnow().isoformat()
        status.last_step = report.get("last_step")
        events.publish_threadsafe(
            run_id,
            {
                "type": "done",
                "failed": status.failed,
                "summary": status.summary,
                "pr_url": status.pr_url,
            },
        )
    except Exception as exc:
        status.state = "failed"
        status.failed = True
        status.finished_at = datetime.utcnow().isoformat()
        events.publish_threadsafe(run_id, {"type": "error", "message": str(exc)})


def evidence_root(run_id: str) -> Path:
    """Where evidence files for this run live (best-effort discovery)."""
    return Path.cwd() / "evidence" / run_id
