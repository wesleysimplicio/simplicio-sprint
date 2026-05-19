"""Repository-scoped operational memory backed by small JSON files."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.failure_learning import (
    FailureEvent,
    FlakyOutcomeTracker,
    LearnedFailure,
    TrustScore,
    calculate_trust_score,
)


class RepositoryOperationalMemory(BaseModel):
    """Compact operational memory for one repository."""

    model_config = ConfigDict(extra="forbid")

    repo: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    facts: dict[str, str] = Field(default_factory=dict)
    recent_events: list[FailureEvent] = Field(default_factory=list)
    learned_failures: dict[str, LearnedFailure] = Field(default_factory=dict)

    def remember(self, key: str, value: str) -> None:
        self.facts[key] = value
        self.updated_at = datetime.now(UTC)

    def record_event(self, event: FailureEvent, *, max_events: int = 50) -> None:
        self.recent_events.append(event)
        if len(self.recent_events) > max_events:
            self.recent_events = self.recent_events[-max_events:]
        tracker = FlakyOutcomeTracker(failures=self.learned_failures)
        learned = tracker.record(event)
        self.learned_failures[event.fingerprint] = learned
        self.updated_at = datetime.now(UTC)

    def trust_score(self) -> TrustScore:
        return calculate_trust_score(self.recent_events)

    def flaky_fingerprints(self) -> list[str]:
        tracker = FlakyOutcomeTracker(failures=self.learned_failures)
        return tracker.flaky_fingerprints()


class OperationalMemoryStore:
    """Persists repository memories under `.sendsprint/operational-memory/`."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).expanduser().resolve()
        self.memory_dir = self.root / ".sendsprint" / "operational-memory"

    def path_for(self, repo: str) -> Path:
        safe = "".join(ch if ch.isalnum() else "-" for ch in repo.lower()).strip("-")
        return self.memory_dir / f"{safe or 'repo'}.json"

    def load_or_create(self, repo: str) -> RepositoryOperationalMemory:
        path = self.path_for(repo)
        if path.exists():
            return RepositoryOperationalMemory.model_validate_json(path.read_text(encoding="utf-8"))
        return RepositoryOperationalMemory(repo=repo)

    def save(self, memory: RepositoryOperationalMemory) -> Path:
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        path = self.path_for(memory.repo)
        path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
        return path

    def remember(self, repo: str, key: str, value: str) -> RepositoryOperationalMemory:
        memory = self.load_or_create(repo)
        memory.remember(key, value)
        self.save(memory)
        return memory

    def record_event(self, repo: str, event: FailureEvent) -> RepositoryOperationalMemory:
        memory = self.load_or_create(repo)
        memory.record_event(event)
        self.save(memory)
        return memory
