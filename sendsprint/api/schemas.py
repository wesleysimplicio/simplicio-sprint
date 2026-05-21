"""Pydantic schemas for the SendSprint web API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Provider = Literal["jira", "azuredevops"]
RunMode = Literal["all", "mine", "selected"]
RouteConfidence = Literal["high", "medium", "low"]
ColumnKey = Literal[
    "backlog",
    "planning",
    "programming",
    "testing",
    "review",
    "awaiting_deploy",
    "blocked",
]


class HealthResponse(BaseModel):
    ok: bool = True
    version: str
    providers_configured: dict[str, bool]


class VersionCheckResponse(BaseModel):
    current_version: str
    latest_version: str | None = None
    update_available: bool = False
    status: Literal["ok", "unavailable"] = "ok"
    source: str = "pypi"
    source_url: str = "https://pypi.org/project/sendsprint/"
    message: str


class JiraAuthRequest(BaseModel):
    base_url: str
    email: str
    api_token: str
    sprint_url: str | None = None
    sprint_id: str | None = None


class AzureAuthRequest(BaseModel):
    organization: str | None = None
    project: str | None = None
    team: str | None = None
    user_email: str | None = None
    pat: str | None = None
    sprint_url: str | None = None


class AuthResponse(BaseModel):
    provider: Provider
    account: str
    ok: bool
    user_display_name: str | None = None
    ado_team_path: str | None = None
    ado_iteration_path: str | None = None
    fallback_used: bool = False
    capture_transport: str | None = None


class AppLoginRequest(BaseModel):
    email: str
    password: str


class AppLoginResponse(BaseModel):
    ok: bool = True
    email: str
    active: bool = True
    display_name: str | None = None
    permissions: dict[str, bool] = Field(default_factory=lambda: {"can_run_all_backlog": True})


class AuthBootstrapResponse(BaseModel):
    operator_token: str
    default_provider: Provider | None = None
    jira_configured: bool = False
    azuredevops_configured: bool = False
    providers: dict[str, object] = Field(default_factory=dict)


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
    description: str | None = None
    revision: int | str | None = None
    assignee: str | None = None
    assignee_email: str | None = None
    story_points: float | None = None
    parent_key: str | None = None
    labels: list[str] = Field(default_factory=list)
    links: list[dict[str, str | None]] = Field(default_factory=list)
    comments: list[dict[str, str | None]] = Field(default_factory=list)
    attachments: list[dict[str, str | int | None]] = Field(default_factory=list)
    acceptance_criteria: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    source_url: str | None = None
    board_column: ColumnKey | None = None
    board_status: str | None = None
    board_updated_at: str | None = None
    board_updated_by: str | None = None
    archived: bool = False
    history: list[dict[str, str | bool | None]] = Field(default_factory=list)


class SprintDetail(BaseModel):
    sprint: SprintSummary
    items: list[SprintItemSummary]
    archived_count: int = 0


class MoveSprintItemRequest(BaseModel):
    provider: Provider
    target_column: ColumnKey
    actor_email: str | None = None
    note: str | None = None


class ArchiveSprintItemRequest(BaseModel):
    provider: Provider
    actor_email: str | None = None
    archived: bool = True
    note: str | None = None


class SprintItemMutationResponse(BaseModel):
    ok: bool = True


class StartRunRequest(BaseModel):
    provider: Provider
    sprint_id: str
    mode: RunMode = "all"
    item_keys: list[str] = Field(default_factory=list)
    repo_path: str | None = None
    workspace_path: str | None = None
    project_setup: dict[str, object] | None = None
    dry_run: bool = False
    resume: bool = True
    no_cache: bool = False
    autonomy_level: str = "plan"
    run_id: str | None = None


class StartRunResponse(BaseModel):
    run_id: str
    status: Literal["started"] = "started"


class RoutePreviewSummary(BaseModel):
    text: str
    task_count: int
    planned_delivery_count: int
    selected_repo_count: int
    low_confidence_count: int
    warning_count: int


class RoutePreviewTaskUnderstanding(BaseModel):
    item_key: str
    item_type: str
    title: str
    status: str
    scopes: list[str] = Field(default_factory=list)
    scope_source: Literal["label", "inferred", "none"] = "none"
    relationship: str = "none"
    selected_repos: list[str] = Field(default_factory=list)
    confidence: RouteConfidence | None = None
    reasons: list[str] = Field(default_factory=list)


class RoutePreviewSelectedRepo(BaseModel):
    item_key: str
    item_type: str
    title: str
    repo: str
    repo_name: str
    repo_role: str | None = None
    branch: str
    target_branch: str
    confidence: RouteConfidence
    reasons: list[str] = Field(default_factory=list)
    relationship: str = "none"
    worktree_path: str | None = None
    validation_template: str | None = None
    validation_commands: list[str] = Field(default_factory=list)


class RoutePreviewLowConfidenceItem(BaseModel):
    item_key: str
    title: str
    repo: str | None = None
    repo_name: str | None = None
    confidence: RouteConfidence = "low"
    reason: str
    recommended_action: str


class RoutePreviewResponse(BaseModel):
    schema_version: str = "1.0"
    provider: Provider
    sprint_id: str
    sprint_name: str
    mode: RunMode
    item_keys: list[str] = Field(default_factory=list)
    autonomy_level: str = "plan"
    side_effects: dict[str, bool] = Field(default_factory=dict)
    summary: RoutePreviewSummary
    task_understanding: list[RoutePreviewTaskUnderstanding] = Field(default_factory=list)
    selected_repos: list[RoutePreviewSelectedRepo] = Field(default_factory=list)
    low_confidence_items: list[RoutePreviewLowConfidenceItem] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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
