"""Stage validation commands from risk, stack, and changed files."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.risk_policy import classify_risk


class ValidationStage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    commands: list[str] = Field(default_factory=list)


class ValidationPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    risk: str
    stages: list[ValidationStage] = Field(default_factory=list)

    def commands(self) -> list[str]:
        return [command for stage in self.stages for command in stage.commands]


def build_validation_plan(
    *,
    issue_text: str = "",
    changed_files: list[str] | None = None,
    base_commands: list[str] | None = None,
) -> ValidationPlan:
    changed_files = changed_files or []
    risk = classify_risk(issue_text=issue_text, changed_files=changed_files)
    commands = list(base_commands or [])
    if not commands:
        commands = _default_commands(changed_files)
    stages = [ValidationStage(name="focused", commands=commands[:2] or commands)]
    if risk.risk in {"medium", "high", "critical"}:
        stages.append(
            ValidationStage(name="regression", commands=_regression_commands(changed_files))
        )
    if risk.risk in {"high", "critical"}:
        stages.append(
            ValidationStage(name="evidence", commands=["pytest -q", "npx playwright test"])
        )
    return ValidationPlan(risk=risk.risk, stages=[stage for stage in stages if stage.commands])


def _default_commands(changed_files: list[str]) -> list[str]:
    joined = " ".join(changed_files).lower()
    if any(path.endswith(".py") for path in changed_files):
        return ["ruff check .", "pytest tests -q"]
    if any(path.endswith((".ts", ".tsx", ".js")) for path in changed_files):
        return ["npm run typecheck", "npm test"]
    if any(path.endswith(".yml") or "workflow" in path.lower() for path in changed_files):
        return ["python -m pytest tests -q", "npm run typecheck"]
    if joined:
        return ["pytest tests -q"]
    return ["pytest tests -q"]


def _regression_commands(changed_files: list[str]) -> list[str]:
    if any(path.endswith(".py") for path in changed_files):
        return ["python -m pytest tests -q", "python -m mypy sendsprint"]
    if any(path.endswith((".ts", ".tsx", ".js")) for path in changed_files):
        return ["npm run build", "npx playwright test"]
    return ["python -m pytest tests -q"]
