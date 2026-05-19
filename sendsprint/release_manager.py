"""Release recommendation and changelog planning helpers."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReleaseLevel = Literal["patch", "minor", "major"]


class ClosedWorkItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    labels: list[str] = Field(default_factory=list)


class ReleaseRecommendation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    level: ReleaseLevel
    rationale: list[str] = Field(default_factory=list)


def recommend_release(items: list[ClosedWorkItem]) -> ReleaseRecommendation:
    text = " ".join(f"{item.title} {' '.join(item.labels)}" for item in items).lower()
    if "breaking" in text or "major" in text:
        return ReleaseRecommendation(level="major", rationale=["breaking-change marker detected"])
    if "feature" in text or "enhancement" in text or "feat" in text:
        return ReleaseRecommendation(level="minor", rationale=["new feature work detected"])
    return ReleaseRecommendation(level="patch", rationale=["default safe release level"])
