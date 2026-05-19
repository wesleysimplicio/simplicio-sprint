"""Mission handoff contract between Tota Agent and SendSprint."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Mission(BaseModel):
    """High-level objective passed into SendSprint for execution planning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    objective: str
    repos: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    autonomy_level: str = "plan"
    budget_usd: float = 10.0
    priority: str = "normal"


class MissionHandoff(BaseModel):
    """Concrete engineering handoff derived from a high-level mission."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    objective: str
    planning_titles: list[str] = Field(default_factory=list)
    execution_order: list[str] = Field(default_factory=list)
    validation_focus: list[str] = Field(default_factory=list)


def build_mission_handoff(mission: Mission) -> MissionHandoff:
    titles = [f"Planning: {mission.objective} ({repo})" for repo in mission.repos] or [
        f"Planning: {mission.objective}"
    ]
    validation = ["focused checks", "regression"]
    if any("release" in item.lower() or "security" in item.lower() for item in mission.constraints):
        validation.append("evidence review")
    return MissionHandoff(
        objective=mission.objective,
        planning_titles=titles,
        execution_order=mission.repos or ["current-repo"],
        validation_focus=validation,
    )
