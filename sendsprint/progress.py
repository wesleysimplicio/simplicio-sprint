"""Progress event contracts for SendSprint runs."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal

ProgressKind = Literal[
    "run_started",
    "item_started",
    "item_skipped",
    "item_finished",
    "drain_requested",
    "run_finished",
]


@dataclass(frozen=True)
class ProgressItem:
    key: str
    type: str


@dataclass(frozen=True)
class ProgressEvent:
    kind: ProgressKind
    sprint_name: str | None = None
    sprint_slug: str | None = None
    total_items: int = 0
    completed_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    pending_count: int = 0
    ok_count: int = 0
    cancelled: bool = False
    resume: bool = False
    items: list[ProgressItem] = field(default_factory=list)
    item_key: str | None = None
    item_type: str | None = None
    index: int | None = None
    status: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    dod: bool | None = None
    elapsed_s: float | None = None
    cost_usd: float | None = None
    reason: str | None = None
    message: str | None = None


ProgressCallback = Callable[[ProgressEvent], None]
