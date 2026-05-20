"""Tests for the generic action lifecycle and domain adapter contract."""

from __future__ import annotations

import json

import pytest

from sendsprint.actions.adapter import DomainAdapter
from sendsprint.actions.code_adapter import _SPRINT_STEP_MAP, CODE_DOMAIN, CodeDomainAdapter
from sendsprint.actions.lifecycle import (
    Action,
    ActionPhase,
    ActionStatus,
    ApprovalPolicy,
    DomainDescriptor,
    ExecutionStep,
    Objective,
    ValidationResult,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_action(domain: DomainDescriptor | None = None) -> Action:
    return Action(
        domain=domain or DomainDescriptor(name="test", label="Test Domain"),
        objective=Objective(
            summary="Implement feature X",
            acceptance_criteria=["Unit tests pass", "No regressions"],
            context={"item_key": "PROJ-42"},
        ),
    )


def _make_code_action() -> Action:
    return _make_action(domain=CODE_DOMAIN)


# ---------------------------------------------------------------------------
# ActionPhase enum
# ---------------------------------------------------------------------------


class TestActionPhase:
    def test_all_phases_present(self) -> None:
        expected = {
            "plan",
            "execute",
            "validate",
            "evidence",
            "publish",
            "monitor",
            "rework",
            "learn",
        }
        assert {p.value for p in ActionPhase} == expected

    def test_phase_is_str_enum(self) -> None:
        assert ActionPhase.plan == "plan"
        assert isinstance(ActionPhase.execute, str)


# ---------------------------------------------------------------------------
# ActionStatus enum
# ---------------------------------------------------------------------------


class TestActionStatus:
    def test_all_statuses(self) -> None:
        expected = {"pending", "in_progress", "blocked", "done", "failed"}
        assert {s.value for s in ActionStatus} == expected


# ---------------------------------------------------------------------------
# DomainDescriptor
# ---------------------------------------------------------------------------


class TestDomainDescriptor:
    def test_frozen(self) -> None:
        d = DomainDescriptor(name="ops", label="Operations")
        with pytest.raises(ValueError):  # ValidationError on frozen model
            d.name = "changed"  # type: ignore[misc]

    def test_default_version(self) -> None:
        d = DomainDescriptor(name="design")
        assert d.version == "1.0"

    def test_serialization_roundtrip(self) -> None:
        d = DomainDescriptor(name="code", label="Software Engineering")
        raw = d.model_dump_json()
        restored = DomainDescriptor.model_validate_json(raw)
        assert restored == d


# ---------------------------------------------------------------------------
# Objective
# ---------------------------------------------------------------------------


class TestObjective:
    def test_defaults(self) -> None:
        obj = Objective(summary="Do something")
        assert obj.priority == "medium"
        assert obj.acceptance_criteria == []
        assert obj.context == {}

    def test_serialization(self) -> None:
        obj = Objective(
            summary="Deploy service",
            acceptance_criteria=["Health check green"],
            context={"env": "staging"},
            priority="high",
        )
        data = json.loads(obj.model_dump_json())
        assert data["priority"] == "high"
        assert data["context"]["env"] == "staging"


# ---------------------------------------------------------------------------
# ExecutionStep
# ---------------------------------------------------------------------------


class TestExecutionStep:
    def test_auto_id(self) -> None:
        s1 = ExecutionStep(name="step-a")
        s2 = ExecutionStep(name="step-b")
        assert s1.id != s2.id
        assert len(s1.id) == 8

    def test_default_status(self) -> None:
        s = ExecutionStep(name="build")
        assert s.status == ActionStatus.pending


# ---------------------------------------------------------------------------
# ValidationResult
# ---------------------------------------------------------------------------


class TestValidationResult:
    def test_passed(self) -> None:
        v = ValidationResult(passed=True, message="OK")
        assert v.passed is True

    def test_with_checks(self) -> None:
        v = ValidationResult(
            passed=False,
            checks=[{"name": "lint", "ok": False}],
            message="Lint failed",
        )
        assert len(v.checks) == 1
        assert v.checks[0]["name"] == "lint"


# ---------------------------------------------------------------------------
# Action model
# ---------------------------------------------------------------------------


class TestAction:
    def test_defaults(self) -> None:
        a = _make_action()
        assert a.phase == ActionPhase.plan
        assert a.status == ActionStatus.pending
        assert a.rework_count == 0
        assert a.plan == []
        assert a.execution_log == []
        assert a.validation is None

    def test_advance_phase(self) -> None:
        a = _make_action()
        a.advance_phase(ActionPhase.execute)
        assert a.phase == ActionPhase.execute
        assert a.updated_at is not None

    def test_mark_done(self) -> None:
        a = _make_action()
        a.mark_done()
        assert a.status == ActionStatus.done
        assert a.updated_at is not None

    def test_mark_failed(self) -> None:
        a = _make_action()
        a.mark_failed("timeout")
        assert a.status == ActionStatus.failed
        assert a.metadata["failure_reason"] == "timeout"

    def test_serialization_roundtrip(self) -> None:
        a = _make_action()
        a.advance_phase(ActionPhase.validate)
        a.validation = ValidationResult(passed=True, message="green")
        raw = a.model_dump_json()
        restored = Action.model_validate_json(raw)
        assert restored.phase == ActionPhase.validate
        assert restored.validation is not None
        assert restored.validation.passed is True

    def test_backwards_compatible_defaults(self) -> None:
        """Minimal JSON (no optional fields) must deserialize cleanly."""
        minimal = {
            "domain": {"name": "code"},
            "objective": {"summary": "Fix bug"},
        }
        a = Action.model_validate(minimal)
        assert a.phase == ActionPhase.plan
        assert a.status == ActionStatus.pending
        assert a.rework_count == 0
        assert a.domain.version == "1.0"

    def test_non_software_action(self) -> None:
        """Generic schema supports non-code domains without code-specific fields."""
        a = Action(
            domain=DomainDescriptor(name="marketing", label="Marketing"),
            objective=Objective(
                summary="Launch Q3 campaign",
                acceptance_criteria=["All creatives approved", "Budget signed off"],
                context={"campaign_id": "Q3-2025"},
                priority="high",
            ),
        )
        data = json.loads(a.model_dump_json())
        assert data["domain"]["name"] == "marketing"
        assert data["objective"]["priority"] == "high"


# ---------------------------------------------------------------------------
# ApprovalPolicy
# ---------------------------------------------------------------------------


class TestApprovalPolicy:
    def test_defaults(self) -> None:
        p = ApprovalPolicy()
        assert p.auto_approve is False
        assert p.required_approvers == 1

    def test_frozen(self) -> None:
        p = ApprovalPolicy(auto_approve=True)
        with pytest.raises(ValueError):
            p.auto_approve = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DomainAdapter ABC
# ---------------------------------------------------------------------------


class TestDomainAdapterContract:
    """Verify the ABC cannot be instantiated and default methods behave."""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            DomainAdapter()  # type: ignore[abstract]

    def test_default_gather_evidence(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        # Without validation data, evidence is empty
        assert adapter.gather_evidence(action) == []

    def test_default_publish(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        pubs = adapter.publish(action)
        assert len(pubs) == 2
        assert pubs[0].channel == "git-commit"

    def test_default_monitor(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        entries = adapter.monitor(action)
        assert len(entries) == 1
        assert entries[0].signal == "deploy-triggered"

    def test_default_learn(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        assert adapter.learn(action) == []


# ---------------------------------------------------------------------------
# CodeDomainAdapter
# ---------------------------------------------------------------------------


class TestCodeDomainAdapter:
    def test_domain_name(self) -> None:
        adapter = CodeDomainAdapter()
        assert adapter.domain_name == "code"

    def test_required_credentials(self) -> None:
        adapter = CodeDomainAdapter()
        assert "GITHUB_TOKEN" in adapter.required_credentials

    def test_required_tools(self) -> None:
        adapter = CodeDomainAdapter()
        assert "git" in adapter.required_tools
        assert "gh" in adapter.required_tools

    def test_approval_policy(self) -> None:
        adapter = CodeDomainAdapter()
        policy = adapter.approval_policy
        assert policy.auto_approve is False
        assert policy.required_approvers == 1
        assert "code-reviewer" in policy.approver_roles

    def test_plan_returns_import_and_delivery(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        steps = adapter.plan(action)
        assert len(steps) == 2
        assert steps[0].name == "import-sprint"
        assert steps[1].name == "plan-delivery"

    def test_execute_returns_codegen_and_build(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        steps = adapter.execute(action)
        assert len(steps) == 2
        names = [s.name for s in steps]
        assert "generate-code" in names
        assert "build" in names

    def test_validate_returns_three_checks(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        result = adapter.validate(action)
        assert result.passed is True
        check_names = [c["name"] for c in result.checks]
        assert "lint" in check_names
        assert "tests" in check_names
        assert "security" in check_names

    def test_gather_evidence_after_validation(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        action.validation = adapter.validate(action)
        evidence = adapter.gather_evidence(action)
        assert len(evidence) == 3
        kinds = [e.kind for e in evidence]
        assert "check-lint" in kinds
        assert "check-tests" in kinds
        assert "check-security" in kinds

    def test_rework_increments_count(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        assert action.rework_count == 0
        steps = adapter.rework(action, feedback="tests failed")
        assert action.rework_count == 1
        assert len(steps) == 5  # codegen + build + lint + tests + security

    def test_learn_after_rework(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        action.rework_count = 2
        lessons = adapter.learn(action)
        assert len(lessons) == 1
        assert "2 rework" in lessons[0].lesson

    def test_learn_after_failure(self) -> None:
        adapter = CodeDomainAdapter()
        action = _make_code_action()
        action.mark_failed("build error")
        lessons = adapter.learn(action)
        assert len(lessons) == 1
        assert "build error" in lessons[0].lesson

    def test_sprint_step_map_covers_10_steps(self) -> None:
        assert set(_SPRINT_STEP_MAP.keys()) == set(range(1, 11))

    def test_full_lifecycle_walkthrough(self) -> None:
        """Simulate walking through all phases with the code adapter."""
        adapter = CodeDomainAdapter()
        action = _make_code_action()

        # Plan
        action.plan = adapter.plan(action)
        action.advance_phase(ActionPhase.execute)
        assert len(action.plan) == 2

        # Execute
        action.execution_log = adapter.execute(action)
        action.advance_phase(ActionPhase.validate)

        # Validate
        action.validation = adapter.validate(action)
        action.advance_phase(ActionPhase.evidence)

        # Evidence
        action.evidence = adapter.gather_evidence(action)
        action.advance_phase(ActionPhase.publish)
        assert len(action.evidence) == 3

        # Publish
        action.publications = adapter.publish(action)
        action.advance_phase(ActionPhase.monitor)
        assert len(action.publications) == 2

        # Monitor
        action.monitors = adapter.monitor(action)
        action.advance_phase(ActionPhase.learn)

        # Learn
        action.learnings = adapter.learn(action)
        action.mark_done()

        assert action.status == ActionStatus.done
        assert action.phase == ActionPhase.learn

        # Full roundtrip serialization
        raw = action.model_dump_json()
        restored = Action.model_validate_json(raw)
        assert restored.status == ActionStatus.done
        assert len(restored.publications) == 2
        assert len(restored.evidence) == 3
