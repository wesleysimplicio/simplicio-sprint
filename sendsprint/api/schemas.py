"""Pydantic schemas for the SendSprint web API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["jira", "azuredevops"]
RunMode = Literal["all", "mine", "selected"]


class HealthResponse(BaseModel):
    ok: bool = True
    version: str
    providers_configured: dict[str, bool]


class JiraAuthRequest(BaseModel):
    base_url: str
    email: str
    api_token: str


class AzureAuthRequest(BaseModel):
    organization: str
    project: str
    pat: str


class AuthResponse(BaseModel):
    provider: Provider
    account: str
    ok: bool
    user_display_name: str | None = None


class SprintSummary(BaseModel):
    id: str
    name: str
    state: str = "active"
    provider: Provider
    start_date: str | None = None
    end_date: str | None = None
    item_count: int | None = None
    goal: str | None = None


class SprintItemSummary(BaseModel):
    id: str
    key: str
    type: str
    title: str
    status: str
    assignee: str | None = None
    assignee_email: str | None = None
    story_points: float | None = None


class SprintDetail(BaseModel):
    sprint: SprintSummary
    items: list[SprintItemSummary]


class StartRunRequest(BaseModel):
    provider: Provider
    sprint_id: str
    mode: RunMode = "all"
    item_keys: list[str] = Field(default_factory=list)
    repo_path: str | None = None
    workspace_path: str | None = None
    dry_run: bool = False
    resume: bool = True
    run_id: str | None = None


class StartRunResponse(BaseModel):
    run_id: str
    status: Literal["started"] = "started"


class RunStepEvent(BaseModel):
    type: Literal["step", "log", "evidence", "loop", "regression", "summary", "done", "error"] = (
        "step"
    )
    run_id: str
    step: int | None = None
    name: str | None = None
    status: str | None = None
    message: str | None = None
    evidence_path: str | None = None
    evidence_label: str | None = None
    progress: float | None = None
    summary: str | None = None
    pr_url: str | None = None
    failed: bool | None = None
    iteration: int | None = None
    max_iterations: int | None = None
    failing_tests: list[str] | None = None


class RunStatus(BaseModel):
    run_id: str
    state: Literal["queued", "running", "done", "failed"]
    sprint_id: str
    provider: Provider
    started_at: str | None = None
    finished_at: str | None = None
    summary: str | None = None
    pr_url: str | None = None
    failed: bool = False
    last_step: int | None = None


class AgentTimelineEvent(BaseModel):
    type: str
    observed_at: str | None = None
    step: int | None = None
    name: str | None = None
    status: str | None = None
    message: str | None = None
    evidence_path: str | None = None
    evidence_label: str | None = None
    progress: float | None = None
    summary: str | None = None
    pr_url: str | None = None
    failed: bool | None = None
    iteration: int | None = None
    max_iterations: int | None = None
    failing_tests: list[str] | None = None


class AgentRunSnapshot(BaseModel):
    run_id: str
    sprint_id: str
    provider: Provider
    state: Literal["queued", "running", "done", "failed"]
    mode: RunMode
    item_keys: list[str] = Field(default_factory=list)
    repo_path: str | None = None
    workspace_path: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    summary: str | None = None
    pr_url: str | None = None
    failed: bool = False
    current_step: int | None = None
    current_step_name: str | None = None
    current_step_status: str | None = None
    progress: float | None = None
    iteration: int | None = None
    max_iterations: int | None = None
    failing_tests: list[str] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    recent_logs: list[str] = Field(default_factory=list)
    timeline: list[AgentTimelineEvent] = Field(default_factory=list)


class AgentStatusAnswer(BaseModel):
    run_id: str
    adapter: Literal["claude", "codex", "hermes", "generic"] = "generic"
    state: Literal["queued", "running", "done", "failed", "unknown"]
    summary: str
    current_step: str = "unknown"
    active_agents: list[str] = Field(default_factory=list)
    last_evidence: str | None = None
    blockers: list[str] = Field(default_factory=list)
    pr_url: str | None = None
    next_action: str = "unknown"
    constraints: list[str] = Field(default_factory=list)
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class ImportSprintsRequest(BaseModel):
    provider: Provider
    board_id: str | None = None
    team_path: str | None = None


class ImportSprintsResponse(BaseModel):
    job_id: str
    started: bool = True
