"""Reports and evidence models for the 10-step orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

StepStatus = Literal["pending", "running", "ok", "failed", "skipped"]
Severity = Literal["info", "low", "medium", "high", "critical"]
PrProvider = Literal["github", "azuredevops"]


def _now() -> datetime:
    return datetime.now(UTC)


class TestEvidence(BaseModel):
    """One test artifact (unit run, e2e screenshot, log)."""

    kind: Literal["unit", "e2e", "lint", "build", "screenshot", "log"]
    title: str
    passed: bool
    path: str | None = None
    message: str | None = None
    duration_ms: int | None = None


class SecurityFinding(BaseModel):
    """A flagged security concern (NOT auto-fixed)."""

    rule: str
    severity: Severity = "medium"
    file: str | None = None
    line: int | None = None
    message: str
    recommendation: str | None = None


class PrInfo(BaseModel):
    """Pull request created on a remote provider."""

    provider: PrProvider
    repo: str
    number: int | None = None
    url: str | None = None
    title: str
    body: str | None = None
    source_branch: str
    target_branch: str
    state: Literal["draft", "open", "merged", "closed"] = "open"


class StepReport(BaseModel):
    """Result of one step of the 10-step flow for one repo (or global)."""

    step: int
    name: str
    repo: str | None = None
    tech: str | None = None
    status: StepStatus = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    message: str | None = None
    evidence: list[TestEvidence] = Field(default_factory=list)
    findings: list[SecurityFinding] = Field(default_factory=list)
    pr: PrInfo | None = None

    @property
    def details(self) -> dict[str, str | None]:
        """Compatibility shape used by the API bridge."""
        return {"message": self.message}


class RunReport(BaseModel):
    """End-to-end run output across the workspace."""

    workspace: str
    sprint_name: str | None = None
    sprint_id: str | None = None
    scope_mode: Literal["all", "mine"] = "all"
    user: str | None = None
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    steps: list[StepReport] = Field(default_factory=list)
    prs: list[PrInfo] = Field(default_factory=list)
    failed: bool = False
    summary: str | None = None
