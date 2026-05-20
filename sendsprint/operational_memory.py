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
from sendsprint.oss_mode import OssGateDecision, OssLearningRecord


class RepositoryOperationalMemory(BaseModel):
    """Compact operational memory for one repository."""

    model_config = ConfigDict(extra="forbid")

    repo: str
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    facts: dict[str, str] = Field(default_factory=dict)
    recent_events: list[FailureEvent] = Field(default_factory=list)
    learned_failures: dict[str, LearnedFailure] = Field(default_factory=dict)
    oss_candidates: dict[str, OssLearningRecord] = Field(default_factory=dict)
    oss_dedupe_markers: dict[str, str] = Field(default_factory=dict)
    oss_monitor_refs: dict[str, str] = Field(default_factory=dict)
    oss_gate_history: dict[str, list[OssGateDecision]] = Field(default_factory=dict)

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

    def remember_oss_candidate(self, record: OssLearningRecord) -> None:
        self.oss_candidates[record.candidate_id] = record
        public_ref = record.related_refs[0] if record.related_refs else record.candidate_id
        markers = {record.candidate_id.lower(), record.title.lower()}
        markers.update(ref.lower() for ref in record.related_refs)
        for marker in markers:
            if marker:
                self.oss_dedupe_markers[marker] = public_ref
        self.updated_at = datetime.now(UTC)

    def find_oss_dedupe(self, marker: str) -> str | None:
        needle = marker.lower()
        for remembered_marker, ref in self.oss_dedupe_markers.items():
            if needle in remembered_marker or remembered_marker in needle:
                return ref
        return None

    def remember_oss_monitor_ref(self, candidate_id: str, ref: str) -> None:
        self.oss_monitor_refs[candidate_id] = ref
        self.updated_at = datetime.now(UTC)

    def record_oss_gate(
        self,
        candidate_id: str,
        decision: OssGateDecision,
        *,
        max_gates: int = 100,
    ) -> None:
        history = self.oss_gate_history.setdefault(candidate_id, [])
        history.append(decision)
        if len(history) > max_gates:
            self.oss_gate_history[candidate_id] = history[-max_gates:]
        self.updated_at = datetime.now(UTC)


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

    def remember_oss_candidate(
        self,
        repo: str,
        record: OssLearningRecord,
    ) -> RepositoryOperationalMemory:
        memory = self.load_or_create(repo)
        memory.remember_oss_candidate(record)
        self.save(memory)
        return memory

    def find_oss_dedupe(self, repo: str, marker: str) -> str | None:
        memory = self.load_or_create(repo)
        return memory.find_oss_dedupe(marker)

    def remember_oss_monitor_ref(
        self,
        repo: str,
        candidate_id: str,
        ref: str,
    ) -> RepositoryOperationalMemory:
        memory = self.load_or_create(repo)
        memory.remember_oss_monitor_ref(candidate_id, ref)
        self.save(memory)
        return memory

    def record_oss_gate(
        self,
        repo: str,
        candidate_id: str,
        decision: OssGateDecision,
    ) -> RepositoryOperationalMemory:
        memory = self.load_or_create(repo)
        memory.record_oss_gate(candidate_id, decision)
        self.save(memory)
        return memory
