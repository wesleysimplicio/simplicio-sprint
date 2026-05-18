"""Tests for executive sprint reports."""

from __future__ import annotations

from sendsprint.models.reports import RunReport, StepReport
from sendsprint.reports import render_executive_report


def test_executive_report_lists_blockers() -> None:
    report = RunReport(workspace="ws", sprint_id="42", failed=True, summary="1 failed")
    report.steps.append(StepReport(step=5, name="unit-tests", status="failed", message="boom"))
    markdown = render_executive_report(report)
    assert "Executive Sprint Summary" in markdown
    assert "- unit-tests: boom" in markdown
