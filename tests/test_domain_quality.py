"""Tests for non-code domain quality gates.

Covers: models, checklist/review/source/risk gates, aggregate runner,
evaluate verdict logic, approval policies, missing input handling,
marketing-style validation, and software gate compatibility.

Issue: #123
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from sendsprint.domain_quality import (
    ApprovalPolicy,
    ChecklistItem,
    DomainCheckType,
    DomainQualityCheck,
    DomainQualityGate,
    ReviewGateInput,
    RiskAssessment,
    SourceEvidence,
)
from sendsprint.quality_gate import (
    CheckSeverity,
    DeliveryQualityGate,
    GateVerdict,
    QualityCheckResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _brand_checklist_check() -> DomainQualityCheck:
    return DomainQualityCheck(
        domain="marketing",
        check_name="brand-checklist",
        check_type=DomainCheckType.checklist,
        required=True,
        details="Brand guidelines compliance",
    )


def _review_check() -> DomainQualityCheck:
    return DomainQualityCheck(
        domain="marketing",
        check_name="marketing-lead-review",
        check_type=DomainCheckType.review,
        required=True,
    )


def _source_check() -> DomainQualityCheck:
    return DomainQualityCheck(
        domain="marketing",
        check_name="evidence-package",
        check_type=DomainCheckType.source,
        required=True,
    )


def _risk_check() -> DomainQualityCheck:
    return DomainQualityCheck(
        domain="marketing",
        check_name="claims-risk",
        check_type=DomainCheckType.risk,
        required=True,
    )


def _all_marketing_checks() -> list[DomainQualityCheck]:
    return [_brand_checklist_check(), _review_check(), _source_check(), _risk_check()]


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------


class TestModels:
    """Model validation and serialization."""

    def test_domain_quality_check_frozen(self) -> None:
        check = _brand_checklist_check()
        with pytest.raises(ValidationError):
            check.domain = "ops"  # type: ignore[misc]

    def test_domain_quality_check_extra_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            DomainQualityCheck(
                domain="marketing",
                check_name="x",
                check_type=DomainCheckType.checklist,
                bogus="nope",  # type: ignore[call-arg]
            )

    def test_check_type_values(self) -> None:
        assert set(DomainCheckType) == {
            DomainCheckType.checklist,
            DomainCheckType.review,
            DomainCheckType.source,
            DomainCheckType.risk,
        }

    def test_approval_policy_defaults(self) -> None:
        policy = ApprovalPolicy()
        assert policy.required_approvals == 1
        assert policy.auto_approve_threshold == 0.0
        assert policy.escalation_path == []
        assert policy.require_explicit_approval_for_external is True

    def test_approval_policy_frozen(self) -> None:
        policy = ApprovalPolicy()
        with pytest.raises(ValidationError):
            policy.required_approvals = 5  # type: ignore[misc]

    def test_checklist_item_defaults(self) -> None:
        item = ChecklistItem(name="test-item")
        assert item.completed is False
        assert item.notes == ""

    def test_risk_assessment_bounds(self) -> None:
        with pytest.raises(ValidationError):
            RiskAssessment(score=101.0)
        with pytest.raises(ValidationError):
            RiskAssessment(score=-1.0)

    def test_source_evidence_defaults(self) -> None:
        ev = SourceEvidence(kind="brief-document")
        assert ev.present is False
        assert ev.uri is None

    def test_serialization_roundtrip(self) -> None:
        check = _brand_checklist_check()
        data = check.model_dump()
        restored = DomainQualityCheck(**data)
        assert restored == check

    def test_approval_policy_serialization(self) -> None:
        policy = ApprovalPolicy(
            required_approvals=2,
            auto_approve_threshold=30.0,
            escalation_path=["marketing-lead", "vp-marketing"],
        )
        data = policy.model_dump()
        restored = ApprovalPolicy(**data)
        assert restored == policy


# ---------------------------------------------------------------------------
# Checklist gate
# ---------------------------------------------------------------------------


class TestChecklistGate:
    """Checklist gate: all items must be completed."""

    def test_all_complete(self) -> None:
        check = _brand_checklist_check()
        items = [
            ChecklistItem(name="logo-usage", completed=True),
            ChecklistItem(name="color-palette", completed=True),
            ChecklistItem(name="font-family", completed=True),
        ]
        result = DomainQualityGate.run_checklist_gate(check, items)
        assert result.passed is True
        assert "3 checklist items" in result.details

    def test_incomplete_items(self) -> None:
        check = _brand_checklist_check()
        items = [
            ChecklistItem(name="logo-usage", completed=True),
            ChecklistItem(name="color-palette", completed=False),
            ChecklistItem(name="font-family", completed=False),
        ]
        result = DomainQualityGate.run_checklist_gate(check, items)
        assert result.passed is False
        assert "color-palette" in result.details
        assert "font-family" in result.details
        assert result.severity == CheckSeverity.blocking

    def test_optional_check_gives_warning(self) -> None:
        check = DomainQualityCheck(
            domain="marketing",
            check_name="nice-to-have",
            check_type=DomainCheckType.checklist,
            required=False,
        )
        items = [ChecklistItem(name="optional-item", completed=False)]
        result = DomainQualityGate.run_checklist_gate(check, items)
        assert result.passed is False
        assert result.severity == CheckSeverity.warning

    def test_empty_checklist_passes(self) -> None:
        check = _brand_checklist_check()
        result = DomainQualityGate.run_checklist_gate(check, [])
        assert result.passed is True


# ---------------------------------------------------------------------------
# Review gate
# ---------------------------------------------------------------------------


class TestReviewGate:
    """Review gate: required approvals must be met."""

    def test_enough_approvals(self) -> None:
        check = _review_check()
        review = ReviewGateInput(approvals=2, reviewers=["alice", "bob"])
        result = DomainQualityGate.run_review_gate(check, review, required_approvals=1)
        assert result.passed is True
        assert "alice" in result.details

    def test_insufficient_approvals(self) -> None:
        check = _review_check()
        review = ReviewGateInput(approvals=0, reviewers=[])
        result = DomainQualityGate.run_review_gate(check, review, required_approvals=2)
        assert result.passed is False
        assert "Need 2" in result.details
        assert "got 0" in result.details

    def test_exact_threshold(self) -> None:
        check = _review_check()
        review = ReviewGateInput(approvals=1, reviewers=["alice"])
        result = DomainQualityGate.run_review_gate(check, review, required_approvals=1)
        assert result.passed is True


# ---------------------------------------------------------------------------
# Source / evidence gate
# ---------------------------------------------------------------------------


class TestSourceGate:
    """Source gate: all evidence items must be present."""

    def test_all_present(self) -> None:
        check = _source_check()
        evidence = [
            SourceEvidence(kind="brief-document", present=True, uri="/docs/brief.pdf"),
            SourceEvidence(kind="approval-notes", present=True),
        ]
        result = DomainQualityGate.run_source_gate(check, evidence)
        assert result.passed is True
        assert "2 evidence items" in result.details

    def test_missing_evidence(self) -> None:
        check = _source_check()
        evidence = [
            SourceEvidence(kind="brief-document", present=True),
            SourceEvidence(kind="approval-notes", present=False),
            SourceEvidence(kind="screenshot", present=False),
        ]
        result = DomainQualityGate.run_source_gate(check, evidence)
        assert result.passed is False
        assert "approval-notes" in result.details
        assert "screenshot" in result.details

    def test_empty_evidence_list_passes(self) -> None:
        check = _source_check()
        result = DomainQualityGate.run_source_gate(check, [])
        assert result.passed is True


# ---------------------------------------------------------------------------
# Risk gate
# ---------------------------------------------------------------------------


class TestRiskGate:
    """Risk gate: score must be below threshold."""

    def test_below_threshold(self) -> None:
        check = _risk_check()
        assessment = RiskAssessment(score=20.0, factors=["minor-claim"])
        result = DomainQualityGate.run_risk_gate(check, assessment, threshold=50.0)
        assert result.passed is True
        assert "20.0" in result.details

    def test_above_threshold(self) -> None:
        check = _risk_check()
        assessment = RiskAssessment(score=75.0, factors=["unverified-claim", "legal-risk"])
        result = DomainQualityGate.run_risk_gate(check, assessment, threshold=50.0)
        assert result.passed is False
        assert "75.0" in result.details
        assert "unverified-claim" in result.details

    def test_exact_threshold_passes(self) -> None:
        check = _risk_check()
        assessment = RiskAssessment(score=50.0)
        result = DomainQualityGate.run_risk_gate(check, assessment, threshold=50.0)
        assert result.passed is True

    def test_custom_threshold(self) -> None:
        check = _risk_check()
        assessment = RiskAssessment(score=25.0)
        result = DomainQualityGate.run_risk_gate(check, assessment, threshold=20.0)
        assert result.passed is False


# ---------------------------------------------------------------------------
# Aggregate runner
# ---------------------------------------------------------------------------


class TestRunDomainChecks:
    """run_domain_checks aggregates all registered checks."""

    def test_all_pass(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks(_all_marketing_checks())
        results = gate.run_domain_checks(
            checklists={"brand-checklist": [ChecklistItem(name="a", completed=True)]},
            reviews={"marketing-lead-review": ReviewGateInput(approvals=1, reviewers=["alice"])},
            sources={"evidence-package": [SourceEvidence(kind="brief", present=True)]},
            risks={"claims-risk": RiskAssessment(score=10.0)},
        )
        assert all(r.passed for r in results)
        assert len(results) == 4

    def test_missing_input_fails(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks(_all_marketing_checks())
        results = gate.run_domain_checks()  # no inputs at all
        assert len(results) == 4
        assert all(not r.passed for r in results)
        assert "No checklist items provided" in results[0].details
        assert "No review input provided" in results[1].details
        assert "No evidence items provided" in results[2].details
        assert "No risk assessment provided" in results[3].details

    def test_partial_input(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks(_all_marketing_checks())
        results = gate.run_domain_checks(
            checklists={"brand-checklist": [ChecklistItem(name="a", completed=True)]},
        )
        assert results[0].passed is True  # checklist ok
        assert results[1].passed is False  # review missing
        assert results[2].passed is False  # source missing
        assert results[3].passed is False  # risk missing

    def test_no_checks_registered(self) -> None:
        gate = DomainQualityGate(domain="ops")
        results = gate.run_domain_checks()
        assert results == []


# ---------------------------------------------------------------------------
# Evaluate verdict
# ---------------------------------------------------------------------------


class TestEvaluate:
    """evaluate() produces correct GateReport verdicts."""

    def test_all_pass_verdict(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_brand_checklist_check()])
        report = gate.evaluate(
            checklists={"brand-checklist": [ChecklistItem(name="a", completed=True)]},
        )
        assert report.verdict == GateVerdict.passed
        assert report.reasons == []

    def test_blocking_failure_needs_rework(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_brand_checklist_check()])
        report = gate.evaluate(
            checklists={"brand-checklist": [ChecklistItem(name="a", completed=False)]},
        )
        assert report.verdict == GateVerdict.needs_rework
        assert len(report.reasons) == 1

    def test_warning_failure_needs_human_approval(self) -> None:
        optional_check = DomainQualityCheck(
            domain="ops",
            check_name="optional-review",
            check_type=DomainCheckType.checklist,
            required=False,
        )
        gate = DomainQualityGate(domain="ops")
        gate.register_checks([optional_check])
        report = gate.evaluate(
            checklists={"optional-review": [ChecklistItem(name="nice", completed=False)]},
        )
        assert report.verdict == GateVerdict.needs_human_approval

    def test_external_facing_requires_approval(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_brand_checklist_check()])
        report = gate.evaluate(
            checklists={"brand-checklist": [ChecklistItem(name="a", completed=True)]},
            is_external_facing=True,
        )
        assert report.verdict == GateVerdict.needs_human_approval
        assert any("External-facing" in r for r in report.reasons)

    def test_external_facing_no_block_when_policy_allows(self) -> None:
        policy = ApprovalPolicy(require_explicit_approval_for_external=False)
        gate = DomainQualityGate(domain="internal-ops", approval_policy=policy)
        gate.register_checks([_brand_checklist_check()])
        report = gate.evaluate(
            checklists={"brand-checklist": [ChecklistItem(name="a", completed=True)]},
            is_external_facing=True,
        )
        assert report.verdict == GateVerdict.passed

    def test_pre_supplied_checks(self) -> None:
        """evaluate() accepts pre-computed check results."""
        gate = DomainQualityGate(domain="design")
        pre = [
            QualityCheckResult(check_name="mockup-review", passed=True),
            QualityCheckResult(
                check_name="a11y-audit",
                passed=False,
                severity=CheckSeverity.error,
                details="contrast ratio too low",
            ),
        ]
        report = gate.evaluate(checks=pre)
        assert report.verdict == GateVerdict.needs_rework

    def test_empty_checks_pass(self) -> None:
        gate = DomainQualityGate(domain="minimal")
        report = gate.evaluate()
        assert report.verdict == GateVerdict.passed


# ---------------------------------------------------------------------------
# Approval policy scenarios
# ---------------------------------------------------------------------------


class TestApprovalPolicy:
    """ApprovalPolicy model edge cases."""

    def test_zero_approvals_allowed(self) -> None:
        policy = ApprovalPolicy(required_approvals=0)
        assert policy.required_approvals == 0

    def test_escalation_path(self) -> None:
        policy = ApprovalPolicy(
            required_approvals=2,
            escalation_path=["team-lead", "director", "vp"],
        )
        assert len(policy.escalation_path) == 3

    def test_auto_approve_threshold(self) -> None:
        policy = ApprovalPolicy(auto_approve_threshold=30.0)
        assert policy.auto_approve_threshold == 30.0

    def test_threshold_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ApprovalPolicy(auto_approve_threshold=101.0)
        with pytest.raises(ValidationError):
            ApprovalPolicy(auto_approve_threshold=-1.0)


# ---------------------------------------------------------------------------
# Marketing-style full validation
# ---------------------------------------------------------------------------


class TestMarketingValidation:
    """Integration: marketing domain quality checks end-to-end."""

    def _marketing_gate(self) -> DomainQualityGate:
        policy = ApprovalPolicy(
            required_approvals=1,
            escalation_path=["marketing-lead"],
            require_explicit_approval_for_external=True,
        )
        gate = DomainQualityGate(domain="marketing", approval_policy=policy)
        gate.register_checks(
            [
                DomainQualityCheck(
                    domain="marketing",
                    check_name="brand-review",
                    check_type=DomainCheckType.checklist,
                    required=True,
                ),
                DomainQualityCheck(
                    domain="marketing",
                    check_name="lead-approval",
                    check_type=DomainCheckType.review,
                    required=True,
                ),
                DomainQualityCheck(
                    domain="marketing",
                    check_name="campaign-evidence",
                    check_type=DomainCheckType.source,
                    required=True,
                ),
                DomainQualityCheck(
                    domain="marketing",
                    check_name="claims-risk-score",
                    check_type=DomainCheckType.risk,
                    required=True,
                ),
            ]
        )
        return gate

    def test_marketing_all_pass_internal(self) -> None:
        gate = self._marketing_gate()
        report = gate.evaluate(
            checklists={
                "brand-review": [
                    ChecklistItem(name="logo", completed=True),
                    ChecklistItem(name="colors", completed=True),
                ]
            },
            reviews={"lead-approval": ReviewGateInput(approvals=1, reviewers=["alice"])},
            sources={
                "campaign-evidence": [
                    SourceEvidence(kind="brief", present=True),
                    SourceEvidence(kind="screenshot", present=True),
                ]
            },
            risks={"claims-risk-score": RiskAssessment(score=15.0, factors=["low-risk-claim"])},
            is_external_facing=False,
        )
        assert report.verdict == GateVerdict.passed

    def test_marketing_all_pass_external_needs_approval(self) -> None:
        gate = self._marketing_gate()
        report = gate.evaluate(
            checklists={"brand-review": [ChecklistItem(name="logo", completed=True)]},
            reviews={"lead-approval": ReviewGateInput(approvals=1, reviewers=["alice"])},
            sources={"campaign-evidence": [SourceEvidence(kind="brief", present=True)]},
            risks={"claims-risk-score": RiskAssessment(score=10.0)},
            is_external_facing=True,
        )
        assert report.verdict == GateVerdict.needs_human_approval

    def test_marketing_missing_evidence_blocks(self) -> None:
        gate = self._marketing_gate()
        report = gate.evaluate(
            checklists={"brand-review": [ChecklistItem(name="logo", completed=True)]},
            reviews={"lead-approval": ReviewGateInput(approvals=1, reviewers=["alice"])},
            sources={
                "campaign-evidence": [
                    SourceEvidence(kind="brief", present=True),
                    SourceEvidence(kind="approval-notes", present=False),
                ]
            },
            risks={"claims-risk-score": RiskAssessment(score=10.0)},
        )
        assert report.verdict == GateVerdict.needs_rework
        assert any("approval-notes" in r for r in report.reasons)

    def test_marketing_high_risk_blocks(self) -> None:
        gate = self._marketing_gate()
        report = gate.evaluate(
            checklists={"brand-review": [ChecklistItem(name="logo", completed=True)]},
            reviews={"lead-approval": ReviewGateInput(approvals=1, reviewers=["alice"])},
            sources={"campaign-evidence": [SourceEvidence(kind="brief", present=True)]},
            risks={
                "claims-risk-score": RiskAssessment(
                    score=80.0,
                    factors=["unverified-health-claim", "regulatory-risk"],
                )
            },
        )
        assert report.verdict == GateVerdict.needs_rework
        assert any("80.0" in r for r in report.reasons)


# ---------------------------------------------------------------------------
# Software gate compatibility
# ---------------------------------------------------------------------------


class TestSoftwareGateCompatibility:
    """Existing DeliveryQualityGate is unchanged and compatible."""

    def test_software_gate_still_works(self) -> None:
        """DeliveryQualityGate can evaluate pre-supplied checks unchanged."""
        from sendsprint.policy import AutonomyPolicy

        gate = DeliveryQualityGate(
            policy=AutonomyPolicy(level="plan"),
        )
        checks = [
            QualityCheckResult(check_name="lint", passed=True),
            QualityCheckResult(check_name="tests", passed=True),
            QualityCheckResult(check_name="security", passed=True),
            QualityCheckResult(check_name="coverage", passed=True),
            QualityCheckResult(check_name="playwright", passed=True),
            QualityCheckResult(check_name="diff-hygiene", passed=True),
        ]
        report = gate.evaluate(checks=checks)
        assert report.verdict == GateVerdict.passed

    def test_gate_report_shared_model(self) -> None:
        """Both gates produce GateReport with the same structure."""
        domain_gate = DomainQualityGate(domain="ops")
        domain_report = domain_gate.evaluate()

        assert hasattr(domain_report, "verdict")
        assert hasattr(domain_report, "checks")
        assert hasattr(domain_report, "reasons")
        assert hasattr(domain_report, "created_at")


# ---------------------------------------------------------------------------
# Snapshot tests for readiness/error messages
# ---------------------------------------------------------------------------


class TestMessageSnapshots:
    """Verify actionable error message content."""

    def test_missing_checklist_message(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_brand_checklist_check()])
        results = gate.run_domain_checks()
        assert results[0].details == "No checklist items provided for 'brand-checklist'"

    def test_missing_review_message(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_review_check()])
        results = gate.run_domain_checks()
        assert results[0].details == "No review input provided for 'marketing-lead-review'"

    def test_missing_source_message(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_source_check()])
        results = gate.run_domain_checks()
        assert results[0].details == "No evidence items provided for 'evidence-package'"

    def test_missing_risk_message(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_risk_check()])
        results = gate.run_domain_checks()
        assert results[0].details == "No risk assessment provided for 'claims-risk'"

    def test_incomplete_checklist_message(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_brand_checklist_check()])
        results = gate.run_domain_checks(
            checklists={
                "brand-checklist": [
                    ChecklistItem(name="logo-usage", completed=False),
                    ChecklistItem(name="color-palette", completed=False),
                ]
            },
        )
        assert results[0].details == "Incomplete items: logo-usage, color-palette"

    def test_insufficient_approvals_message(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_review_check()])
        results = gate.run_domain_checks(
            reviews={"marketing-lead-review": ReviewGateInput(approvals=0)},
        )
        assert results[0].details == "Need 1 approval(s), got 0"

    def test_missing_evidence_message(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_source_check()])
        results = gate.run_domain_checks(
            sources={
                "evidence-package": [
                    SourceEvidence(kind="brief-document", present=False),
                ]
            },
        )
        assert results[0].details == "Missing evidence: brief-document"

    def test_high_risk_message(self) -> None:
        gate = DomainQualityGate(domain="marketing")
        gate.register_checks([_risk_check()])
        results = gate.run_domain_checks(
            risks={"claims-risk": RiskAssessment(score=75.0, factors=["legal-risk"])},
        )
        assert "75.0 exceeds threshold 50.0" in results[0].details
        assert "legal-risk" in results[0].details
