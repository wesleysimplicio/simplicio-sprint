"""Go worker specification and proxy.

Defines the JSON protocol that a Go worker daemon speaks over
stdio / localhost / named pipe, plus a proxy class that wraps
subprocess calls to the Go binary when it is available.

The Go binary is OPTIONAL — Python always falls back to PythonWorker.
"""

from __future__ import annotations

import json
import logging
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.contracts import (
    CommandType,
    EventType,
    RunCommand,
    RunEvent,
    WorkerCapability,
    WorkerStack,
    to_json,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol specification (documentation + JSON schema)
# ---------------------------------------------------------------------------

GO_WORKER_BINARY = "sendsprint-worker"

#: JSON schema for messages sent TO the Go worker (request envelope).
REQUEST_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoWorkerRequest",
    "description": "JSON envelope sent from Python control plane to Go worker over stdio/pipe.",
    "type": "object",
    "required": ["action", "version"],
    "properties": {
        "action": {
            "type": "string",
            "enum": ["queue", "start", "cancel", "heartbeat", "status", "log_tail", "shutdown"],
            "description": "Operation to perform.",
        },
        "version": {
            "type": "string",
            "description": "Contract version (e.g. '1.0.0').",
        },
        "run_id": {
            "type": "string",
            "description": "Task identifier (required for queue/cancel/status).",
        },
        "command": {
            "type": "object",
            "description": "Full RunCommand payload (required for 'queue' action).",
        },
        "params": {
            "type": "object",
            "description": 'Action-specific parameters (e.g. {"n": 50} for log_tail).',
        },
    },
}

#: JSON schema for messages received FROM the Go worker (response envelope).
RESPONSE_SCHEMA: dict[str, Any] = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "GoWorkerResponse",
    "description": "JSON envelope sent from Go worker back to Python control plane.",
    "type": "object",
    "required": ["ok"],
    "properties": {
        "ok": {"type": "boolean"},
        "event": {
            "type": "object",
            "description": "RunEvent payload when the action produces an event.",
        },
        "data": {
            "type": "object",
            "description": "Arbitrary response data (status snapshot, log lines, etc.).",
        },
        "error": {
            "type": "string",
            "description": "Error message when ok=false.",
        },
    },
}


class GoWorkerSpec(BaseModel):
    """Documents the Go worker JSON protocol.

    This model is informational — it describes what a future Go binary
    must implement. Python never runs Go code directly; it speaks JSON
    over stdio/pipe to a subprocess.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    binary_name: str = GO_WORKER_BINARY
    transport: str = Field(
        default="stdio",
        description="Communication channel: 'stdio' | 'localhost:<port>' | 'pipe:<name>'",
    )
    request_schema: dict[str, Any] = Field(default_factory=lambda: REQUEST_SCHEMA)
    response_schema: dict[str, Any] = Field(default_factory=lambda: RESPONSE_SCHEMA)
    supported_actions: list[str] = Field(
        default_factory=lambda: [
            "queue",
            "start",
            "cancel",
            "heartbeat",
            "status",
            "log_tail",
            "shutdown",
        ]
    )
    notes: str = (
        "The Go worker is an optional accelerator. "
        "Python PythonWorker is the always-available fallback. "
        "Protocol is newline-delimited JSON (NDJSON) over stdio."
    )


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


def detect_go_worker() -> bool:
    """Return True if the Go worker binary is on PATH and executable."""
    return shutil.which(GO_WORKER_BINARY) is not None


# ---------------------------------------------------------------------------
# Proxy
# ---------------------------------------------------------------------------


@dataclass
class GoWorkerProxy:
    """Wraps subprocess calls to the Go worker binary.

    Speaks the JSON protocol defined by GoWorkerSpec over stdio.
    Each call spawns a short-lived subprocess (request-response style).
    A future version may keep a long-lived process with streaming.
    """

    binary: str = GO_WORKER_BINARY
    timeout_s: int = 30
    worker_id: str = "go-worker"

    def available(self) -> bool:
        """Check if the Go binary is reachable."""
        return shutil.which(self.binary) is not None

    def capability(self) -> WorkerCapability:
        """Return capability descriptor for the Go worker."""
        return WorkerCapability(
            worker_id=self.worker_id,
            stack=WorkerStack.go,
            supported_commands=list(CommandType),
            max_concurrency=16,
            metadata={"binary": self.binary, "transport": "stdio"},
        )

    def send(
        self,
        action: str,
        *,
        run_id: str | None = None,
        command: RunCommand | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Send a request to the Go worker and return the parsed response.

        Raises RuntimeError if the binary is missing or returns an error.
        """
        if not self.available():
            raise RuntimeError(f"{self.binary} not found on PATH")

        request: dict[str, Any] = {
            "action": action,
            "version": "1.0.0",
        }
        if run_id:
            request["run_id"] = run_id
        if command:
            request["command"] = json.loads(to_json(command))
        if params:
            request["params"] = params

        payload = json.dumps(request) + "\n"

        try:
            result = subprocess.run(
                [self.binary],
                input=payload,
                capture_output=True,
                text=True,
                timeout=self.timeout_s,
            )
        except FileNotFoundError:
            raise RuntimeError(f"{self.binary} not found") from None
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{self.binary} timed out after {self.timeout_s}s") from None

        if result.returncode != 0:
            raise RuntimeError(f"{self.binary} exited {result.returncode}: {result.stderr.strip()}")

        try:
            response = json.loads(result.stdout.strip())
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid JSON from {self.binary}: {exc}") from exc

        if not response.get("ok", False):
            raise RuntimeError(f"go worker error: {response.get('error', 'unknown')}")

        return response

    def queue(self, command: RunCommand) -> str:
        """Queue a command on the Go worker. Returns run_id."""
        self.send("queue", run_id=command.run_id, command=command)
        return command.run_id

    def cancel(self, run_id: str) -> RunEvent:
        """Cancel a task on the Go worker."""
        resp = self.send("cancel", run_id=run_id)
        event_data = resp.get("event", {})
        return RunEvent(
            event_type=EventType.cancelled,
            run_id=run_id,
            source_stack=WorkerStack.go,
            data=event_data,
        )

    def heartbeat(self) -> dict[str, Any]:
        """Get heartbeat from Go worker."""
        resp = self.send("heartbeat")
        return resp.get("data", {})

    def status(self, run_id: str | None = None) -> dict[str, Any]:
        """Get status snapshot from Go worker."""
        resp = self.send("status", run_id=run_id)
        return resp.get("data", {})

    def log_tail(self, n: int = 50) -> list[str]:
        """Get last n log lines from Go worker."""
        resp = self.send("log_tail", params={"n": n})
        return resp.get("data", {}).get("lines", [])
