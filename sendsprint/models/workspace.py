"""Workspace, repo, watch and run-scope models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RepoRole = Literal["front", "api", "back", "infra", "mobile", "lib", "other"]
ScopeMode = Literal["all", "mine"]
WatchProvider = Literal["jira", "azuredevops", "github"]
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
    test_command: str | None = None
    pr_reviewers: list[str] = Field(default_factory=list)
    required_pr_reviewers: list[str] = Field(default_factory=list)
    # Frontend hints used to capture screenshot evidence with Playwright.
    frontend_url: str | None = None
    dev_server_command: str | None = None


class WatchConfig(BaseModel):
    """Trigger configuration: poll assigned cards and finish them."""

    enabled: bool = False
    provider: WatchProvider = "azuredevops"
    interval_minutes: int = Field(default=15, ge=1)
    scope: WatchScope = "assigned_to_me"
    allowed_states: list[str] = Field(default_factory=lambda: ["New"])
    ignored_states: list[str] = Field(default_factory=lambda: ["Removed", "Closed", "Done"])
    work_item_types: list[str] = Field(default_factory=lambda: ["Task"])
    sprint_id: int | str | None = None
    max_tasks_per_cycle: int = Field(default=1, ge=1)
    require_clean_worktree: bool = True
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
    pr_provider: Literal["github", "azuredevops"] = "github"
    pr_reviewers: list[str] = Field(default_factory=list)
    required_pr_reviewers: list[str] = Field(default_factory=list)
    default_base_branch: str = "develop"
    branch_name_template: str = "feature/{number}-{title}"
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
