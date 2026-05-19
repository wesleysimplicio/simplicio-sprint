"""Compact human review pack builder."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class HumanReviewPack(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    summary: str
    changed_areas: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    evidence_links: list[str] = Field(default_factory=list)
    risk_class: str = "low"
    rollback_plan: str | None = None

    def to_markdown(self) -> str:
        areas = "\n".join(f"- {item}" for item in self.changed_areas) or "- none"
        tests = "\n".join(f"- `{item}`" for item in self.test_commands) or "- none"
        evidence = "\n".join(f"- {item}" for item in self.evidence_links) or "- none"
        rollback = self.rollback_plan or "Not provided."
        return (
            "## Human Review Pack\n\n"
            f"### Summary\n{self.summary}\n\n"
            f"### Changed Areas\n{areas}\n\n"
            f"### Validation\n{tests}\n\n"
            f"### Evidence\n{evidence}\n\n"
            f"### Risk\n- {self.risk_class}\n\n"
            f"### Rollback\n{rollback}\n"
        )
