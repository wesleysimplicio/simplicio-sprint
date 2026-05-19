from sendsprint.risk_policy import classify_risk


def test_classify_risk_marks_docs_only_changes() -> None:
    decision = classify_risk(changed_files=["README.md", "docs/setup.md"])
    assert decision.risk == "docs-only"
    assert decision.budget.max_cost_usd == 1


def test_classify_risk_marks_security_changes_critical() -> None:
    decision = classify_risk(
        issue_text="rotate auth token safely", changed_files=["auth/service.py"]
    )
    assert decision.risk == "critical"
    assert decision.requires_human_review is True
