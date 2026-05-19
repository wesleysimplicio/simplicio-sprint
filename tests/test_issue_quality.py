"""Tests for issue quality scoring and test intent generation."""

from __future__ import annotations

from sendsprint.issue_quality import (
    analyze_issue_quality,
    generate_test_intents,
    parse_acceptance_criteria,
)


def test_parse_acceptance_criteria_normalizes_markdown_checklist() -> None:
    raw = """Acceptance Criteria:
- [ ] User can save the form
- [ ] API returns 200
3. Logs remain visible
"""
    assert parse_acceptance_criteria(raw) == [
        "User can save the form",
        "API returns 200",
        "Logs remain visible",
    ]


def test_analyze_issue_quality_scores_complete_issue_high() -> None:
    report = analyze_issue_quality(
        title="Add dashboard export flow",
        description=(
            "Add a dashboard export button for finance users without breaking existing filters. "
            "Validation: pytest tests/test_exports.py and playwright export journey. "
            "Screenshot shows the broken state. "
            "Steps to reproduce: 1. Open dashboard 2. Click export."
        ),
        acceptance_criteria=[
            "Finance users can export the dashboard as CSV",
            "The export keeps the active filters applied",
        ],
        labels=["scope:front", "component:dashboard"],
        comments=["Error log attached from staging"],
        attachments=["export-bug.png"],
        threshold=70,
    )
    assert report.score >= 85
    assert report.passes is True
    assert report.planning_needed is False
    assert report.missing_sections == []


def test_analyze_issue_quality_scores_incomplete_issue_low_and_suggests_plan() -> None:
    report = analyze_issue_quality(
        title="Fix login",
        description="Bug in login page",
        acceptance_criteria=None,
        threshold=70,
    )
    assert report.score < 70
    assert report.passes is False
    assert "acceptance_criteria" in report.missing_sections
    assert report.suggested_acceptance_criteria
    assert report.suggested_test_plan


def test_generate_test_intents_maps_frontend_backend_cli_and_docs_cases() -> None:
    intents = generate_test_intents(
        title="Cover quality gates",
        description="Frontend flow, API contract, CLI output, and docs update",
        acceptance_criteria=[
            "User can submit the signup form and reach the confirmation screen",
            "API persists the audit record after the request succeeds",
            "CLI command prints the generated plan to stdout",
            "README example remains accurate and runnable",
        ],
    )
    assert [intent.level for intent in intents] == ["e2e", "integration", "smoke", "smoke"]
    assert all("implementation details" not in intent.rationale.lower() for intent in intents)
