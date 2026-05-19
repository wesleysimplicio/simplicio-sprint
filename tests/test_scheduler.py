from sendsprint.scheduler import ParallelIssueScheduler, ScheduledTask


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
