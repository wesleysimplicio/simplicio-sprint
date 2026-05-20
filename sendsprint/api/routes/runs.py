"""Run endpoints: start a sprint run + list status + SSE event stream."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from sendsprint.api.runs import events, manager
from sendsprint.api.runs.agent_status import build_agent_snapshot
from sendsprint.api.runs.status_answer import render_status_answer
from sendsprint.api.schemas import (
    AgentRunSnapshot,
    AgentStatusAnswer,
    RunStatus,
    StartRunRequest,
    StartRunResponse,
)

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=StartRunResponse)
def start_run(req: StartRunRequest) -> StartRunResponse:
    status = manager.start_run(req)
    return StartRunResponse(run_id=status.run_id)


@router.get("", response_model=list[RunStatus])
def list_runs() -> list[RunStatus]:
    return manager.list_runs()


@router.get("/{run_id}", response_model=RunStatus)
def get_run(run_id: str) -> RunStatus:
    s = manager.get_run(run_id)
    if s is None:
        raise HTTPException(status_code=404, detail="run not found")
    return s


@router.get("/{run_id}/agent-status", response_model=AgentRunSnapshot)
def get_agent_status(run_id: str) -> AgentRunSnapshot:
    snapshot = build_agent_snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return snapshot


@router.get("/{run_id}/status-answer", response_model=AgentStatusAnswer)
def get_status_answer(
    run_id: str,
    adapter: str = "generic",
    question: str | None = None,
) -> AgentStatusAnswer:
    snapshot = build_agent_snapshot(run_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="run not found")
    return render_status_answer(snapshot, adapter=adapter, question=question)


@router.get("/{run_id}/dashboard", response_model=dict)
def get_run_dashboard(run_id: str) -> dict:
    """Return a local dashboard snapshot backed by run status and evidence files."""
    status = manager.get_run(run_id)
    if status is None:
        raise HTTPException(status_code=404, detail="run not found")
    evidence_dir = manager.evidence_root(run_id)
    evidence = [
        {"name": path.name, "path": str(path)}
        for path in sorted(evidence_dir.glob("*"))
        if path.is_file()
    ]
    return {
        "run": status.model_dump(),
        "evidence": evidence,
        "summary": status.summary,
        "pr_url": status.pr_url,
        "blockers": [] if not status.failed else [status.summary or "run failed"],
    }


@router.get("/{run_id}/events")
async def run_events(run_id: str) -> StreamingResponse:
    """Server-Sent Events stream — one JSON event per `data:` line."""
    if manager.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")

    async def gen():
        yield 'event: hello\ndata: {"run_id":"' + run_id + '"}\n\n'
        while True:
            try:
                event = await asyncio.wait_for(events.drain(run_id), timeout=30.0)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            payload = json.dumps({**event, "run_id": run_id})
            yield f"data: {payload}\n\n"
            if event.get("type") in {"done", "error"}:
                events.close(run_id)
                break

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/{run_id}/events/stream")
async def run_event_stream(run_id: str) -> StreamingResponse:
    """SSE stream for live dashboard updates — richer than /events.

    Emits ``hello``, ``step``, ``log``, ``evidence``, ``done``, and ``error``
    frames.  Keepalive every 30 s.  Issue #103.
    """
    if manager.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail="run not found")

    async def _generate():
        yield f"event: hello\ndata: {json.dumps({'run_id': run_id})}\n\n"
        while True:
            try:
                event = await asyncio.wait_for(events.drain(run_id), timeout=30.0)
            except TimeoutError:
                yield ": keepalive\n\n"
                continue
            event_type = event.get("type", "message")
            payload = json.dumps({**event, "run_id": run_id})
            yield f"event: {event_type}\ndata: {payload}\n\n"
            if event_type in {"done", "error"}:
                events.close(run_id)
                break

    return StreamingResponse(_generate(), media_type="text/event-stream")


@router.get("/{run_id}/evidence/{name}")
def get_evidence(run_id: str, name: str) -> FileResponse:
    """Serve a captured evidence file (screenshot/log) for the web UI."""
    safe = os.path.basename(name)
    candidates = [
        Path("evidence") / run_id / safe,
        Path("evidence") / safe,
    ]
    for path in candidates:
        if path.is_file():
            return FileResponse(path)
    raise HTTPException(status_code=404, detail="evidence not found")
