"""Tests for central autonomy policy."""

from __future__ import annotations

import pytest

from sendsprint.policy import AutonomyDenied, AutonomyPolicy, parse_autonomy_level


def test_plan_policy_blocks_side_effects() -> None:
    policy = AutonomyPolicy(level="plan")
    assert policy.allows("plan") is True
    assert policy.allows("push") is False
    with pytest.raises(AutonomyDenied):
        policy.require("create-pr")


def test_pr_policy_allows_issue_updates_but_not_release() -> None:
    policy = AutonomyPolicy(level="pr")
    assert policy.allows("comment-issue") is True
    assert policy.allows("close-issue") is True
    assert policy.allows("publish-release") is False


def test_parse_autonomy_level_rejects_unknown() -> None:
    assert parse_autonomy_level("deploy-callback") == "deploy-callback"
    with pytest.raises(ValueError):
        parse_autonomy_level("chaos")
