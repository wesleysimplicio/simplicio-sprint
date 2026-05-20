"""Tests for repository-scoped operational memory."""

from __future__ import annotations

from sendsprint.failure_learning import FailureEvent
from sendsprint.operational_memory import OperationalMemoryStore
from sendsprint.oss_mode import OssGateDecision, OssLearningRecord


def test_operational_memory_store_persists_repo_facts_and_events(tmp_path) -> None:
    store = OperationalMemoryStore(tmp_path)
    store.remember("Org/API Repo", "default_branch", "develop")
    store.record_event(
        "Org/API Repo",
        FailureEvent.inferred(
            fingerprint="tests::payments",
            step="step-5-tests",
            status="failed",
            message="pytest assertion failed",
        ),
    )
    store.record_event(
        "Org/API Repo",
        FailureEvent.inferred(
            fingerprint="tests::payments",
            step="step-5-tests",
            status="passed",
            message="pytest passed on retry",
        ),
    )

    loaded = store.load_or_create("Org/API Repo")

    assert loaded.facts["default_branch"] == "develop"
    assert len(loaded.recent_events) == 2
    assert loaded.learned_failures["tests::payments"].is_flaky is True
    assert loaded.flaky_fingerprints() == ["tests::payments"]
    assert loaded.trust_score().score < 1.0


def test_operational_memory_is_isolated_per_repository(tmp_path) -> None:
    store = OperationalMemoryStore(tmp_path)
    store.remember("repo-a", "stack", "python")
    store.remember("repo-b", "stack", "node")

    repo_a = store.load_or_create("repo-a")
    repo_b = store.load_or_create("repo-b")

    assert repo_a.facts == {"stack": "python"}
    assert repo_b.facts == {"stack": "node"}


def test_operational_memory_caps_recent_events_but_keeps_aggregates(tmp_path) -> None:
    store = OperationalMemoryStore(tmp_path)
    memory = store.load_or_create("repo-a")

    for idx in range(60):
        memory.record_event(
            FailureEvent.inferred(
                fingerprint="lint::ruff",
                step="step-4-lint",
                status="failed" if idx % 2 == 0 else "passed",
                message="ruff check failed" if idx % 2 == 0 else "ruff clean",
            ),
            max_events=10,
        )

    assert len(memory.recent_events) == 10
    assert memory.learned_failures["lint::ruff"].total_runs == 60
    assert memory.learned_failures["lint::ruff"].is_flaky is True


def test_operational_memory_persists_oss_learning_and_follow_up(tmp_path) -> None:
    store = OperationalMemoryStore(tmp_path)
    repo = "NousResearch/hermes-agent"
    record = OssLearningRecord(
        candidate_id="fix-nameerror-in-conversation-loop",
        repo=repo,
        title="Fix NameError in conversation loop",
        decision="salvage",
        signal="closed duplicate lineage points to the accepted fix",
        result="defer new PR and review the existing fix",
        reusable_rule="check closed PR lineage before opening tiny fixes",
        related_refs=["PR #27359"],
    )
    gate = OssGateDecision(
        gate="dedupe",
        status="blocked",
        reason="duplicate-risk match found",
        evidence=["PR #27359"],
    )

    store.remember_oss_candidate(repo, record)
    store.record_oss_gate(repo, record.candidate_id, gate)
    store.remember_oss_monitor_ref(repo, record.candidate_id, "PR #27359")

    loaded = store.load_or_create(repo)

    assert loaded.oss_candidates[record.candidate_id].reusable_rule == (
        "check closed PR lineage before opening tiny fixes"
    )
    assert loaded.find_oss_dedupe("Fix NameError") == "PR #27359"
    assert loaded.oss_gate_history[record.candidate_id][0].status == "blocked"
    assert loaded.oss_monitor_refs[record.candidate_id] == "PR #27359"
