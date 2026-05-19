"""Risk classification and budget policy helpers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskClass = Literal["docs-only", "low", "medium", "high", "critical"]
TaskProfile = Literal["mass", "research", "deep"]


class BudgetPolicy(BaseModel):
    """Execution budget limits used by planners and retries."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    max_cost_usd: float = 10.0
    max_duration_minutes: int = 60
    max_retries: int = 2
    provider_preference: list[str] = Field(default_factory=list)
    task_profile: TaskProfile = "research"


class RiskDecision(BaseModel):
    """Risk result plus the implied budget and approval requirement."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    risk: RiskClass
    reasons: list[str] = Field(default_factory=list)
    requires_human_review: bool = False
    budget: BudgetPolicy = Field(default_factory=BudgetPolicy)


def classify_risk(*, issue_text: str = "", changed_files: list[str] | None = None) -> RiskDecision:
    changed_files = changed_files or []
    haystack = f"{issue_text} {' '.join(changed_files)}".lower()
    reasons: list[str] = []
    risk: RiskClass = "low"
    if changed_files and all(
        path.lower().endswith((".md", ".mdx", ".txt")) for path in changed_files
    ):
        risk = "docs-only"
        reasons.append("only documentation files changed")
    if any(token in haystack for token in ("auth", "token", "password", "security", "secret")):
        risk = "critical"
        reasons.append("auth/security sensitive surface")
    elif any(token in haystack for token in ("release", "publish", "deploy", "workflow")):
        risk = "high"
        reasons.append("release or delivery surface changed")
    elif any(token in haystack for token in ("payment", "billing", "migration", "shared")):
        risk = "high"
        reasons.append("shared or business-critical flow")
    elif (
        any(token in haystack for token in ("api", "database", "config", "ci"))
        and risk != "docs-only"
    ):
        risk = "medium"
        reasons.append("integration/config surface changed")
    budget = _budget_for(risk)
    return RiskDecision(
        risk=risk,
        reasons=reasons or ["default classification"],
        requires_human_review=risk in {"high", "critical"},
        budget=budget,
    )


def _budget_for(risk: RiskClass) -> BudgetPolicy:
    if risk == "docs-only":
        return BudgetPolicy(
            max_cost_usd=1, max_duration_minutes=15, max_retries=1, task_profile="mass"
        )
    if risk == "low":
        return BudgetPolicy(
            max_cost_usd=3, max_duration_minutes=30, max_retries=1, task_profile="mass"
        )
    if risk == "medium":
        return BudgetPolicy(
            max_cost_usd=10, max_duration_minutes=60, max_retries=2, task_profile="research"
        )
    return BudgetPolicy(
        max_cost_usd=25, max_duration_minutes=120, max_retries=3, task_profile="deep"
    )
