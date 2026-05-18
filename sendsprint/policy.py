"""Autonomy policy for side-effecting sprint operations."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AutonomyLevel = Literal[
    "observe",
    "plan",
    "execute",
    "commit",
    "push",
    "pr",
    "release",
    "deploy-callback",
]

PolicyAction = Literal[
    "read",
    "plan",
    "write-files",
    "run-validation",
    "llm-codegen",
    "commit",
    "push",
    "create-pr",
    "comment-issue",
    "close-issue",
    "publish-release",
    "deploy-callback",
]

LEVEL_ORDER: tuple[AutonomyLevel, ...] = (
    "observe",
    "plan",
    "execute",
    "commit",
    "push",
    "pr",
    "release",
    "deploy-callback",
)

ACTION_REQUIREMENTS: dict[PolicyAction, AutonomyLevel] = {
    "read": "observe",
    "plan": "plan",
    "write-files": "execute",
    "run-validation": "execute",
    "llm-codegen": "execute",
    "commit": "commit",
    "push": "push",
    "create-pr": "pr",
    "comment-issue": "pr",
    "close-issue": "pr",
    "publish-release": "release",
    "deploy-callback": "deploy-callback",
}


class AutonomyDenied(RuntimeError):
    """Raised when a policy blocks a side-effecting operation."""


def level_rank(level: AutonomyLevel) -> int:
    """Return a comparable rank for an autonomy level."""
    return LEVEL_ORDER.index(level)


class AutonomyPolicy(BaseModel):
    """Single contract for how far SendSprint may go in a run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: AutonomyLevel = "plan"
    require_human_review: bool = True
    notes: list[str] = Field(default_factory=list)

    def allows_level(self, required: AutonomyLevel) -> bool:
        """Return whether this policy reaches the requested autonomy level."""
        return level_rank(self.level) >= level_rank(required)

    def allows(self, action: PolicyAction) -> bool:
        """Return whether a named action is allowed."""
        return self.allows_level(ACTION_REQUIREMENTS[action])

    def require(self, action: PolicyAction) -> None:
        """Raise if a named action is not allowed."""
        if not self.allows(action):
            required = ACTION_REQUIREMENTS[action]
            raise AutonomyDenied(
                f"autonomy level '{self.level}' does not allow '{action}' "
                f"(requires '{required}')"
            )

    def side_effects(self) -> dict[str, bool]:
        """Compact side-effect matrix for dry-run plans and reports."""
        return {action: self.allows(action) for action in ACTION_REQUIREMENTS}


def parse_autonomy_level(value: str | None) -> AutonomyLevel:
    """Parse CLI/config strings into an autonomy level."""
    level = (value or "plan").strip().lower()
    if level not in LEVEL_ORDER:
        allowed = ", ".join(LEVEL_ORDER)
        raise ValueError(f"unknown autonomy level '{value}'. expected one of: {allowed}")
    return level  # type: ignore[return-value]
