"""Tests for autonomy level integration across run state, reports, and policy."""

from __future__ import annotations

import pytest

from sendsprint.models.reports import RunReport
from sendsprint.policy import (
    ACTION_REQUIREMENTS,
    LEVEL_ORDER,
    AutonomyDenied,
    AutonomyPolicy,
    level_rank,
    parse_autonomy_level,
)
from sendsprint.reports import render_executive_report
from sendsprint.run_state import RunState, RunStateStore

# ---------------------------------------------------------------------------
# AutonomyPolicy — permissions allowed and denied per level
# ---------------------------------------------------------------------------


class TestAutonomyPolicyAllows:
    """Verify that each level allows exactly the expected actions."""

    def test_observe_allows_only_read(self) -> None:
        policy = AutonomyPolicy(level="observe")
        assert policy.allows("read") is True
        assert policy.allows("plan") is False
        assert policy.allows("write-files") is False

    def test_plan_allows_read_and_plan(self) -> None:
        policy = AutonomyPolicy(level="plan")
        assert policy.allows("read") is True
        assert policy.allows("plan") is True
        assert policy.allows("write-files") is False
        assert policy.allows("commit") is False

    def test_execute_allows_write_and_validation(self) -> None:
        policy = AutonomyPolicy(level="execute")
        assert policy.allows("write-files") is True
        assert policy.allows("run-validation") is True
        assert policy.allows("llm-codegen") is True
        assert policy.allows("commit") is False

    def test_commit_allows_commit_but_not_push(self) -> None:
        policy = AutonomyPolicy(level="commit")
        assert policy.allows("commit") is True
        assert policy.allows("push") is False

    def test_push_allows_push_but_not_pr(self) -> None:
        policy = AutonomyPolicy(level="push")
        assert policy.allows("push") is True
        assert policy.allows("create-pr") is False

    def test_pr_allows_pr_and_issue_ops(self) -> None:
        policy = AutonomyPolicy(level="pr")
        assert policy.allows("create-pr") is True
        assert policy.allows("comment-issue") is True
        assert policy.allows("close-issue") is True
        assert policy.allows("publish-release") is False

    def test_release_allows_publish(self) -> None:
        policy = AutonomyPolicy(level="release")
        assert policy.allows("publish-release") is True
        assert policy.allows("deploy-callback") is False

    def test_deploy_callback_allows_everything(self) -> None:
        policy = AutonomyPolicy(level="deploy-callback")
        for action in ACTION_REQUIREMENTS:
            assert policy.allows(action) is True


# ---------------------------------------------------------------------------
# AutonomyPolicy.require — raises AutonomyDenied
# ---------------------------------------------------------------------------


class TestAutonomyPolicyRequire:
    """Verify require() raises AutonomyDenied for blocked actions."""

    def test_observe_denies_plan(self) -> None:
        policy = AutonomyPolicy(level="observe")
        with pytest.raises(AutonomyDenied, match="observe.*plan"):
            policy.require("plan")

    def test_plan_denies_commit(self) -> None:
        policy = AutonomyPolicy(level="plan")
        with pytest.raises(AutonomyDenied, match="plan.*commit"):
            policy.require("commit")

    def test_allowed_action_does_not_raise(self) -> None:
        policy = AutonomyPolicy(level="pr")
        policy.require("read")
        policy.require("plan")
        policy.require("create-pr")


# ---------------------------------------------------------------------------
# side_effects matrix
# ---------------------------------------------------------------------------


def test_side_effects_matrix_keys_match_actions() -> None:
    policy = AutonomyPolicy(level="plan")
    matrix = policy.side_effects()
    assert set(matrix.keys()) == set(ACTION_REQUIREMENTS.keys())


def test_side_effects_plan_level() -> None:
    matrix = AutonomyPolicy(level="plan").side_effects()
    assert matrix["read"] is True
    assert matrix["plan"] is True
    assert matrix["write-files"] is False
    assert matrix["push"] is False


# ---------------------------------------------------------------------------
# level_rank ordering
# ---------------------------------------------------------------------------


def test_level_ordering_is_monotonic() -> None:
    for i in range(len(LEVEL_ORDER) - 1):
        assert level_rank(LEVEL_ORDER[i]) < level_rank(LEVEL_ORDER[i + 1])


# ---------------------------------------------------------------------------
# parse_autonomy_level
# ---------------------------------------------------------------------------


class TestParseAutonomyLevel:
    def test_valid_levels(self) -> None:
        for level in LEVEL_ORDER:
            assert parse_autonomy_level(level) == level

    def test_none_defaults_to_plan(self) -> None:
        assert parse_autonomy_level(None) == "plan"

    def test_whitespace_stripped(self) -> None:
        assert parse_autonomy_level("  pr  ") == "pr"

    def test_case_insensitive(self) -> None:
        assert parse_autonomy_level("OBSERVE") == "observe"
        assert parse_autonomy_level("Deploy-Callback") == "deploy-callback"
        assert parse_autonomy_level("FULL") == "deploy-callback"

    def test_invalid_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="unknown autonomy level"):
            parse_autonomy_level("chaos")

    def test_empty_string_defaults_to_plan(self) -> None:
        assert parse_autonomy_level("") == "plan"


# ---------------------------------------------------------------------------
# RunState — autonomy_level field
# ---------------------------------------------------------------------------


class TestRunStateAutonomy:
    def test_default_autonomy_is_plan(self) -> None:
        state = RunState(run_id="run-1", source="jira", sprint_id="42")
        assert state.autonomy_level == "plan"

    def test_explicit_autonomy_level(self) -> None:
        state = RunState(run_id="run-1", source="jira", sprint_id="42", autonomy_level="pr")
        assert state.autonomy_level == "pr"

    def test_autonomy_level_persists(self, tmp_path) -> None:
        store = RunStateStore(tmp_path)
        state = store.load_or_create(
            "run-auto", source="jira", sprint_id="42", autonomy_level="execute"
        )
        store.save(state)
        loaded = store.load_or_create("run-auto", source="jira", sprint_id="42")
        assert loaded.autonomy_level == "execute"

    def test_autonomy_serialized_in_json(self, tmp_path) -> None:
        store = RunStateStore(tmp_path)
        state = store.load_or_create(
            "run-json", source="ado", sprint_id="99", autonomy_level="release"
        )
        store.save(state)
        raw = store.path_for("run-json").read_text()
        assert '"autonomy_level": "release"' in raw


# ---------------------------------------------------------------------------
# RunReport — autonomy_level field
# ---------------------------------------------------------------------------


class TestRunReportAutonomy:
    def test_default_autonomy_is_plan(self) -> None:
        report = RunReport(workspace="ws")
        assert report.autonomy_level == "plan"

    def test_explicit_autonomy_level(self) -> None:
        report = RunReport(workspace="ws", autonomy_level="observe")
        assert report.autonomy_level == "observe"

    def test_autonomy_in_json_output(self) -> None:
        report = RunReport(workspace="ws", autonomy_level="pr")
        data = report.model_dump()
        assert data["autonomy_level"] == "pr"


# ---------------------------------------------------------------------------
# Executive report — shows autonomy level
# ---------------------------------------------------------------------------


def test_executive_report_shows_autonomy_level() -> None:
    report = RunReport(workspace="ws", sprint_id="42", autonomy_level="observe")
    markdown = render_executive_report(report)
    assert "Autonomy level: observe" in markdown


def test_executive_report_default_autonomy() -> None:
    report = RunReport(workspace="ws", sprint_id="42")
    markdown = render_executive_report(report)
    assert "Autonomy level: plan" in markdown
