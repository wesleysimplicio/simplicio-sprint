"""Tests for Ralph Wiggum and Codex Goal loop contracts."""

from __future__ import annotations

from sendsprint.loops import LoopAttempt, LoopContract, LoopReport


def test_loop_report_records_exit_signal() -> None:
    contract = LoopContract(
        kind="codex-goal",
        objective="finish issue",
        acceptance_criteria=["tests pass"],
        validation_gates=["pytest"],
    )
    report = LoopReport(contract=contract)
    report = report.record(LoopAttempt(attempt=1, status="passed", exit_signal=True))
    assert report.exit_signal is True
    assert report.final_status == "passed"
    assert contract.display_name == "Codex /goal"
