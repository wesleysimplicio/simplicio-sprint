"""Workspace and run-scope models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from sendsprint.llm.client import Provider as LlmProvider

RepoRole = Literal["front", "api", "back", "infra", "mobile", "lib", "other"]
ScopeMode = Literal["all", "mine"]
WatchProvider = Literal["jira", "azuredevops"]
WatchScope = Literal["assigned_to_me", "all"]


class RepoConfig(BaseModel):
    """A single repository inside the workspace."""

    name: str
    path: str
    role: RepoRole = "other"
    tech: str | None = None
    default_branch: str = "main"
    pr_target_branch: str | None = None
    branch_name_template: str | None = None
    pr_reviewers: list[str] = Field(default_factory=list)
    required_pr_reviewers: list[str] = Field(default_factory=list)
    package_manager: str | None = None
    test_command: str | None = None
    build_command: str | None = None
    lint_command: str | None = None
    e2e_command: str | None = None


class CodeGenerationConfig(BaseModel):
    """Opt-in LLM patch generation between build and lint."""

    enabled: bool = False
    provider: LlmProvider | None = None
    model: str | None = None
    max_usd: float = 1.0
    max_tokens: int = 8_000


class DeployWorkflowConfig(BaseModel):
    """Opt-in deploy callback executed after PR creation."""

    enabled: bool = False
    provider: str = "webhook"
    url: str | None = None
    method: str = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    final_status: str = "Deployed"


class WatchConfig(BaseModel):
    """Opt-in polling watcher configuration."""

    enabled: bool = False
    provider: WatchProvider = "azuredevops"
    interval_minutes: int = Field(default=15, ge=1)
    scope: WatchScope = "assigned_to_me"
    allowed_states: list[str] = Field(default_factory=lambda: ["New"])
    ignored_states: list[str] = Field(default_factory=lambda: ["Removed", "Closed", "Done"])
    work_item_types: list[str] = Field(default_factory=lambda: ["Task"])
    iteration_path: str | None = None
    sprint_id: int | str | None = None
    max_tasks_per_cycle: int = Field(default=1, ge=1)
    max_concurrent_tasks: int = Field(default=1, ge=1)
    require_clean_worktree: bool = True
    evidence_required: bool = True
    playwright_required_for_front: bool = True
    create_pr: bool = True
    pr_target_branch: str | None = None
    state_path: str = ".sendsprint/runs/watch-state.json"


class WorkspaceConfig(BaseModel):
    """Multi-repo workspace declared by the user (workspace.yaml)."""

    name: str = "workspace"
    root_path: str
    user_email: str | None = None
    user_display_name: str | None = None
    user_account_id: str | None = None
    user_descriptor: str | None = None
    repos: list[RepoConfig] = Field(default_factory=list)
    new_projects_dir: str = "Projetos/novos"
    pr_provider: Literal["github", "azuredevops"] = "github"
    pr_reviewers: list[str] = Field(default_factory=list)
    required_pr_reviewers: list[str] = Field(default_factory=list)
    default_base_branch: str = "develop"
    branch_name_template: str = "feature/{number}-{title}"
    code_generation: CodeGenerationConfig = Field(default_factory=CodeGenerationConfig)
    deploy: DeployWorkflowConfig = Field(default_factory=DeployWorkflowConfig)
    watch: WatchConfig = Field(default_factory=WatchConfig)


DEFAULT_DEVELOPABLE_STATUSES = (
    "new",
    "active",
    "to do",
    "todo",
    "open",
    "in progress",
    "doing",
    "selected for development",
    "backlog",
    "ready",
)


class ScopeConfig(BaseModel):
    """Filter: full sprint, only the running user's items, explicit keys, or status whitelist."""

    mode: ScopeMode = "all"
    user_email: str | None = None
    user_account_id: str | None = None
    user_descriptor: str | None = None
    user_display_name: str | None = None
    allowed_statuses: list[str] = Field(default_factory=lambda: list(DEFAULT_DEVELOPABLE_STATUSES))
    task_keys: list[str] | None = None

    def matches(self, item: object) -> bool:
        """Compatibility helper for older API routes."""
        if self.mode != "mine":
            return True
        email = getattr(item, "assignee_email", None)
        account_id = getattr(item, "assignee_account_id", None)
        descriptor = getattr(item, "assignee_descriptor", None)
        display_name = getattr(item, "assignee", None)
        return bool(
            (self.user_email and email and str(email).lower() == self.user_email.lower())
            or (self.user_account_id and account_id == self.user_account_id)
            or (self.user_descriptor and descriptor == self.user_descriptor)
            or (
                self.user_display_name
                and display_name
                and str(display_name).strip().lower() == self.user_display_name.strip().lower()
            )
        )
