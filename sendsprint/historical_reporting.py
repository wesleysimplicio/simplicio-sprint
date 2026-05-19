"""Historical reporting aggregates for dashboard analytics."""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field


class HistoricalRun(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    repo: str
    provider: str
    status: str


class HistoricalReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    totals_by_status: dict[str, int] = Field(default_factory=dict)
    totals_by_provider: dict[str, int] = Field(default_factory=dict)


def build_historical_report(runs: list[HistoricalRun]) -> HistoricalReport:
    return HistoricalReport(
        totals_by_status=dict(Counter(run.status for run in runs)),
        totals_by_provider=dict(Counter(run.provider for run in runs)),
    )
