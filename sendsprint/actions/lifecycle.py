"""Generic action lifecycle models.

These models represent work in *any* domain — software, design, ops,
compliance, marketing, etc. — without assuming GitHub, PRs, or tests.
Domain-specific concepts live in adapter implementations.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class ActionPhase(StrEnum):
    """Ordered phases an action traverses."""

    plan = "plan"
    execute = "execute"
    validate = "validate"
    evidence = "evidence"
    publish = "publish"
    monitor = "monitor"
    rework = "rework"
    learn = "learn"


class ActionStatus(StrEnum):
    """High-level status of an action."""

    pending = "pending"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    failed = "failed"


# ---------------------------------------------------------------------------
# Supporting models
# ---------------------------------------------------------------------------


class DomainDescriptor(BaseModel):
    """Identifies the domain an action belongs to."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Machine-readable domain key, e.g. 'code', 'design', 'ops'")
    label: str | None = Field(default=None, description="Human-friendly display name")
    version: str = "1.0"


class Objective(BaseModel):
    """What the action aims to achieve — decoupled from *how*."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(..., description="One-line description of the goal")
    acceptance_criteria: list[str] = Field(default_factory=list)
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary domain context (e.g. sprint item key, design brief URL)",
    )
    priority: Literal["critical", "high", "medium", "low"] = "medium"


class ExecutionStep(BaseModel):
    """One atomic unit of work inside the execute phase."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid4().hex[:8])
    name: str
    description: str | None = None
    status: ActionStatus = ActionStatus.pending
    started_at: datetime | None = None
    finished_at: datetime | None = None
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ValidationResult(BaseModel):
    """Outcome of the validate phase."""

    model_config = ConfigDict(extra="forbid")

    passed: bool
    checks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Individual check results (schema varies per domain)",
    )
    message: str | None = None


class EvidenceRecord(BaseModel):
    """A piece of evidence captured during or after execution."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(..., description="e.g. 'test-report', 'screenshot', 'approval-email'")
    uri: str | None = None
    content: str | None = Field(default=None, description="Inline content for small artifacts")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PublicationRecord(BaseModel):
    """Where and how results were published / reported."""

    model_config = ConfigDict(extra="forbid")

    channel: str = Field(..., description="e.g. 'github-pr', 'email', 'dashboard', 'jira-comment'")
    url: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    published_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class MonitorEntry(BaseModel):
    """A monitoring observation after publication."""

    model_config = ConfigDict(extra="forbid")

    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    signal: str = Field(
        ..., description="What was observed, e.g. 'deploy-healthy', 'error-rate-spike'"
    )
    details: dict[str, Any] = Field(default_factory=dict)
    requires_rework: bool = False


class LearningRecord(BaseModel):
    """Insight captured at the end of the lifecycle for future improvement."""

    model_config = ConfigDict(extra="forbid")

    lesson: str
    tags: list[str] = Field(default_factory=list)
    source_action_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalPolicy(BaseModel):
    """Declares how approval works for a given domain / action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    auto_approve: bool = False
    required_approvers: int = 1
    approver_roles: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Core action model
# ---------------------------------------------------------------------------


class Action(BaseModel):
    """Domain-agnostic action that traverses the lifecycle phases.

    An Action can represent a code task, a design deliverable, a compliance
    check, an ops runbook step, or anything else — the domain adapter fills
    in domain-specific logic while this model keeps the structure uniform.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    domain: DomainDescriptor
    phase: ActionPhase = ActionPhase.plan
    status: ActionStatus = ActionStatus.pending
    objective: Objective
    plan: list[ExecutionStep] = Field(default_factory=list)
    execution_log: list[ExecutionStep] = Field(default_factory=list)
    validation: ValidationResult | None = None
    evidence: list[EvidenceRecord] = Field(default_factory=list)
    publications: list[PublicationRecord] = Field(default_factory=list)
    monitors: list[MonitorEntry] = Field(default_factory=list)
    rework_count: int = 0
    learnings: list[LearningRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Escape hatch for domain-specific data not covered by the generic schema",
    )

    # -- helpers -------------------------------------------------------------

    def advance_phase(self, to: ActionPhase) -> None:
        """Move the action to *to* phase, updating timestamp."""
        self.phase = to
        self.updated_at = datetime.now(UTC)

    def mark_done(self) -> None:
        self.status = ActionStatus.done
        self.updated_at = datetime.now(UTC)

    def mark_failed(self, reason: str | None = None) -> None:
        self.status = ActionStatus.failed
        if reason:
            self.metadata["failure_reason"] = reason
        self.updated_at = datetime.now(UTC)
