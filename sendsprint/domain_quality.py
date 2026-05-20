"""Non-code domain quality gates -- checklists, review gates, source/evidence
requirements, risk scoring, and approval policies for domains like marketing,
ops, compliance, and design.

Software quality gates (DeliveryQualityGate) remain unchanged.

Issue: #123
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.quality_gate import (
    CheckSeverity,
    GateReport,
    GateVerdict,
    QualityCheckResult,
)

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class DomainCheckType(StrEnum):
    """Kind of quality check a domain gate can run."""

    checklist = "checklist"
    review = "review"
    source = "source"
    risk = "risk"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DomainQualityCheck(BaseModel):
    """A single domain-specific quality check definition."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    domain: str = Field(..., description="Domain this check belongs to, e.g. 'marketing'")
    check_name: str = Field(..., description="Machine-readable check identifier")
    check_type: DomainCheckType = Field(..., description="What kind of gate this check represents")
    required: bool = Field(default=True, description="Whether this check blocks readiness")
    details: str = Field(default="", description="Human-readable description of the check")


class ChecklistItem(BaseModel):
    """A single item in a checklist gate."""

    model_config = ConfigDict(extra="forbid")

    name: str
    completed: bool = False
    notes: str = ""


class ReviewGateInput(BaseModel):
    """Input for a review-type gate."""

    model_config = ConfigDict(extra="forbid")

    approvals: int = Field(default=0, ge=0)
    reviewers: list[str] = Field(default_factory=list)


class SourceEvidence(BaseModel):
    """A piece of evidence for a source-type gate."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(..., description="Evidence type, e.g. 'brief-document', 'screenshot'")
    present: bool = False
    uri: str | None = None
    notes: str = ""


class RiskAssessment(BaseModel):
    """Input for a risk-type gate."""

    model_config = ConfigDict(extra="forbid")

    score: float = Field(default=0.0, ge=0.0, le=100.0, description="Risk score 0-100")
    factors: list[str] = Field(default_factory=list)
    mitigations: list[str] = Field(default_factory=list)


class ApprovalPolicy(BaseModel):
    """Policy governing publication / release approval for domain work."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    required_approvals: int = Field(default=1, ge=0)
    auto_approve_threshold: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Risk score at or below which auto-approval is allowed",
    )
    escalation_path: list[str] = Field(
        default_factory=list,
        description="Ordered list of roles/people to escalate to when approval is needed",
    )
    require_explicit_approval_for_external: bool = Field(
        default=True,
        description="External-facing work always requires explicit approval",
    )


# ---------------------------------------------------------------------------
# DomainQualityGate
# ---------------------------------------------------------------------------


class DomainQualityGate:
    """Quality gate for non-code domain work.

    Evaluates checklists, review approvals, source/evidence presence, and
    risk scores to produce a pass / needs_rework / needs_human_approval
    verdict compatible with :class:`GateReport`.

    Parameters
    ----------
    domain:
        Domain name (e.g. ``"marketing"``, ``"ops"``).
    approval_policy:
        Publication approval policy.  Defaults to requiring 1 approval and
        explicit approval for external-facing work.
    """

    def __init__(
        self,
        domain: str = "generic",
        approval_policy: ApprovalPolicy | None = None,
    ) -> None:
        self.domain = domain
        self.approval_policy = approval_policy or ApprovalPolicy()
        self._checks: list[DomainQualityCheck] = []

    # -- registration -------------------------------------------------------

    def register_checks(self, checks: list[DomainQualityCheck]) -> None:
        """Register domain-specific checks to be evaluated."""
        self._checks.extend(checks)

    @property
    def registered_checks(self) -> list[DomainQualityCheck]:
        return list(self._checks)

    # -- individual gate runners --------------------------------------------

    @staticmethod
    def run_checklist_gate(
        check: DomainQualityCheck,
        items: list[ChecklistItem],
    ) -> QualityCheckResult:
        """Evaluate a checklist gate: all required items must be completed."""
        incomplete = [item.name for item in items if not item.completed]
        if incomplete:
            return QualityCheckResult(
                check_name=check.check_name,
                passed=False,
                details=f"Incomplete items: {', '.join(incomplete[:10])}",
                severity=CheckSeverity.blocking if check.required else CheckSeverity.warning,
            )
        return QualityCheckResult(
            check_name=check.check_name,
            passed=True,
            details=f"All {len(items)} checklist items completed",
        )

    @staticmethod
    def run_review_gate(
        check: DomainQualityCheck,
        review_input: ReviewGateInput,
        required_approvals: int = 1,
    ) -> QualityCheckResult:
        """Evaluate a review gate: required approvals must be met."""
        if review_input.approvals < required_approvals:
            return QualityCheckResult(
                check_name=check.check_name,
                passed=False,
                details=(f"Need {required_approvals} approval(s), got {review_input.approvals}"),
                severity=CheckSeverity.blocking if check.required else CheckSeverity.warning,
            )
        return QualityCheckResult(
            check_name=check.check_name,
            passed=True,
            details=(
                f"{review_input.approvals} approval(s) obtained from: "
                f"{', '.join(review_input.reviewers)}"
            ),
        )

    @staticmethod
    def run_source_gate(
        check: DomainQualityCheck,
        evidence_items: list[SourceEvidence],
    ) -> QualityCheckResult:
        """Evaluate a source/evidence gate: all items must be present."""
        missing = [item.kind for item in evidence_items if not item.present]
        if missing:
            return QualityCheckResult(
                check_name=check.check_name,
                passed=False,
                details=f"Missing evidence: {', '.join(missing[:10])}",
                severity=CheckSeverity.blocking if check.required else CheckSeverity.warning,
            )
        return QualityCheckResult(
            check_name=check.check_name,
            passed=True,
            details=f"All {len(evidence_items)} evidence items present",
        )

    @staticmethod
    def run_risk_gate(
        check: DomainQualityCheck,
        assessment: RiskAssessment,
        threshold: float = 50.0,
    ) -> QualityCheckResult:
        """Evaluate a risk gate: risk score must be below threshold."""
        if assessment.score > threshold:
            return QualityCheckResult(
                check_name=check.check_name,
                passed=False,
                details=(
                    f"Risk score {assessment.score:.1f} exceeds threshold {threshold:.1f}. "
                    f"Factors: {', '.join(assessment.factors[:5])}"
                ),
                severity=CheckSeverity.blocking if check.required else CheckSeverity.warning,
            )
        return QualityCheckResult(
            check_name=check.check_name,
            passed=True,
            details=f"Risk score {assessment.score:.1f} within threshold {threshold:.1f}",
        )

    # -- aggregate runner ---------------------------------------------------

    def run_domain_checks(
        self,
        *,
        checklists: dict[str, list[ChecklistItem]] | None = None,
        reviews: dict[str, ReviewGateInput] | None = None,
        sources: dict[str, list[SourceEvidence]] | None = None,
        risks: dict[str, RiskAssessment] | None = None,
        risk_threshold: float = 50.0,
    ) -> list[QualityCheckResult]:
        """Run all registered checks with provided inputs.

        Keys in the input dicts must match ``check_name`` of registered checks.
        Checks without matching input are reported as failed with an actionable
        reason.
        """
        checklists = checklists or {}
        reviews = reviews or {}
        sources = sources or {}
        risks = risks or {}
        results: list[QualityCheckResult] = []

        for check in self._checks:
            if check.check_type == DomainCheckType.checklist:
                items = checklists.get(check.check_name)
                if items is None:
                    results.append(
                        QualityCheckResult(
                            check_name=check.check_name,
                            passed=False,
                            details=f"No checklist items provided for '{check.check_name}'",
                            severity=CheckSeverity.blocking
                            if check.required
                            else CheckSeverity.warning,
                        )
                    )
                else:
                    results.append(self.run_checklist_gate(check, items))

            elif check.check_type == DomainCheckType.review:
                review_input = reviews.get(check.check_name)
                if review_input is None:
                    results.append(
                        QualityCheckResult(
                            check_name=check.check_name,
                            passed=False,
                            details=f"No review input provided for '{check.check_name}'",
                            severity=CheckSeverity.blocking
                            if check.required
                            else CheckSeverity.warning,
                        )
                    )
                else:
                    results.append(
                        self.run_review_gate(
                            check,
                            review_input,
                            required_approvals=self.approval_policy.required_approvals,
                        )
                    )

            elif check.check_type == DomainCheckType.source:
                evidence = sources.get(check.check_name)
                if evidence is None:
                    results.append(
                        QualityCheckResult(
                            check_name=check.check_name,
                            passed=False,
                            details=f"No evidence items provided for '{check.check_name}'",
                            severity=CheckSeverity.blocking
                            if check.required
                            else CheckSeverity.warning,
                        )
                    )
                else:
                    results.append(self.run_source_gate(check, evidence))

            elif check.check_type == DomainCheckType.risk:
                assessment = risks.get(check.check_name)
                if assessment is None:
                    results.append(
                        QualityCheckResult(
                            check_name=check.check_name,
                            passed=False,
                            details=f"No risk assessment provided for '{check.check_name}'",
                            severity=CheckSeverity.blocking
                            if check.required
                            else CheckSeverity.warning,
                        )
                    )
                else:
                    results.append(self.run_risk_gate(check, assessment, threshold=risk_threshold))

        return results

    # -- verdict ------------------------------------------------------------

    def evaluate(
        self,
        checks: list[QualityCheckResult] | None = None,
        *,
        checklists: dict[str, list[ChecklistItem]] | None = None,
        reviews: dict[str, ReviewGateInput] | None = None,
        sources: dict[str, list[SourceEvidence]] | None = None,
        risks: dict[str, RiskAssessment] | None = None,
        risk_threshold: float = 50.0,
        is_external_facing: bool = False,
    ) -> GateReport:
        """Evaluate all checks and produce a :class:`GateReport`.

        Decision logic (mirrors :meth:`DeliveryQualityGate.evaluate`):

        - Any *blocking* failure -> ``needs_rework``
        - Any *error* failure -> ``needs_rework``
        - Any *warning* failure -> ``needs_human_approval``
        - All pass + external-facing + policy requires explicit approval
          -> ``needs_human_approval``
        - All pass -> ``pass``
        """
        results = (
            checks
            if checks is not None
            else self.run_domain_checks(
                checklists=checklists,
                reviews=reviews,
                sources=sources,
                risks=risks,
                risk_threshold=risk_threshold,
            )
        )

        reasons: list[str] = []
        has_blocking = False
        has_error = False
        has_warning = False

        for check in results:
            if check.passed:
                continue
            reasons.append(f"{check.check_name}: {check.details[:200]}")
            if check.severity == CheckSeverity.blocking:
                has_blocking = True
            elif check.severity == CheckSeverity.error:
                has_error = True
            elif check.severity == CheckSeverity.warning:
                has_warning = True

        if has_blocking or has_error:
            verdict = GateVerdict.needs_rework
        elif has_warning:
            verdict = GateVerdict.needs_human_approval
        elif is_external_facing and self.approval_policy.require_explicit_approval_for_external:
            reasons.append("External-facing work requires explicit approval per policy")
            verdict = GateVerdict.needs_human_approval
        else:
            verdict = GateVerdict.passed

        return GateReport(verdict=verdict, checks=results, reasons=reasons)
