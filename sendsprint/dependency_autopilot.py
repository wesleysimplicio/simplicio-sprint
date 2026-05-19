"""Dependency/security maintenance planning helpers."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DependencyFinding(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ecosystem: str
    manifest: str
    recommended_command: str


class DependencyAutopilotPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    findings: list[DependencyFinding] = Field(default_factory=list)


def detect_dependency_work(repo_path: str | Path) -> DependencyAutopilotPlan:
    root = Path(repo_path)
    findings: list[DependencyFinding] = []
    if (root / "pyproject.toml").is_file():
        findings.append(
            DependencyFinding(
                ecosystem="python",
                manifest="pyproject.toml",
                recommended_command="pip-audit && python -m pytest tests -q",
            )
        )
    if (root / "package.json").is_file() or (root / "web" / "package.json").is_file():
        findings.append(
            DependencyFinding(
                ecosystem="node",
                manifest="package.json",
                recommended_command="npm audit --json && npm test",
            )
        )
    return DependencyAutopilotPlan(findings=findings)
