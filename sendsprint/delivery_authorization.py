"""Project profiles and authorization checkpoints for delivery actions."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.policy import PolicyAction
from sendsprint.risk_policy import RiskClass

ApprovalMode = Literal["auto", "manual"]


class ProjectProfile(BaseModel):
    """Company/project-specific autonomy and review contract."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    company: str
    organization: str
    repository: str
    allowed_actions: list[PolicyAction] = Field(default_factory=list)
    default_reviewers: list[str] = Field(default_factory=list)
    autonomy_level: str = "plan"
    branch_rules: list[str] = Field(default_factory=list)


class AuthorizationCheckpoint(BaseModel):
    """Decision for a side effect under a profile and risk class."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: PolicyAction
    risk: RiskClass
    mode: ApprovalMode
    approved: bool
    reason: str


def authorize_action(
    *,
    profile: ProjectProfile,
    action: PolicyAction,
    risk: RiskClass,
) -> AuthorizationCheckpoint:
    if action not in profile.allowed_actions:
        return AuthorizationCheckpoint(
            action=action,
            risk=risk,
            mode="manual",
            approved=False,
            reason="action is not enabled for this project profile",
        )
    if risk in {"high", "critical"}:
        return AuthorizationCheckpoint(
            action=action,
            risk=risk,
            mode="manual",
            approved=False,
            reason="high-risk actions require explicit human approval",
        )
    return AuthorizationCheckpoint(
        action=action,
        risk=risk,
        mode="auto",
        approved=True,
        reason="profile allows this low-risk action automatically",
    )
