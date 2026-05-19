"""Pydantic models for sprint data and architecture reports."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field

ItemType = Literal["Story", "Task", "Subtask", "Bug", "Epic", "Feature", "Issue"]


class Link(BaseModel):
    type: str
    target_key: str
    target_url: str | None = None


class Comment(BaseModel):
    author: str
    body: str
    created_at: datetime


class Attachment(BaseModel):
    filename: str
    url: str
    mime_type: str | None = None
    size_bytes: int | None = None


class SprintItem(BaseModel):
    id: str
    key: str
    type: ItemType
    title: str
    description: str | None = None
    status: str
    revision: int | str | None = None
    assignee: str | None = None
    assignee_email: str | None = None
    assignee_account_id: str | None = None
    assignee_descriptor: str | None = None
    story_points: float | None = None
    parent_key: str | None = None
    labels: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    comments: list[Comment] = Field(default_factory=list)
    attachments: list[Attachment] = Field(default_factory=list)
    acceptance_criteria: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    source_url: str | None = None


class Sprint(BaseModel):
    id: str
    name: str
    state: str = "active"
    goal: str | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    items: list[SprintItem] = Field(default_factory=list)
    source: Literal["jira", "azuredevops"] = "jira"
    transport: Literal["mcp", "api", "playwright"] = "api"

    @property
    def stories(self) -> list[SprintItem]:
        return [i for i in self.items if i.type == "Story"]

    @property
    def tasks(self) -> list[SprintItem]:
        return [i for i in self.items if i.type == "Task"]

    @property
    def subtasks(self) -> list[SprintItem]:
        return [i for i in self.items if i.type == "Subtask"]

    @property
    def bugs(self) -> list[SprintItem]:
        return [i for i in self.items if i.type == "Bug"]

    @property
    def epics(self) -> list[SprintItem]:
        return [i for i in self.items if i.type == "Epic"]

    @property
    def features(self) -> list[SprintItem]:
        return [i for i in self.items if i.type == "Feature"]

    @property
    def issues(self) -> list[SprintItem]:
        return [i for i in self.items if i.type == "Issue"]


class ArchitectureReport(BaseModel):
    repo_path: str
    has_architecture_md: bool = False
    has_docs_architecture_dir: bool = False
    has_c4: bool = False
    has_adrs: bool = False
    adr_count: int = 0
    has_dependency_graph: bool = False
    has_deploy_topology: bool = False
    has_readme: bool = False
    has_agentic_starter: bool = False
    mapping_substrate: str = "native"
    has_skill_catalog: bool = False
    has_agent_catalog: bool = False
    missing: list[str] = Field(default_factory=list)
    score: float = 0.0
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def is_mapped(self) -> bool:
        return self.has_agentic_starter or self.score >= 0.6
