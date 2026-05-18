"""Native Ralph Wiggum and Codex Goal loop contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

LoopKind = Literal["ralph-wiggum", "codex-goal"]
LoopStatus = Literal["pending", "running", "passed", "failed", "blocked"]


class LoopAttempt(BaseModel):
    """One autonomous loop attempt."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    attempt: int
    status: LoopStatus
    failing_command: str | None = None
    applied_fix: str | None = None
    validation_output: str | None = None
    exit_signal: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LoopContract(BaseModel):
    """Execution contract shared by Claude Ralph and Codex Goal flows."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: LoopKind
    objective: str
    acceptance_criteria: list[str] = Field(default_factory=list)
    validation_gates: list[str] = Field(default_factory=list)
    max_attempts: int = 5

    @property
    def display_name(self) -> str:
        if self.kind == "ralph-wiggum":
            return "Claude Code Ralph Wiggum"
        return "Codex /goal"


class LoopReport(BaseModel):
    """Recorded loop execution history."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract: LoopContract
    attempts: list[LoopAttempt] = Field(default_factory=list)
    final_status: LoopStatus = "pending"

    def record(self, attempt: LoopAttempt) -> LoopReport:
        """Return a new report with an appended attempt and updated status."""
        attempts = [*self.attempts, attempt]
        final = (
            attempt.status
            if attempt.exit_signal or len(attempts) >= self.contract.max_attempts
            else "running"
        )
        return self.model_copy(update={"attempts": attempts, "final_status": final})

    @property
    def exit_signal(self) -> bool:
        return any(attempt.exit_signal for attempt in self.attempts)
