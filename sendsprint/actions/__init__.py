"""Generic action lifecycle and domain adapter contracts."""

from sendsprint.actions.adapter import DomainAdapter
from sendsprint.actions.lifecycle import (
    Action,
    ActionPhase,
    ActionStatus,
    ApprovalPolicy,
    DomainDescriptor,
    ExecutionStep,
    LearningRecord,
    Objective,
    ValidationResult,
)

__all__ = [
    "Action",
    "ActionPhase",
    "ActionStatus",
    "ApprovalPolicy",
    "DomainAdapter",
    "DomainDescriptor",
    "ExecutionStep",
    "LearningRecord",
    "Objective",
    "ValidationResult",
]
