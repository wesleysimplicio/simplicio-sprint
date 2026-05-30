"""Persistent run state for resumable SendSprint deliveries."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STATE_DIR = Path(".sendsprint/state")
STOP_FILE = "STOP"


def state_dir(repo_root: str | Path) -> Path:
    return Path(repo_root) / STATE_DIR


def state_path(repo_root: str | Path, sprint_slug: str) -> Path:
    return state_dir(repo_root) / f"{sprint_slug}.json"


def stop_file_path(repo_root: str | Path) -> Path:
    return state_dir(repo_root) / STOP_FILE


def stop_requested(repo_root: str | Path) -> bool:
    return stop_file_path(repo_root).exists()


@dataclass
class RunState:
    """Durable item state for one sprint run."""

    sprint_slug: str
    completed: set[str] = field(default_factory=set)
    failed: set[str] = field(default_factory=set)
    pending: set[str] = field(default_factory=set)
    last_pr: dict[str, int] = field(default_factory=dict)
    path: Path | None = None

    @classmethod
    def for_sprint(
        cls,
        repo_root: str | Path,
        sprint_slug: str,
        item_keys: list[str],
        *,
        resume: bool = False,
    ) -> RunState:
        path = state_path(repo_root, sprint_slug)
        if resume and not path.exists():
            raise FileNotFoundError(f"run state not found: {path}")
        if resume:
            state = cls.load(path)
            state.sprint_slug = sprint_slug
            state.path = path
            state.sync_items(item_keys)
        else:
            state = cls(sprint_slug=sprint_slug, pending=set(_clean_keys(item_keys)), path=path)
        state.save()
        return state

    @classmethod
    def load(cls, path: str | Path) -> RunState:
        state_path_ = Path(path)
        data = json.loads(state_path_.read_text(encoding="utf-8"))
        return cls(
            sprint_slug=str(data.get("sprint_slug") or state_path_.stem),
            completed=_str_set(data.get("completed")),
            failed=_str_set(data.get("failed")),
            pending=_str_set(data.get("pending")),
            last_pr=_last_pr(data.get("last_pr")),
            path=state_path_,
        )

    def sync_items(self, item_keys: list[str]) -> None:
        current = set(_clean_keys(item_keys))
        self.completed &= current
        self.failed &= current
        self.pending = (self.pending & current) | (current - self.completed - self.failed)
        self.last_pr = {key: number for key, number in self.last_pr.items() if key in current}

    def should_run(self, item_key: str) -> bool:
        return (
            item_key in self.pending
            and item_key not in self.completed
            and item_key not in self.failed
        )

    def mark_completed(self, item_key: str, *, pr_number: int | None = None) -> None:
        self.pending.discard(item_key)
        self.failed.discard(item_key)
        self.completed.add(item_key)
        if pr_number is not None:
            self.last_pr[item_key] = pr_number

    def mark_failed(self, item_key: str) -> None:
        self.pending.discard(item_key)
        self.completed.discard(item_key)
        self.failed.add(item_key)

    def save(self) -> None:
        if self.path is None:
            raise ValueError("RunState.path is required before save")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "sprint_slug": self.sprint_slug,
            "completed": sorted(self.completed),
            "failed": sorted(self.failed),
            "pending": sorted(self.pending),
            "last_pr": {key: self.last_pr[key] for key in sorted(self.last_pr)},
        }
        temp_path = self.path.with_name(f"{self.path.name}.tmp")
        temp_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        temp_path.replace(self.path)


def _clean_keys(item_keys: list[str]) -> list[str]:
    return [key for key in (str(item_key).strip() for item_key in item_keys) if key]


def _str_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {item for item in (str(raw).strip() for raw in value) if item}


def _last_pr(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, int] = {}
    for raw_key, raw_number in value.items():
        key = str(raw_key).strip()
        if not key:
            continue
        try:
            result[key] = int(raw_number)
        except (TypeError, ValueError):
            continue
    return result
