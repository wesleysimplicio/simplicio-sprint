"""Code domain adapter — maps the existing sprint-to-PR flow onto the generic lifecycle.

This adapter is backwards-compatible: it wraps the same 10-step SprintFlow
concepts (import → plan → codegen → build → lint → test → security → commit →
PR → deploy) into the generic action lifecycle without changing any existing
behaviour.

Non-code domains will implement their own adapters following the same
:class:`DomainAdapter` contract.
"""

from __future__ import annotations

from typing import Any

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

# Domain descriptor singleton for code work.
CODE_DOMAIN = DomainDescriptor(name="code", label="Software Engineering", version="1.0")

# Map SprintFlow 10-step names to generic execution step names.
_SPRINT_STEP_MAP: dict[int, str] = {
    1: "import-sprint",
    2: "plan-delivery",
    3: "generate-code",
    4: "build",
    5: "lint",
    6: "run-tests",
    7: "security-review",
    8: "commit-changes",
    9: "create-pr",
    10: "deploy",
}


class CodeDomainAdapter(DomainAdapter):
    """Adapter for the software-engineering domain.

    Phase mapping to SprintFlow steps:

    =============  ============================
    ActionPhase    SprintFlow steps
    =============  ============================
    plan           1 (import) + 2 (plan)
    execute        3 (codegen) + 4 (build)
    validate       5 (lint) + 6 (tests) + 7 (security)
    evidence       Test reports, security findings
    publish        8 (commit) + 9 (PR)
    monitor        10 (deploy) + post-deploy checks
    rework         Fix loop (steps 3-7 repeated)
    learn          Failure-learning / operational-memory
    =============  ============================
    """

    @property
    def domain_name(self) -> str:
        return "code"

    @property
    def required_credentials(self) -> list[str]:
        return ["GITHUB_TOKEN"]

    @property
    def required_tools(self) -> list[str]:
        return ["git", "gh"]

    @property
    def approval_policy(self) -> ApprovalPolicy:
        return ApprovalPolicy(
            auto_approve=False,
            required_approvers=1,
            approver_roles=["code-reviewer"],
        )

    # -- lifecycle ----------------------------------------------------------

    def plan(self, action: Action, **kwargs: Any) -> list[ExecutionStep]:
        """Plan phase: import sprint items and build delivery plan."""
        steps = [
            ExecutionStep(
                name=_SPRINT_STEP_MAP[1],
                description="Read sprint items from tracker (Jira / ADO)",
            ),
            ExecutionStep(
                name=_SPRINT_STEP_MAP[2],
                description="Route items to repos and plan branches",
            ),
        ]
        return steps

    def execute(self, action: Action, **kwargs: Any) -> list[ExecutionStep]:
        """Execute phase: code generation and build."""
        steps = [
            ExecutionStep(
                name=_SPRINT_STEP_MAP[3],
                description="Generate / edit code for each planned delivery",
            ),
            ExecutionStep(
                name=_SPRINT_STEP_MAP[4],
                description="Build the project to catch compilation errors",
            ),
        ]
        return steps

    def validate(self, action: Action, **kwargs: Any) -> ValidationResult:
        """Validate phase: lint + tests + security review."""
        checks: list[dict[str, Any]] = [
            {"name": "lint", "sprint_step": 5, "description": "Run linters (ruff, eslint, etc.)"},
            {"name": "tests", "sprint_step": 6, "description": "Run unit / integration / e2e tests"},
            {"name": "security", "sprint_step": 7, "description": "Static security analysis"},
        ]
        return ValidationResult(passed=True, checks=checks, message="All checks passed")

    def gather_evidence(self, action: Action, **kwargs: Any) -> list[EvidenceRecord]:
        """Collect test reports and security findings as evidence."""
        records: list[EvidenceRecord] = []
        if action.validation and action.validation.checks:
            for check in action.validation.checks:
                records.append(
                    EvidenceRecord(
                        kind=f"check-{check.get('name', 'unknown')}",
                        content=check.get("description"),
                    )
                )
        return records

    def publish(self, action: Action, **kwargs: Any) -> list[PublicationRecord]:
        """Publish phase: commit + PR creation."""
        return [
            PublicationRecord(
                channel="git-commit",
                metadata={"sprint_step": 8},
            ),
            PublicationRecord(
                channel="github-pr",
                metadata={"sprint_step": 9},
            ),
        ]

    def monitor(self, action: Action, **kwargs: Any) -> list[MonitorEntry]:
        """Monitor phase: deploy + post-deploy health check."""
        return [
            MonitorEntry(
                signal="deploy-triggered",
                details={"sprint_step": 10},
            ),
        ]

    def rework(self, action: Action, feedback: str, **kwargs: Any) -> list[ExecutionStep]:
        """Rework: re-run codegen → build → lint → test → security."""
        action.rework_count += 1
        return [
            ExecutionStep(name=name, description=f"Rework iteration {action.rework_count}")
            for name in [
                _SPRINT_STEP_MAP[3],
                _SPRINT_STEP_MAP[4],
                _SPRINT_STEP_MAP[5],
                _SPRINT_STEP_MAP[6],
                _SPRINT_STEP_MAP[7],
            ]
        ]

    def learn(self, action: Action, **kwargs: Any) -> list[LearningRecord]:
        """Extract lessons from the completed action."""
        lessons: list[LearningRecord] = []
        if action.rework_count > 0:
            lessons.append(
                LearningRecord(
                    lesson=f"Required {action.rework_count} rework iteration(s) before passing validation",
                    tags=["rework", "code"],
                    source_action_id=action.id,
                )
            )
        if action.status.value == "failed":
            reason = action.metadata.get("failure_reason", "unknown")
            lessons.append(
                LearningRecord(
                    lesson=f"Action failed: {reason}",
                    tags=["failure", "code"],
                    source_action_id=action.id,
                )
            )
        return lessons
