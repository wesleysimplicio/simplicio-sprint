"""Multi-agent control-plane primitives."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.agent_registry import AgentRegistry, default_agent_registry

WorkerStatus = Literal["queued", "running", "blocked", "done", "failed"]


class WorkerAssignment(BaseModel):
    """One worker's ownership claim."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    worker_id: str
    provider_key: str = "codex"
    capability_key: str = "implement"
    issue_key: str
    repo: str
    branch: str
    worktree_path: str
    status: WorkerStatus = "queued"
    blocker: str | None = None
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def ownership_key(self) -> str:
        return f"{self.repo}::{self.issue_key}"


class ControlPlaneState(BaseModel):
    """Coordination state for multiple agents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    assignments: list[WorkerAssignment] = Field(default_factory=list)
    registry: AgentRegistry = Field(default_factory=default_agent_registry)

    def claim(self, assignment: WorkerAssignment) -> ControlPlaneState:
        """Return new state with an assignment if ownership is free."""
        self.registry.resolve(assignment.provider_key)
        self.registry.resolve(assignment.provider_key).capability(assignment.capability_key)
        for current in self.assignments:
            if current.status in {"done", "failed"}:
                continue
            if current.ownership_key == assignment.ownership_key:
                raise ValueError(
                    f"{assignment.ownership_key} already assigned to {current.worker_id}"
                )
            if current.worktree_path == assignment.worktree_path:
                raise ValueError(
                    f"worktree already assigned to {current.worker_id}: {current.worktree_path}"
                )
        return self.model_copy(update={"assignments": [*self.assignments, assignment]})

    def update(
        self,
        worker_id: str,
        status: WorkerStatus,
        blocker: str | None = None,
    ) -> ControlPlaneState:
        """Return new state with updated worker status."""
        updated: list[WorkerAssignment] = []
        found = False
        for current in self.assignments:
            if current.worker_id == worker_id:
                found = True
                updated.append(
                    current.model_copy(
                        update={
                            "status": status,
                            "blocker": blocker,
                            "updated_at": datetime.now(UTC),
                        }
                    )
                )
            else:
                updated.append(current)
        if not found:
            raise KeyError(worker_id)
        return self.model_copy(update={"assignments": updated})

    def active(self) -> list[WorkerAssignment]:
        """Return non-terminal workers."""
        return [item for item in self.assignments if item.status not in {"done", "failed"}]
