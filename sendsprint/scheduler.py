"""Parallel issue scheduler primitives."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.agent_registry import AgentRegistry, default_agent_registry

TaskStatus = Literal["pending", "running", "blocked", "failed", "completed"]


class ScheduledTask(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_key: str
    repo: str
    capability_key: str = "implement"
    status: TaskStatus = "pending"
    provider_key: str | None = None
    confidence: float = 0.5


class ParallelIssueScheduler(BaseModel):
    model_config = ConfigDict(extra="forbid")

    concurrency_limit: int = 2
    registry: AgentRegistry = Field(default_factory=default_agent_registry)
    tasks: list[ScheduledTask] = Field(default_factory=list)

    def enqueue(self, task: ScheduledTask) -> None:
        self.tasks.append(task)

    def dispatchable(self) -> list[ScheduledTask]:
        running = sum(1 for task in self.tasks if task.status == "running")
        capacity = max(0, self.concurrency_limit - running)
        ready = [task for task in self.tasks if task.status == "pending"]
        return ready[:capacity]

    def assign_next(self) -> list[ScheduledTask]:
        assigned: list[ScheduledTask] = []
        for task in self.dispatchable():
            provider = self.registry.preferred_provider_for(task.capability_key)
            if provider is None:
                self._replace(task, status="blocked")
                continue
            assigned_task = task.model_copy(
                update={"provider_key": provider.key, "status": "running"}
            )
            self._replace(assigned_task)
            assigned.append(assigned_task)
        return assigned

    def _replace(self, updated: ScheduledTask, **changes: str) -> None:
        replacement = updated.model_copy(update=changes) if changes else updated
        self.tasks = [
            replacement
            if task.issue_key == updated.issue_key and task.repo == updated.repo
            else task
            for task in self.tasks
        ]
