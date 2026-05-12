"""Run endpoints: start a sprint run + list status + SSE event stream."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, StreamingResponse

from sendsprint.api.runs import events, manager
from sendsprint.api.schemas import RunStatus, StartRunRequest, StartRunResponse

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
