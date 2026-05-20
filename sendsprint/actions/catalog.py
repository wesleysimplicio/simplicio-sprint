"""Action catalog — reusable playbook templates for domain-agnostic orchestration.

Each ``PlaybookTemplate`` declares the contract an action run must honour:
required/optional inputs, default execution steps, evidence requirements,
a validation recipe, an approval policy, and the expected output format.

The ``ActionCatalog`` keeps a registry of templates that can be discovered
via CLI (``sendsprint actions list``) or API (``GET /api/actions``).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.actions.lifecycle import ApprovalPolicy

# ---------------------------------------------------------------------------
# Template model
# ---------------------------------------------------------------------------


class PlaybookTemplate(BaseModel):
    """Reusable playbook template for a domain action."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(..., description="Machine-readable template key (unique)")
    domain: str = Field(..., description="Domain key, e.g. 'software', 'marketing'")
    description: str = Field(default="", description="What this playbook produces")
    required_inputs: list[str] = Field(
        default_factory=list,
        description="Input fields the operator must supply before execution",
    )
    optional_inputs: list[str] = Field(
        default_factory=list,
        description="Input fields the operator may supply to customise behaviour",
    )
    default_steps: list[str] = Field(
        default_factory=list,
        description="Ordered step names the playbook runs by default",
    )
    evidence_requirements: list[str] = Field(
        default_factory=list,
        description="Evidence artifact kinds the playbook must produce",
    )
    validation_recipe: list[str] = Field(
        default_factory=list,
        description="Checks that must pass before the action is considered done",
    )
    approval_policy: ApprovalPolicy = Field(
        default_factory=ApprovalPolicy,
        description="Who must approve the action output",
    )
    output_format: str = Field(
        default="json",
        description="Expected output format (json, markdown, html, artifact-bundle, …)",
    )


# ---------------------------------------------------------------------------
# Built-in software playbooks
# ---------------------------------------------------------------------------

SPRINT_TO_PR = PlaybookTemplate(
    name="sprint-to-pr",
    domain="software",
    description="Import sprint items, plan delivery, generate code, validate, and open PRs",
    required_inputs=["sprint_id", "repo_path"],
    optional_inputs=["scope_mode", "transport", "dry_run", "autonomy_level"],
    default_steps=[
        "import-sprint",
        "plan-delivery",
        "generate-code",
        "build",
        "lint",
        "run-tests",
        "security-review",
        "commit-changes",
        "create-pr",
        "deploy",
    ],
    evidence_requirements=["test-report", "lint-report", "security-findings", "pr-url"],
    validation_recipe=[
        "build-passes",
        "lint-clean",
        "tests-green",
        "security-no-critical",
        "pr-created",
    ],
    approval_policy=ApprovalPolicy(
        auto_approve=False, required_approvers=1, approver_roles=["reviewer"]
    ),
    output_format="json",
)

BUG_FIX = PlaybookTemplate(
    name="bug-fix",
    domain="software",
    description="Triage a bug, write a failing test, fix, and open a PR",
    required_inputs=["issue_key", "repo_path"],
    optional_inputs=["branch_name", "root_cause_hint"],
    default_steps=[
        "triage-issue",
        "write-failing-test",
        "implement-fix",
        "run-tests",
        "security-review",
        "commit-changes",
        "create-pr",
    ],
    evidence_requirements=["test-report", "root-cause-analysis", "pr-url"],
    validation_recipe=[
        "failing-test-added",
        "tests-green",
        "no-regressions",
        "security-no-critical",
    ],
    approval_policy=ApprovalPolicy(
        auto_approve=False, required_approvers=1, approver_roles=["reviewer"]
    ),
    output_format="json",
)

REFACTOR = PlaybookTemplate(
    name="refactor",
    domain="software",
    description="Refactor code to improve structure without changing behaviour",
    required_inputs=["repo_path", "target_files"],
    optional_inputs=["refactor_goal", "max_scope"],
    default_steps=[
        "snapshot-baseline",
        "analyse-code",
        "plan-refactor",
        "apply-changes",
        "run-tests",
        "lint",
        "diff-review",
        "commit-changes",
        "create-pr",
    ],
    evidence_requirements=["test-report", "diff-summary", "pr-url"],
    validation_recipe=[
        "tests-green",
        "lint-clean",
        "no-behaviour-change",
        "diff-within-scope",
    ],
    approval_policy=ApprovalPolicy(
        auto_approve=False, required_approvers=1, approver_roles=["reviewer"]
    ),
    output_format="json",
)

# ---------------------------------------------------------------------------
# Built-in marketing playbooks
# ---------------------------------------------------------------------------

CAMPAIGN_BRIEF = PlaybookTemplate(
    name="campaign-brief",
    domain="marketing",
    description="Strategic brief defining audience, offer, channels, timeline, and KPIs",
    required_inputs=["audience", "offer", "channels", "objective", "deadline", "budget"],
    optional_inputs=["brand_guidelines_url", "competitor_refs"],
    default_steps=[
        "define-audience",
        "craft-offer",
        "select-channels",
        "set-kpis",
        "draft-brief",
        "review-brief",
    ],
    evidence_requirements=["brief-document", "approval-notes"],
    validation_recipe=[
        "brand-guidelines-reviewed",
        "target-audience-defined",
        "kpis-specified",
        "budget-approved",
        "timeline-feasible",
    ],
    approval_policy=ApprovalPolicy(
        auto_approve=False, required_approvers=1, approver_roles=["marketing-lead"]
    ),
    output_format="markdown",
)

LANDING_PAGE = PlaybookTemplate(
    name="landing-page",
    domain="marketing",
    description="Draft copy for a landing page including headline, body, CTA, and SEO metadata",
    required_inputs=["audience", "offer", "brand_constraints", "cta_goal", "seo_keywords"],
    optional_inputs=["design_reference", "a_b_variants"],
    default_steps=[
        "draft-headline",
        "write-body-copy",
        "define-cta",
        "add-seo-metadata",
        "review-copy",
        "screenshot-preview",
    ],
    evidence_requirements=["copy-draft", "screenshot-preview", "seo-audit"],
    validation_recipe=[
        "brand-checklist-passed",
        "claims-risk-review",
        "cta-clear-and-actionable",
        "seo-metadata-present",
        "link-checks-passed",
    ],
    approval_policy=ApprovalPolicy(
        auto_approve=False, required_approvers=1, approver_roles=["marketing-lead"]
    ),
    output_format="markdown",
)

EMAIL_SEQUENCE = PlaybookTemplate(
    name="email-sequence",
    domain="marketing",
    description="Multi-step email drip sequence with subject lines, body copy, and send schedule",
    required_inputs=["audience", "offer", "sequence_length", "objective", "brand_constraints"],
    optional_inputs=["send_schedule", "utm_parameters"],
    default_steps=[
        "outline-sequence",
        "write-emails",
        "set-subject-lines",
        "define-send-schedule",
        "add-utm-parameters",
        "review-copy",
    ],
    evidence_requirements=["email-drafts", "send-schedule", "utm-checklist"],
    validation_recipe=[
        "brand-checklist-passed",
        "claims-risk-review",
        "unsubscribe-link-present",
        "subject-lines-reviewed",
        "send-schedule-defined",
        "utm-parameters-set",
    ],
    approval_policy=ApprovalPolicy(
        auto_approve=False, required_approvers=1, approver_roles=["marketing-lead"]
    ),
    output_format="markdown",
)

# ---------------------------------------------------------------------------
# Catalog registry
# ---------------------------------------------------------------------------

_BUILTIN_PLAYBOOKS: list[PlaybookTemplate] = [
    # software
    SPRINT_TO_PR,
    BUG_FIX,
    REFACTOR,
    # marketing
    CAMPAIGN_BRIEF,
    LANDING_PAGE,
    EMAIL_SEQUENCE,
]


class ActionCatalog:
    """In-memory registry of playbook templates with discovery helpers."""

    def __init__(self) -> None:
        self._templates: dict[str, PlaybookTemplate] = {}
        for tpl in _BUILTIN_PLAYBOOKS:
            self._templates[tpl.name] = tpl

    # -- mutation -------------------------------------------------------------

    def register(self, template: PlaybookTemplate) -> None:
        """Register (or replace) a playbook template."""
        self._templates[template.name] = template

    # -- query ----------------------------------------------------------------

    def list_all(self) -> list[PlaybookTemplate]:
        """Return all registered templates sorted by domain then name."""
        return sorted(self._templates.values(), key=lambda t: (t.domain, t.name))

    def get_by_name(self, name: str) -> PlaybookTemplate | None:
        """Lookup a single template by exact name."""
        return self._templates.get(name)

    def get_by_domain(self, domain: str) -> list[PlaybookTemplate]:
        """Return all templates belonging to *domain*."""
        return sorted(
            [t for t in self._templates.values() if t.domain == domain],
            key=lambda t: t.name,
        )

    def search(self, query: str) -> list[PlaybookTemplate]:
        """Case-insensitive substring search across name, domain, and description."""
        q = query.lower()
        return sorted(
            [
                t
                for t in self._templates.values()
                if q in t.name.lower() or q in t.domain.lower() or q in t.description.lower()
            ],
            key=lambda t: (t.domain, t.name),
        )

    # -- serialisation --------------------------------------------------------

    def to_dicts(self) -> list[dict[str, Any]]:
        """Dump all templates as JSON-ready dicts."""
        return [t.model_dump(mode="json") for t in self.list_all()]


def default_action_catalog() -> ActionCatalog:
    """Return a catalog pre-loaded with built-in playbooks."""
    return ActionCatalog()
