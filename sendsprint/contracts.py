"""Typed control-plane contracts for the SendSprint runtime split.

Python owns: CLI, API server, workspace loader, planning, quality gates,
operational memory, and PR publishing.  External workers (Go, Rust, Node)
implement the RunCommand/RunEvent protocol defined here.

See: https://github.com/wesleysimplicio/SendSprint/issues/106
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Contract version — bump on breaking changes to the wire format.
# ---------------------------------------------------------------------------
CONTRACT_VERSION = "1.0.0"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class CommandType(StrEnum):
    """Commands the control plane can send to external workers."""

    plan = "plan"
    implement = "implement"
    validate = "validate"
    test = "test"
    lint = "lint"
    build = "build"
    deploy = "deploy"
    rollback = "rollback"
    cancel = "cancel"
    resume = "resume"
    inspect = "inspect"


class EventType(StrEnum):
    """Events workers emit back to the control plane."""

    started = "started"
    progress = "progress"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"
    blocked = "blocked"
    heartbeat = "heartbeat"
    artifact = "artifact"
    log = "log"


class WorkerStack(StrEnum):
    """Supported worker runtime stacks."""

    python = "python"
    go = "go"
    rust = "rust"
    node = "node"


# ---------------------------------------------------------------------------
# Wire models
# ---------------------------------------------------------------------------
class RunCommand(BaseModel):
    """Command sent from Python control plane to an external worker."""

    model_config = ConfigDict(extra="allow")

    version: str = CONTRACT_VERSION
    command_type: CommandType
    run_id: str
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    timeout_s: int = 300
    correlation_id: str | None = None


class RunEvent(BaseModel):
    """Event emitted by a worker back to the control plane."""

    model_config = ConfigDict(extra="allow")

    version: str = CONTRACT_VERSION
    event_type: EventType
    run_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_stack: WorkerStack = WorkerStack.python
    correlation_id: str | None = None
    error: str | None = None


class WorkerCapability(BaseModel):
    """Describes what an external worker can do."""

    model_config = ConfigDict(extra="allow")

    worker_id: str
    stack: WorkerStack
    supported_commands: list[CommandType] = Field(default_factory=list)
    max_concurrency: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Python-owned API surface (documentation + runtime guard)
# ---------------------------------------------------------------------------
class ControlPlaneContract:
    """Documents which APIs remain Python-owned.

    External workers MUST NOT re-implement these; they call Python over
    the RunCommand/RunEvent protocol instead.
    """

    PYTHON_OWNED_APIS: tuple[str, ...] = (
        "cli",
        "api_server",
        "workspace_loader",
        "planning",
        "quality_gates",
        "operational_memory",
        "pr_publishing",
    )

    WORKER_LIFECYCLE: tuple[str, ...] = (
        "start",
        "monitor",
        "cancel",
        "resume",
    )

    @classmethod
    def is_python_owned(cls, api_name: str) -> bool:
        return api_name in cls.PYTHON_OWNED_APIS

    @classmethod
    def lifecycle_commands(cls) -> list[CommandType]:
        """CommandTypes that map to worker lifecycle management."""
        return [CommandType.cancel, CommandType.resume, CommandType.inspect]


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------
def to_json(model: BaseModel) -> str:
    """Serialize a contract model to JSON with version stamp."""
    return model.model_dump_json()


def from_json(raw: str | bytes, model_cls: type[BaseModel]) -> BaseModel:
    """Deserialize JSON into a contract model.

    Handles backwards compatibility:
    - Missing ``version`` defaults to CONTRACT_VERSION.
    - Missing optional fields use Pydantic defaults.
    - Unknown extra fields are preserved (``extra="allow"``).
    """
    data: dict[str, Any] = json.loads(raw)
    if "version" not in data:
        data["version"] = CONTRACT_VERSION
    return model_cls.model_validate(data)
