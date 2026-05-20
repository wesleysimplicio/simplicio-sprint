"""Tests for the deterministic tri-agent status answer renderer.

Covers: normal, failed, blocked, completed, sparse-history snapshots,
determinism, human-readable markdown, machine-readable dict, evidence
truncation, unknown-state defaults, and adapter-agnostic usage.

See: https://github.com/wesleysimplicio/SendSprint/issues/116
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from sendsprint.status_relay import RunSnapshot
from sendsprint.status_renderer import (
    _MAX_HISTORY_SUMMARY,
    StatusAnswer,
    StatusRenderer,
    format_human_readable,
    format_machine_readable,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _ts() -> datetime:
    """Fixed timestamp for deterministic assertions."""
    return datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC)


def _normal_snapshot() -> RunSnapshot:
    return RunSnapshot(
        run_id="run-001",
        current_action="running tests",
        failures=[],
        blockers=[],
        next_step="create PR",
        active_agents=["claude", "codex"],
        evidence_refs=["evidence/log-001.txt", "evidence/screenshot-001.png"],
        pr_links=["https://github.com/org/repo/pull/42"],
        last_command="pytest tests/",
        last_evidence="tests passed (34/34)",
        event_count=15,
        updated_at=_ts(),
    )


def _failed_snapshot() -> RunSnapshot:
    return RunSnapshot(
        run_id="run-002",
        current_action="rework loop",
        failures=["lint: 3 errors", "test: 1 assertion failed"],
        blockers=[],
        next_step="fix lint errors",
        active_agents=["codex"],
        evidence_refs=["evidence/lint-output.txt"],
        pr_links=[],
        last_command="ruff check .",
        last_evidence="lint failed",
        event_count=8,
        updated_at=_ts(),
    )


def _blocked_snapshot() -> RunSnapshot:
    return RunSnapshot(
        run_id="run-003",
        current_action="waiting for approval",
        failures=[],
        blockers=["security finding: CVE-2026-1234", "human review required"],
        next_step="escalate to operator",
        active_agents=["hermes"],
        evidence_refs=[],
        pr_links=["https://github.com/org/repo/pull/99"],
        last_command="",
        last_evidence="security scan flagged CVE",
        event_count=22,
        updated_at=_ts(),
    )


def _completed_snapshot() -> RunSnapshot:
    return RunSnapshot(
        run_id="run-004",
        current_action="completed",
        failures=[],
        blockers=[],
        next_step="",
        active_agents=[],
        evidence_refs=["evidence/final-report.md"],
        pr_links=["https://github.com/org/repo/pull/50"],
        last_command="gh pr create",
        last_evidence="PR merged",
        event_count=30,
        updated_at=_ts(),
    )


def _sparse_snapshot() -> RunSnapshot:
    """Minimal snapshot — almost no data filled in."""
    return RunSnapshot(
        run_id="run-005",
        updated_at=_ts(),
    )


# ---------------------------------------------------------------------------
# StatusAnswer model tests
# ---------------------------------------------------------------------------


class TestStatusAnswerModel:
    def test_defaults_are_unknown(self) -> None:
        answer = StatusAnswer()
        assert answer.current_action == "unknown"
        assert answer.next_step == "unknown"
        assert answer.failures == []
        assert answer.blockers == []
        assert answer.active_agents == []
        assert answer.evidence_refs == []
        assert answer.pr_links == []

    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValueError):
            StatusAnswer(bogus_field="nope")  # type: ignore[call-arg]

    def test_serialization_roundtrip(self) -> None:
        answer = StatusAnswer(
            run_id="r1",
            current_action="testing",
            timestamp=_ts(),
        )
        data = answer.model_dump()
        restored = StatusAnswer(**data)
        assert restored == answer


# ---------------------------------------------------------------------------
# Renderer tests
# ---------------------------------------------------------------------------


class TestStatusRenderer:
    def setup_method(self) -> None:
        self.renderer = StatusRenderer()

    def test_normal_snapshot(self) -> None:
        answer = self.renderer.render(_normal_snapshot())
        assert answer.current_action == "running tests"
        assert answer.next_step == "create PR"
        assert answer.active_agents == ["claude", "codex"]
        assert answer.event_count == 15
        assert answer.failures == []
        assert answer.blockers == []
        assert len(answer.pr_links) == 1

    def test_failed_snapshot(self) -> None:
        answer = self.renderer.render(_failed_snapshot())
        assert answer.current_action == "rework loop"
        assert len(answer.failures) == 2
        assert "lint: 3 errors" in answer.failures
        assert answer.blockers == []

    def test_blocked_snapshot(self) -> None:
        answer = self.renderer.render(_blocked_snapshot())
        assert len(answer.blockers) == 2
        assert "security finding: CVE-2026-1234" in answer.blockers
        assert answer.failures == []

    def test_completed_snapshot(self) -> None:
        answer = self.renderer.render(_completed_snapshot())
        assert answer.current_action == "completed"
        assert answer.active_agents == []
        assert answer.next_step == "unknown"  # empty -> unknown

    def test_sparse_snapshot_defaults_to_unknown(self) -> None:
        answer = self.renderer.render(_sparse_snapshot())
        assert answer.current_action == "idle"  # snapshot default
        assert answer.next_step == "unknown"  # empty string -> unknown
        assert answer.failures == []
        assert answer.blockers == []
        assert answer.active_agents == []
        assert answer.event_count == 0

    def test_determinism(self) -> None:
        """Same snapshot must produce identical answers every time."""
        snap = _normal_snapshot()
        a1 = self.renderer.render(snap)
        a2 = self.renderer.render(snap)
        assert a1.model_dump() == a2.model_dump()

    def test_determinism_100_iterations(self) -> None:
        snap = _failed_snapshot()
        baseline = self.renderer.render(snap).model_dump()
        for _ in range(100):
            assert self.renderer.render(snap).model_dump() == baseline

    def test_timestamp_matches_snapshot(self) -> None:
        snap = _normal_snapshot()
        answer = self.renderer.render(snap)
        assert answer.timestamp == snap.updated_at

    def test_no_mutation_of_snapshot(self) -> None:
        snap = _normal_snapshot()
        original_action = snap.current_action
        self.renderer.render(snap)
        assert snap.current_action == original_action

    def test_evidence_refs_are_copies(self) -> None:
        snap = _normal_snapshot()
        answer = self.renderer.render(snap)
        answer.evidence_refs.append("extra")
        assert "extra" not in snap.evidence_refs


# ---------------------------------------------------------------------------
# Human-readable formatter tests
# ---------------------------------------------------------------------------


class TestFormatHumanReadable:
    def setup_method(self) -> None:
        self.renderer = StatusRenderer()

    def test_normal_contains_header(self) -> None:
        answer = self.renderer.render(_normal_snapshot())
        md = format_human_readable(answer)
        assert "## Status — `run-001`" in md
        assert "**Current action:** running tests" in md
        assert "**Next step:** create PR" in md

    def test_normal_shows_agents(self) -> None:
        answer = self.renderer.render(_normal_snapshot())
        md = format_human_readable(answer)
        assert "claude, codex" in md

    def test_failed_shows_failures(self) -> None:
        answer = self.renderer.render(_failed_snapshot())
        md = format_human_readable(answer)
        assert "### Failures" in md
        assert "- lint: 3 errors" in md

    def test_blocked_shows_blockers(self) -> None:
        answer = self.renderer.render(_blocked_snapshot())
        md = format_human_readable(answer)
        assert "### Blockers" in md
        assert "- security finding: CVE-2026-1234" in md

    def test_pr_links_section(self) -> None:
        answer = self.renderer.render(_normal_snapshot())
        md = format_human_readable(answer)
        assert "### PRs / Issues" in md
        assert "https://github.com/org/repo/pull/42" in md

    def test_sparse_no_crash(self) -> None:
        answer = self.renderer.render(_sparse_snapshot())
        md = format_human_readable(answer)
        assert "## Status" in md
        assert "**Active agents:** none" in md

    def test_evidence_truncation(self) -> None:
        snap = _normal_snapshot()
        snap_dict = snap.model_dump()
        snap_dict["evidence_refs"] = [f"evidence/item-{i}.txt" for i in range(10)]
        snap_big = RunSnapshot(**snap_dict)
        answer = self.renderer.render(snap_big)
        md = format_human_readable(answer)
        assert "... and 5 more" in md

    def test_no_evidence_section_when_empty(self) -> None:
        answer = self.renderer.render(_blocked_snapshot())
        md = format_human_readable(answer)
        assert "### Evidence" not in md

    def test_last_evidence_shown(self) -> None:
        answer = self.renderer.render(_normal_snapshot())
        md = format_human_readable(answer)
        assert "**Last evidence:** tests passed (34/34)" in md

    def test_completed_no_failures_or_blockers(self) -> None:
        answer = self.renderer.render(_completed_snapshot())
        md = format_human_readable(answer)
        assert "### Failures" not in md
        assert "### Blockers" not in md


# ---------------------------------------------------------------------------
# Machine-readable formatter tests
# ---------------------------------------------------------------------------


class TestFormatMachineReadable:
    def setup_method(self) -> None:
        self.renderer = StatusRenderer()

    def test_normal_keys(self) -> None:
        answer = self.renderer.render(_normal_snapshot())
        d = format_machine_readable(answer)
        assert d["run_id"] == "run-001"
        assert d["current_action"] == "running tests"
        assert d["next_step"] == "create PR"
        assert isinstance(d["failures"], list)
        assert isinstance(d["timestamp"], str)

    def test_json_serializable(self) -> None:
        answer = self.renderer.render(_normal_snapshot())
        d = format_machine_readable(answer)
        serialized = json.dumps(d)
        restored = json.loads(serialized)
        assert restored["run_id"] == "run-001"

    def test_evidence_total_vs_refs(self) -> None:
        snap = _normal_snapshot()
        snap_dict = snap.model_dump()
        snap_dict["evidence_refs"] = [f"e{i}" for i in range(60)]
        snap_big = RunSnapshot(**snap_dict)
        answer = self.renderer.render(snap_big)
        d = format_machine_readable(answer)
        assert len(d["evidence_refs"]) == _MAX_HISTORY_SUMMARY
        assert d["evidence_total"] == 60

    def test_sparse_machine_readable(self) -> None:
        answer = self.renderer.render(_sparse_snapshot())
        d = format_machine_readable(answer)
        assert d["current_action"] == "idle"
        assert d["next_step"] == "unknown"
        assert d["failures"] == []

    def test_failed_machine_readable(self) -> None:
        answer = self.renderer.render(_failed_snapshot())
        d = format_machine_readable(answer)
        assert len(d["failures"]) == 2
        assert d["blockers"] == []

    def test_blocked_machine_readable(self) -> None:
        answer = self.renderer.render(_blocked_snapshot())
        d = format_machine_readable(answer)
        assert len(d["blockers"]) == 2
        assert d["failures"] == []

    def test_timestamp_is_iso(self) -> None:
        answer = self.renderer.render(_normal_snapshot())
        d = format_machine_readable(answer)
        parsed = datetime.fromisoformat(d["timestamp"])
        assert parsed.tzinfo is not None


# ---------------------------------------------------------------------------
# Cross-adapter usage test
# ---------------------------------------------------------------------------


class TestCrossAdapterUsage:
    """All three adapters can use the same renderer and get consistent data."""

    def test_same_renderer_for_all_adapters(self) -> None:
        renderer = StatusRenderer()
        snap = _normal_snapshot()
        answer = renderer.render(snap)

        human = format_human_readable(answer)
        machine = format_machine_readable(answer)

        # Both contain the same core data
        assert "run-001" in human
        assert machine["run_id"] == "run-001"
        assert "running tests" in human
        assert machine["current_action"] == "running tests"

    def test_renderer_instance_is_stateless(self) -> None:
        renderer = StatusRenderer()
        a1 = renderer.render(_normal_snapshot())
        a2 = renderer.render(_failed_snapshot())
        a3 = renderer.render(_normal_snapshot())
        # First and third should be identical (stateless)
        assert a1.model_dump() == a3.model_dump()
        assert a1.model_dump() != a2.model_dump()
