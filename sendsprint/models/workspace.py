"""Workspace and run-scope models."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

RepoRole = Literal["front", "api", "back", "infra", "mobile", "lib", "other"]
ScopeMode = Literal["all", "mine"]


class RepoConfig(BaseModel):
    """A single repository inside the workspace."""

    name: str
    path: str
    role: RepoRole = "other"
    tech: str | None = None
    default_branch: str = "main"
    pr_target_branch: str | None = None
    package_manager: str | None = None
    test_command: str | None = None
    build_command: str | None = None
    lint_command: str | None = None
    e2e_command: str | None = None


class WorkspaceConfig(BaseModel):
    """Multi-repo workspace declared by the user (workspace.yaml)."""

    name: str = "workspace"
    root_path: str
    repos: list[RepoConfig] = Field(default_factory=list)
    new_projects_dir: str = "Projetos/novos"
    pr_provider: Literal["github", "azuredevops"] = "github"
    pr_reviewers: list[str] = Field(default_factory=list)
    default_base_branch: str = "develop"


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
