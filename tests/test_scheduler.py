from sendsprint.scheduler import (
    AgentFanoutPolicy,
    HostResourceSnapshot,
    ParallelIssueScheduler,
    ScheduledTask,
)


def test_scheduler_assigns_preferred_provider_within_capacity() -> None:
    scheduler = ParallelIssueScheduler(concurrency_limit=1)
    scheduler.enqueue(ScheduledTask(issue_key="#1", repo="repo-a", capability_key="test"))
    scheduler.enqueue(ScheduledTask(issue_key="#2", repo="repo-b", capability_key="review"))

    assigned = scheduler.assign_next()

    assert len(assigned) == 1
    assert assigned[0].provider_key in {"codex", "hermes"}
    assert assigned[0].status == "running"


def test_scheduler_blocks_unknown_capability() -> None:
    scheduler = ParallelIssueScheduler(concurrency_limit=1)
    scheduler.enqueue(ScheduledTask(issue_key="#1", repo="repo-a", capability_key="nonexistent"))

    assigned = scheduler.assign_next()

    assert assigned == []
    assert scheduler.tasks[0].status == "blocked"


def test_scheduler_uses_resource_aware_fanout_capacity() -> None:
    scheduler = ParallelIssueScheduler(
        concurrency_limit=1,
        fanout_policy=AgentFanoutPolicy(requested_agents=5),
        resource_snapshot=HostResourceSnapshot(
            logical_cpus=16,
            available_memory_mb=32768,
            cpu_idle_percent=80,
        ),
    )
    for issue in range(1, 7):
        scheduler.enqueue(
            ScheduledTask(issue_key=f"#{issue}", repo=f"repo-{issue}", capability_key="test")
        )

    assigned = scheduler.assign_next()

    assert len(assigned) == 5
    assert scheduler.effective_concurrency_limit == 5


def test_scheduler_reduces_fanout_when_memory_is_low() -> None:
    scheduler = ParallelIssueScheduler(
        fanout_policy=AgentFanoutPolicy(requested_agents=5),
        resource_snapshot=HostResourceSnapshot(logical_cpus=16, available_memory_mb=2500),
    )

    assert scheduler.effective_concurrency_limit == 1
    receipt = scheduler.fanout_receipt
    assert receipt is not None
    assert receipt.allowed_agents == 1
    assert receipt.limiting_factor == "memory_slots"


def test_scheduler_reduces_fanout_when_cpu_is_busy() -> None:
    scheduler = ParallelIssueScheduler(
        fanout_policy=AgentFanoutPolicy(requested_agents=5),
        resource_snapshot=HostResourceSnapshot(
            logical_cpus=16,
            available_memory_mb=32768,
            cpu_idle_percent=5,
        ),
    )

    assert scheduler.effective_concurrency_limit == 1


def test_fanout_receipt_explains_unknown_cpu_telemetry() -> None:
    policy = AgentFanoutPolicy(requested_agents=5)
    receipt = policy.decision_for(
        HostResourceSnapshot(logical_cpus=8, available_memory_mb=32768, cpu_idle_percent=None)
    )

    assert receipt.allowed_agents == 5
    assert receipt.requested_agents == 5
    assert "cpu idle telemetry unavailable" in " ".join(receipt.reasons)
