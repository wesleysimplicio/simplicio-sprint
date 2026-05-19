"""GitHub Actions CI triage and safe repair planning primitives."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class CheckRunFailure(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    conclusion: str
    log_excerpt: str = ""


class CiRepairPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    root_cause: str
    repair_actions: list[str] = Field(default_factory=list)
    rerun_commands: list[str] = Field(default_factory=list)


def plan_ci_repair(failures: list[CheckRunFailure]) -> CiRepairPlan:
    joined = " ".join(f"{item.name} {item.log_excerpt}" for item in failures).lower()
    if "ruff" in joined or "eslint" in joined or "mypy" in joined:
        return CiRepairPlan(
            root_cause="static-analysis failure",
            repair_actions=["apply lint/type fix in the affected files"],
            rerun_commands=["python -m pytest tests -q", "ruff check ."],
        )
    if "playwright" in joined or "pytest" in joined or "test" in joined:
        return CiRepairPlan(
            root_cause="test failure",
            repair_actions=[
                "reproduce failing test locally",
                "fix regression and capture evidence",
            ],
            rerun_commands=["python -m pytest tests -q", "npx playwright test"],
        )
    return CiRepairPlan(
        root_cause="unknown ci failure",
        repair_actions=["inspect logs and reproduce the failing workflow step"],
        rerun_commands=["python -m pytest tests -q"],
    )
