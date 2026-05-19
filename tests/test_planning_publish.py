"""Tests for planning issue body generation and publication."""

from __future__ import annotations

from sendsprint.issue_quality import analyze_issue_quality
from sendsprint.planning import DeliveryPlan, PlannedDelivery
from sendsprint.planning_publish import (
    PlanningPublishConfig,
    build_planning_issue_drafts,
    build_planning_status_comment,
    find_existing_issue,
    planning_marker,
    publish_planning_issues,
)
from sendsprint.policy import AutonomyPolicy
from sendsprint.trackers.github_issues import GitHubIssue


def _plan() -> DeliveryPlan:
    return DeliveryPlan(
        source="jira",
        sprint_id="42",
        sprint_name="Sprint 42",
        autonomy_level="plan",
        deliveries=[
            PlannedDelivery(
                item_key="APP-1",
                item_type="Task",
                title="Add export button",
                repo="/tmp/frontend",
                repo_role="front",
                branch="feature/app-1",
                target_branch="develop",
                confidence="high",
                reason="explicit scope label",
                relationship="parent",
                validation_template="react",
                validation_commands=["npm test", "npm run e2e"],
            )
        ],
    )


def test_build_planning_issue_drafts_supports_umbrella_and_delivery_modes() -> None:
    report = analyze_issue_quality(
        title="Add export button",
        description="Implement export button on dashboard without breaking filters.",
        acceptance_criteria=["User exports the current dashboard filters"],
    )
    drafts = build_planning_issue_drafts(
        _plan(),
        config=PlanningPublishConfig(mode="both", labels=["planning", "quality"]),
        quality_reports={"APP-1": report},
    )
    assert len(drafts) == 2
    assert drafts[0].kind == "umbrella"
    assert drafts[1].kind == "delivery"
    assert planning_marker("42", kind="delivery", item_key="APP-1") in drafts[1].body
    assert "Execution Links" in drafts[1].body
    assert "Suggested Validation Plan" in drafts[1].body


def test_find_existing_issue_deduplicates_by_marker_even_when_title_changes() -> None:
    draft = build_planning_issue_drafts(_plan(), config=PlanningPublishConfig(mode="per-delivery"))[
        0
    ]
    existing = GitHubIssue(
        number=9,
        title="Planning: renamed by human",
        body=f"Intro\n{draft.marker}\nmore",
        url="https://example.com/issues/9",
    )
    match = find_existing_issue([existing], draft)
    assert match is not None
    assert match.number == 9


def test_publish_planning_issues_respects_autonomy_and_dry_run() -> None:
    class FakeTracker:
        def __init__(self) -> None:
            self.created: list[tuple[str, str, list[str] | None]] = []

        def list_issues(self, *, state: str = "all") -> list[GitHubIssue]:
            return []

        def create(self, title: str, body: str, *, labels: list[str] | None = None) -> str:
            self.created.append((title, body, labels))
            return "https://example.com/issues/10"

    tracker = FakeTracker()
    dry_run = publish_planning_issues(
        _plan(),
        tracker,  # type: ignore[arg-type]
        autonomy_policy=AutonomyPolicy(level="plan"),
        config=PlanningPublishConfig(mode="umbrella", dry_run=True),
    )
    assert dry_run.entries[0].action == "dry-run"
    assert tracker.created == []

    blocked = publish_planning_issues(
        _plan(),
        tracker,  # type: ignore[arg-type]
        autonomy_policy=AutonomyPolicy(level="execute"),
        config=PlanningPublishConfig(mode="umbrella", dry_run=False),
    )
    assert blocked.entries[0].action == "blocked"
    assert tracker.created == []

    created = publish_planning_issues(
        _plan(),
        tracker,  # type: ignore[arg-type]
        autonomy_policy=AutonomyPolicy(level="pr"),
        config=PlanningPublishConfig(mode="umbrella", dry_run=False),
    )
    assert created.entries[0].action == "created"
    assert tracker.created[0][0].startswith("Planning: sprint 42")


def test_build_planning_status_comment_links_prs_evidence_and_status() -> None:
    body = build_planning_status_comment(
        event="execution-finished",
        pr_urls=["https://example.com/pr/1"],
        evidence_urls=["https://example.com/evidence/1"],
        final_status="passed",
    )
    assert "execution-finished" in body
    assert "https://example.com/pr/1" in body
    assert "https://example.com/evidence/1" in body
    assert "passed" in body
