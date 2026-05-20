"""Domain adapter abstract base class.

Each domain (code, design, ops, …) implements a concrete adapter that
provides the domain-specific logic for every lifecycle phase.  The
generic orchestrator calls adapter methods in phase order; the adapter
decides *how* each phase runs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sendsprint.actions.lifecycle import (
    Action,
    ApprovalPolicy,
    EvidenceRecord,
    ExecutionStep,
    LearningRecord,
    MonitorEntry,
    PublicationRecord,
    ValidationResult,
)


class DomainAdapter(ABC):
    """Contract every domain adapter must fulfil.

    Methods correspond 1-to-1 with :class:`ActionPhase` values.  An
    orchestrator walks the phases in order, calling the matching method
    and writing results back into the :class:`Action`.

    Adapters also declare their operational requirements via class-level
    properties so the orchestrator can pre-flight before execution.
    """

    # -- metadata (override in subclass) ------------------------------------

    @property
    @abstractmethod
    def domain_name(self) -> str:
        """Machine-readable domain key (matches ``DomainDescriptor.name``)."""

    @property
    def required_credentials(self) -> list[str]:
        """Env-var names or secret keys the adapter needs at runtime."""
        return []

    @property
    def required_tools(self) -> list[str]:
        """CLI tools / binaries the adapter expects on ``$PATH``."""
        return []

    @property
    def approval_policy(self) -> ApprovalPolicy:
        """Default approval policy for actions in this domain."""
        return ApprovalPolicy()

    # -- lifecycle methods --------------------------------------------------

    @abstractmethod
    def plan(self, action: Action, **kwargs: Any) -> list[ExecutionStep]:
        """Break the objective into concrete execution steps.

        Returns the planned steps; the orchestrator stores them on
        ``action.plan``.
        """

    @abstractmethod
    def execute(self, action: Action, **kwargs: Any) -> list[ExecutionStep]:
        """Run the planned steps.

        Returns executed steps (with status/output filled in); stored on
        ``action.execution_log``.
        """

    @abstractmethod
    def validate(self, action: Action, **kwargs: Any) -> ValidationResult:
        """Verify execution output meets acceptance criteria."""

    def gather_evidence(self, action: Action, **kwargs: Any) -> list[EvidenceRecord]:
        """Collect evidence artifacts.

        Default implementation returns an empty list; domains that produce
        auditable artifacts should override.
        """
        return []

    def publish(self, action: Action, **kwargs: Any) -> list[PublicationRecord]:
        """Publish or report results to external channels.

        Default: no-op.
        """
        return []

    def monitor(self, action: Action, **kwargs: Any) -> list[MonitorEntry]:
        """Post-publication monitoring.

        Default: no-op (returns empty list — no signals).
        """
        return []

    def rework(self, action: Action, feedback: str, **kwargs: Any) -> list[ExecutionStep]:
        """Handle rework when validation or monitoring fails.

        Default raises ``NotImplementedError``; domains that support
        automated rework should override.
        """
        raise NotImplementedError(f"Rework not implemented for domain '{self.domain_name}'")

    def learn(self, action: Action, **kwargs: Any) -> list[LearningRecord]:
        """Extract learnings from the completed action.

        Default: empty list.
        """
        return []
