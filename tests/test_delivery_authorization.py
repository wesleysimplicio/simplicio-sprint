from sendsprint.delivery_authorization import ProjectProfile, authorize_action


def test_authorize_action_auto_approves_low_risk_allowed_actions() -> None:
    profile = ProjectProfile(
        company="Acme",
        organization="acme",
        repository="repo",
        allowed_actions=["write-files", "commit"],
        default_reviewers=["lead"],
    )
    checkpoint = authorize_action(profile=profile, action="commit", risk="low")
    assert checkpoint.approved is True
    assert checkpoint.mode == "auto"


def test_authorize_action_requires_manual_for_high_risk_or_disallowed() -> None:
    profile = ProjectProfile(
        company="Acme",
        organization="acme",
        repository="repo",
        allowed_actions=["write-files", "commit"],
    )
    blocked = authorize_action(profile=profile, action="push", risk="low")
    assert blocked.approved is False
    high_risk = authorize_action(profile=profile, action="commit", risk="high")
    assert high_risk.approved is False
    assert high_risk.mode == "manual"
