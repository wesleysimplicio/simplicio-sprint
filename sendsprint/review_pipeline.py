"""Cross-agent review pipeline primitives."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReviewRole = Literal["implementer", "reviewer", "validator", "security"]


class ReviewAssignment(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    role: ReviewRole
    provider_key: str
    status: str = "pending"


class ReviewPipeline(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_key: str
    assignments: list[ReviewAssignment] = Field(default_factory=list)

    def blocking_roles(self) -> list[str]:
        return [item.role for item in self.assignments if item.status not in {"approved", "passed"}]


def default_review_pipeline(issue_key: str) -> ReviewPipeline:
    return ReviewPipeline(
        issue_key=issue_key,
        assignments=[
            ReviewAssignment(role="implementer", provider_key="codex", status="done"),
            ReviewAssignment(role="reviewer", provider_key="openclaw"),
            ReviewAssignment(role="validator", provider_key="claude-code"),
            ReviewAssignment(role="security", provider_key="openclaw"),
        ],
    )
