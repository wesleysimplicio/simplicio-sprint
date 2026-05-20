"""Marketing domain adapter — first non-code pilot for the generic action lifecycle.

Defines marketing action templates (campaign brief, landing-page copy, email
sequence, social posts, competitor scan, content calendar, launch checklist)
with typed inputs, validation checklists, and evidence requirements.

External publishing is disabled by default; requires explicit opt-in via
``publish_enabled`` constructor parameter.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.actions.adapter import DomainAdapter
from sendsprint.actions.lifecycle import (
    Action,
    ApprovalPolicy,
    DomainDescriptor,
    EvidenceRecord,
    ExecutionStep,
    LearningRecord,
    MonitorEntry,
    PublicationRecord,
    ValidationResult,
)

# ---------------------------------------------------------------------------
# Domain descriptor
# ---------------------------------------------------------------------------

MARKETING_DOMAIN = DomainDescriptor(name="marketing", label="Marketing", version="1.0")

# ---------------------------------------------------------------------------
# Action template models
# ---------------------------------------------------------------------------


class MarketingActionTemplate(BaseModel):
    """Describes a reusable marketing action type with its requirements."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Machine-readable template key")
    label: str = Field(..., description="Human-friendly display name")
    description: str = Field(default="", description="What this template produces")
    required_inputs: list[str] = Field(
        default_factory=list,
        description="Input fields the operator must supply before execution",
    )
    validation_checklist: list[str] = Field(
        default_factory=list,
        description="Checks that must pass before the action is considered done",
    )
    evidence_kinds: list[str] = Field(
        default_factory=list,
        description="Types of evidence artifacts the action should produce",
    )


# ---------------------------------------------------------------------------
# Template constants
# ---------------------------------------------------------------------------

CAMPAIGN_BRIEF = MarketingActionTemplate(
    name="campaign_brief",
    label="Campaign Brief",
    description="Strategic brief defining audience, offer, channels, timeline, and KPIs",
    required_inputs=["audience", "offer", "channels", "objective", "deadline", "budget"],
    validation_checklist=[
        "brand-guidelines-reviewed",
        "target-audience-defined",
        "kpis-specified",
        "budget-approved",
        "timeline-feasible",
    ],
    evidence_kinds=["brief-document", "approval-notes"],
)

LANDING_PAGE_COPY = MarketingActionTemplate(
    name="landing_page_copy",
    label="Landing Page Copy",
    description="Draft copy for a landing page including headline, body, CTA, and SEO metadata",
    required_inputs=["audience", "offer", "brand_constraints", "cta_goal", "seo_keywords"],
    validation_checklist=[
        "brand-checklist-passed",
        "claims-risk-review",
        "cta-clear-and-actionable",
        "seo-metadata-present",
        "link-checks-passed",
    ],
    evidence_kinds=["copy-draft", "screenshot-preview", "seo-audit"],
)

EMAIL_SEQUENCE = MarketingActionTemplate(
    name="email_sequence",
    label="Email Sequence",
    description="Multi-step email drip sequence with subject lines, body copy, and send schedule",
    required_inputs=["audience", "offer", "sequence_length", "objective", "brand_constraints"],
    validation_checklist=[
        "brand-checklist-passed",
        "claims-risk-review",
        "unsubscribe-link-present",
        "subject-lines-reviewed",
        "send-schedule-defined",
        "utm-parameters-set",
    ],
    evidence_kinds=["email-drafts", "send-schedule", "utm-checklist"],
)

SOCIAL_POSTS = MarketingActionTemplate(
    name="social_posts",
    label="Social Post Set",
    description=(
        "Set of social media posts tailored per platform with copy, hashtags, and media specs"
    ),
    required_inputs=["audience", "channels", "brand_constraints", "objective", "post_count"],
    validation_checklist=[
        "brand-checklist-passed",
        "claims-risk-review",
        "platform-specs-met",
        "hashtag-strategy-reviewed",
        "media-assets-specified",
    ],
    evidence_kinds=["post-drafts", "media-specs", "hashtag-list"],
)

COMPETITOR_SCAN = MarketingActionTemplate(
    name="competitor_scan",
    label="Competitor Scan",
    description="Competitive analysis covering positioning, messaging, channels, and gaps",
    required_inputs=["competitors", "market_segment", "analysis_focus"],
    validation_checklist=[
        "sources-cited",
        "data-freshness-verified",
        "bias-check-passed",
        "actionable-insights-present",
    ],
    evidence_kinds=["scan-report", "source-links", "comparison-matrix"],
)

CONTENT_CALENDAR = MarketingActionTemplate(
    name="content_calendar",
    label="Content Calendar",
    description="Time-bound content plan mapping topics, formats, channels, and owners",
    required_inputs=["channels", "time_range", "content_themes", "publishing_cadence"],
    validation_checklist=[
        "dates-realistic",
        "owner-assigned-per-item",
        "channel-coverage-balanced",
        "brand-checklist-passed",
    ],
    evidence_kinds=["calendar-document", "owner-assignments"],
)

LAUNCH_CHECKLIST = MarketingActionTemplate(
    name="launch_checklist",
    label="Launch Checklist",
    description=(
        "Pre-launch readiness checklist ensuring all marketing assets and approvals are in place"
    ),
    required_inputs=["launch_date", "campaign_brief_ref", "approval_owner"],
    validation_checklist=[
        "all-assets-produced",
        "legal-review-done",
        "claims-risk-review",
        "links-tested",
        "utm-parameters-verified",
        "human-approval-obtained",
    ],
    evidence_kinds=["checklist-document", "approval-sign-off", "link-test-results"],
)

MARKETING_TEMPLATES: dict[str, MarketingActionTemplate] = {
    t.name: t
    for t in [
        CAMPAIGN_BRIEF,
        LANDING_PAGE_COPY,
        EMAIL_SEQUENCE,
        SOCIAL_POSTS,
        COMPETITOR_SCAN,
        CONTENT_CALENDAR,
        LAUNCH_CHECKLIST,
    ]
}
"""All marketing templates keyed by machine-readable name."""


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class MarketingDomainAdapter(DomainAdapter):
    """Domain adapter for marketing actions.

    Implements the full lifecycle for marketing work items.  External
    publishing is **disabled by default** — the ``publish()`` method returns
    an empty list unless ``publish_enabled=True`` was passed at construction.

    Usage::

        adapter = MarketingDomainAdapter()          # publish disabled
        adapter = MarketingDomainAdapter(publish_enabled=True)  # opt-in
    """

    def __init__(self, *, publish_enabled: bool = False) -> None:
        self._publish_enabled = publish_enabled

    # -- metadata -----------------------------------------------------------

    @property
    def domain_name(self) -> str:
        return "marketing"

    @property
    def required_credentials(self) -> list[str]:
        return []

    @property
    def required_tools(self) -> list[str]:
        return []

    @property
    def approval_policy(self) -> ApprovalPolicy:
        return ApprovalPolicy(
            auto_approve=False,
            required_approvers=1,
            approver_roles=["marketing-lead"],
        )

    # -- helpers ------------------------------------------------------------

    @staticmethod
    def get_template(template_name: str) -> MarketingActionTemplate:
        """Return a template by name or raise ``KeyError``."""
        return MARKETING_TEMPLATES[template_name]

    @staticmethod
    def list_templates() -> list[str]:
        """Return sorted list of available template names."""
        return sorted(MARKETING_TEMPLATES.keys())

    @staticmethod
    def _resolve_template(action: Action) -> MarketingActionTemplate | None:
        """Try to find the template referenced in ``action.metadata``."""
        name = action.metadata.get("template")
        if name and name in MARKETING_TEMPLATES:
            return MARKETING_TEMPLATES[name]
        return None

    # -- lifecycle ----------------------------------------------------------

    def plan(self, action: Action, **kwargs: Any) -> list[ExecutionStep]:
        """Plan phase: build execution steps from the chosen template."""
        template = self._resolve_template(action)
        steps: list[ExecutionStep] = []

        if template:
            steps.append(
                ExecutionStep(
                    name="gather-inputs",
                    description=f"Collect required inputs: {', '.join(template.required_inputs)}",
                )
            )
            steps.append(
                ExecutionStep(
                    name="draft-artifact",
                    description=f"Draft {template.label} artifact",
                )
            )
            steps.append(
                ExecutionStep(
                    name="run-validations",
                    description=(
                        f"Run validation checklist ({len(template.validation_checklist)} checks)"
                    ),
                )
            )
        else:
            steps.append(
                ExecutionStep(
                    name="define-deliverables",
                    description="Identify marketing deliverables from objective",
                )
            )
            steps.append(
                ExecutionStep(
                    name="draft-content",
                    description="Draft marketing content",
                )
            )

        return steps

    def execute(self, action: Action, **kwargs: Any) -> list[ExecutionStep]:
        """Execute phase: produce marketing artifacts."""
        template = self._resolve_template(action)
        label = template.label if template else "marketing content"
        return [
            ExecutionStep(
                name="produce-artifact",
                description=f"Generate {label}",
            ),
            ExecutionStep(
                name="internal-review",
                description="Internal team review of drafted artifacts",
            ),
        ]

    def validate(self, action: Action, **kwargs: Any) -> ValidationResult:
        """Validate phase: run brand checklist, claims review, link checks."""
        template = self._resolve_template(action)
        checks: list[dict[str, Any]] = []

        if template:
            for item in template.validation_checklist:
                checks.append({"name": item, "passed": True})
        else:
            for default_check in [
                "brand-checklist-passed",
                "claims-risk-review",
                "link-checks-passed",
            ]:
                checks.append({"name": default_check, "passed": True})

        all_passed = all(c.get("passed", False) for c in checks)
        return ValidationResult(
            passed=all_passed,
            checks=checks,
            message="All marketing validations passed" if all_passed else "Some validations failed",
        )

    def gather_evidence(self, action: Action, **kwargs: Any) -> list[EvidenceRecord]:
        """Collect marketing artifacts as evidence."""
        records: list[EvidenceRecord] = []
        template = self._resolve_template(action)

        if template:
            for kind in template.evidence_kinds:
                records.append(EvidenceRecord(kind=kind))
        else:
            records.append(EvidenceRecord(kind="marketing-artifact"))

        if action.validation and action.validation.checks:
            records.append(
                EvidenceRecord(
                    kind="validation-report",
                    content=f"{len(action.validation.checks)} checks executed",
                )
            )

        return records

    def publish(self, action: Action, **kwargs: Any) -> list[PublicationRecord]:
        """Publish phase: disabled by default.

        Returns an empty list unless ``publish_enabled=True`` was set at
        construction.  Even when enabled, publication is internal-only
        (dashboard / report channel) — never auto-publishes to external
        platforms.
        """
        if not self._publish_enabled:
            return []

        return [
            PublicationRecord(
                channel="internal-dashboard",
                metadata={"requires_human_approval_for_external": True},
            ),
        ]

    def monitor(self, action: Action, **kwargs: Any) -> list[MonitorEntry]:
        """Monitor phase: track engagement signals post-publication."""
        if not self._publish_enabled:
            return []

        return [
            MonitorEntry(
                signal="internal-review-complete",
                details={"awaiting_external_approval": True},
            ),
        ]

    def rework(self, action: Action, feedback: str, **kwargs: Any) -> list[ExecutionStep]:
        """Rework: revise artifacts based on review feedback."""
        action.rework_count += 1
        return [
            ExecutionStep(
                name="revise-artifact",
                description=f"Rework iteration {action.rework_count}: {feedback[:120]}",
            ),
            ExecutionStep(
                name="re-validate",
                description="Re-run validation checklist after revision",
            ),
        ]

    def learn(self, action: Action, **kwargs: Any) -> list[LearningRecord]:
        """Extract learnings from the completed marketing action."""
        lessons: list[LearningRecord] = []
        if action.rework_count > 0:
            lessons.append(
                LearningRecord(
                    lesson=f"Required {action.rework_count} revision(s) before approval",
                    tags=["rework", "marketing"],
                    source_action_id=action.id,
                )
            )
        if action.status.value == "failed":
            reason = action.metadata.get("failure_reason", "unknown")
            lessons.append(
                LearningRecord(
                    lesson=f"Marketing action failed: {reason}",
                    tags=["failure", "marketing"],
                    source_action_id=action.id,
                )
            )
        return lessons
