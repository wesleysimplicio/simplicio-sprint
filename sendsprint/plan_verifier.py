"""Verifiable planning phase before implementation (#97).

Generates a structured plan before any diff, persists it in run state and
evidence, gates on human approval when autonomy policy requires it, and
detects duplicate work.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.evidence import BundleManager, EvidenceBundle, EvidenceItemType
from sendsprint.policy import AutonomyPolicy, level_rank
from sendsprint.run_state import RunState

# Autonomy levels at or above this rank require human approval on the plan.
_APPROVAL_THRESHOLD: str = "execute"


class VerifiablePlan(BaseModel):
    """Structured plan produced before any implementation diff."""

    model_config = ConfigDict(extra="forbid")

    task_summary: str
    target_files: list[str] = Field(default_factory=list)
    expected_tests: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    done_criteria: list[str] = Field(default_factory=list)
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class DuplicateWorkError(RuntimeError):
    """Raised when the plan targets work already completed in the run."""


class PlanNotApprovedError(RuntimeError):
    """Raised when a plan requires approval but has not been approved."""


class PlanVerifier:
    """Create, persist, gate and verify implementation plans."""

    def __init__(
        self,
        policy: AutonomyPolicy | None = None,
        bundle_manager: BundleManager | None = None,
    ) -> None:
        self._policy = policy or AutonomyPolicy()
        self._bundle_manager = bundle_manager

    # -- creation --------------------------------------------------------------

    def create_plan(
        self,
        *,
        task_summary: str,
        target_files: list[str] | None = None,
        expected_tests: list[str] | None = None,
        risks: list[str] | None = None,
        done_criteria: list[str] | None = None,
    ) -> VerifiablePlan:
        """Build a new verifiable plan (not yet approved or persisted)."""
        return VerifiablePlan(
            task_summary=task_summary,
            target_files=target_files or [],
            expected_tests=expected_tests or [],
            risks=risks or [],
            done_criteria=done_criteria or [],
        )

    # -- approval gating -------------------------------------------------------

    def requires_approval(self, plan: VerifiablePlan | None = None) -> bool:
        """Return True when the current autonomy policy demands human approval."""
        return (
            level_rank(self._policy.level) >= level_rank(_APPROVAL_THRESHOLD)  # type: ignore[arg-type]
            and self._policy.require_human_review
        )

    def approve(
        self,
        plan: VerifiablePlan,
        *,
        approved_by: str = "human",
    ) -> VerifiablePlan:
        """Mark a plan as approved.  Returns a new instance (model is mutable)."""
        plan.approved_by = approved_by
        plan.approved_at = datetime.now(UTC)
        return plan

    def assert_approved(self, plan: VerifiablePlan) -> None:
        """Raise if approval is required but the plan lacks it."""
        if self.requires_approval(plan) and plan.approved_by is None:
            raise PlanNotApprovedError("plan requires human approval before implementation")

    # -- duplicate detection ---------------------------------------------------

    def check_duplicate_work(
        self,
        plan: VerifiablePlan,
        run_state: RunState,
    ) -> list[str]:
        """Return delivery keys from *run_state.completed* whose item key
        appears in the plan's target files or task summary.

        Raises ``DuplicateWorkError`` when every planned target file is
        already covered by completed work.
        """
        if not run_state.completed:
            return []

        completed_keys = set(run_state.completed.keys())
        overlapping: list[str] = []
        for key in completed_keys:
            item_key = key.split("::")[0] if "::" in key else key
            if item_key in plan.task_summary or any(item_key in f for f in plan.target_files):
                overlapping.append(key)

        if (
            overlapping
            and plan.target_files
            and all(any(k.split("::")[0] in f for k in overlapping) for f in plan.target_files)
        ):
            raise DuplicateWorkError(
                f"all target files already covered by completed work: {overlapping}"
            )

        return overlapping

    # -- persistence -----------------------------------------------------------

    def persist_to_run_state(
        self,
        plan: VerifiablePlan,
        run_state: RunState,
    ) -> RunState:
        """Store the plan snapshot inside the run state's planned list."""
        marker = f"plan::{plan.task_summary[:80]}"
        run_state.mark_planned(marker)
        return run_state

    def persist_to_evidence(
        self,
        plan: VerifiablePlan,
        bundle: EvidenceBundle,
    ) -> EvidenceBundle:
        """Append the plan as a decision-type evidence item."""
        if self._bundle_manager is None:
            raise RuntimeError("BundleManager required for evidence persistence")

        metadata: dict[str, Any] = {
            "target_files": plan.target_files,
            "expected_tests": plan.expected_tests,
            "risks": plan.risks,
            "done_criteria": plan.done_criteria,
        }
        if plan.approved_by:
            metadata["approved_by"] = plan.approved_by
            metadata["approved_at"] = plan.approved_at.isoformat() if plan.approved_at else None

        self._bundle_manager.add_item(
            bundle,
            item_type=EvidenceItemType.decision,
            content=f"Verifiable plan: {plan.task_summary}",
            metadata=metadata,
        )
        return bundle
