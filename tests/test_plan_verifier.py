"""Tests for sendsprint.plan_verifier (#97)."""

from __future__ import annotations

import tempfile
from datetime import datetime

import pytest

from sendsprint.evidence import BundleManager, EvidenceBundle, EvidenceItemType
from sendsprint.plan_verifier import (
    DuplicateWorkError,
    PlanNotApprovedError,
    PlanVerifier,
    VerifiablePlan,
)
from sendsprint.policy import AutonomyPolicy
from sendsprint.run_state import RunState

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_state(**overrides) -> RunState:
    defaults = {"run_id": "run-abc123", "source": "jira", "sprint_id": "SP-1"}
    defaults.update(overrides)
    return RunState(**defaults)


def _make_verifier(
    level: str = "plan",
    require_human_review: bool = True,
    bundle_manager: BundleManager | None = None,
) -> PlanVerifier:
    policy = AutonomyPolicy(level=level, require_human_review=require_human_review)
    return PlanVerifier(policy=policy, bundle_manager=bundle_manager)


# ---------------------------------------------------------------------------
# VerifiablePlan model
# ---------------------------------------------------------------------------


class TestVerifiablePlanModel:
    def test_minimal_plan(self):
        plan = VerifiablePlan(task_summary="Implement feature X")
        assert plan.task_summary == "Implement feature X"
        assert plan.target_files == []
        assert plan.expected_tests == []
        assert plan.risks == []
        assert plan.done_criteria == []
        assert plan.approved_by is None
        assert plan.approved_at is None
        assert isinstance(plan.created_at, datetime)

    def test_full_plan(self):
        plan = VerifiablePlan(
            task_summary="Add login endpoint",
            target_files=["src/auth.py", "tests/test_auth.py"],
            expected_tests=["test_login_success", "test_login_invalid_creds"],
            risks=["May break session middleware"],
            done_criteria=["200 on valid creds", "401 on invalid creds"],
        )
        assert len(plan.target_files) == 2
        assert len(plan.expected_tests) == 2
        assert len(plan.risks) == 1
        assert len(plan.done_criteria) == 2

    def test_serialization_roundtrip(self):
        plan = VerifiablePlan(
            task_summary="Roundtrip test",
            target_files=["a.py"],
            risks=["none"],
        )
        data = plan.model_dump_json()
        restored = VerifiablePlan.model_validate_json(data)
        assert restored.task_summary == plan.task_summary
        assert restored.target_files == plan.target_files

    def test_extra_fields_rejected(self):
        with pytest.raises(ValueError):
            VerifiablePlan(task_summary="x", unknown_field="boom")


# ---------------------------------------------------------------------------
# PlanVerifier.create_plan
# ---------------------------------------------------------------------------


class TestCreatePlan:
    def test_create_plan_defaults(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(task_summary="Do something")
        assert plan.task_summary == "Do something"
        assert plan.target_files == []

    def test_create_plan_with_all_fields(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(
            task_summary="Add widget",
            target_files=["widget.py"],
            expected_tests=["test_widget"],
            risks=["breakage"],
            done_criteria=["widget renders"],
        )
        assert plan.target_files == ["widget.py"]
        assert plan.expected_tests == ["test_widget"]
        assert plan.risks == ["breakage"]
        assert plan.done_criteria == ["widget renders"]


# ---------------------------------------------------------------------------
# Approval gating
# ---------------------------------------------------------------------------


class TestApprovalGating:
    def test_plan_level_no_approval_needed(self):
        verifier = _make_verifier(level="plan", require_human_review=True)
        assert verifier.requires_approval() is False

    def test_observe_level_no_approval_needed(self):
        verifier = _make_verifier(level="observe", require_human_review=True)
        assert verifier.requires_approval() is False

    def test_execute_level_requires_approval(self):
        verifier = _make_verifier(level="execute", require_human_review=True)
        assert verifier.requires_approval() is True

    def test_execute_level_no_approval_when_review_disabled(self):
        verifier = _make_verifier(level="execute", require_human_review=False)
        assert verifier.requires_approval() is False

    def test_commit_level_requires_approval(self):
        verifier = _make_verifier(level="commit", require_human_review=True)
        assert verifier.requires_approval() is True

    def test_pr_level_requires_approval(self):
        verifier = _make_verifier(level="pr", require_human_review=True)
        assert verifier.requires_approval() is True

    def test_approve_sets_fields(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(task_summary="x")
        assert plan.approved_by is None
        verifier.approve(plan, approved_by="alice")
        assert plan.approved_by == "alice"
        assert plan.approved_at is not None

    def test_assert_approved_passes_when_approved(self):
        verifier = _make_verifier(level="execute")
        plan = verifier.create_plan(task_summary="x")
        verifier.approve(plan)
        verifier.assert_approved(plan)  # should not raise

    def test_assert_approved_raises_when_not_approved(self):
        verifier = _make_verifier(level="execute")
        plan = verifier.create_plan(task_summary="x")
        with pytest.raises(PlanNotApprovedError):
            verifier.assert_approved(plan)

    def test_assert_approved_passes_at_plan_level(self):
        verifier = _make_verifier(level="plan")
        plan = verifier.create_plan(task_summary="x")
        # No approval needed at plan level
        verifier.assert_approved(plan)


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


class TestDuplicateDetection:
    def test_no_duplicates_when_nothing_completed(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(
            task_summary="FEAT-1 add widget",
            target_files=["FEAT-1/widget.py"],
        )
        state = _make_run_state()
        result = verifier.check_duplicate_work(plan, state)
        assert result == []

    def test_detects_overlap_by_item_key_in_summary(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(
            task_summary="Implement FEAT-1 login",
            target_files=["src/login.py"],
        )
        state = _make_run_state(completed={"FEAT-1::repo-a": "2024-01-01T00:00:00"})
        result = verifier.check_duplicate_work(plan, state)
        assert "FEAT-1::repo-a" in result

    def test_detects_overlap_by_item_key_in_target_files(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(
            task_summary="Some work",
            target_files=["FEAT-2/auth.py", "other/new.py"],
        )
        state = _make_run_state(completed={"FEAT-2::repo-b": "2024-01-01T00:00:00"})
        result = verifier.check_duplicate_work(plan, state)
        assert "FEAT-2::repo-b" in result

    def test_raises_when_all_files_covered(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(
            task_summary="Implement FEAT-3",
            target_files=["FEAT-3/a.py", "FEAT-3/b.py"],
        )
        state = _make_run_state(completed={"FEAT-3::repo": "2024-01-01T00:00:00"})
        with pytest.raises(DuplicateWorkError):
            verifier.check_duplicate_work(plan, state)

    def test_no_raise_when_partial_overlap(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(
            task_summary="Implement FEAT-4",
            target_files=["FEAT-4/a.py", "other/b.py"],
        )
        state = _make_run_state(completed={"FEAT-4::repo": "2024-01-01T00:00:00"})
        result = verifier.check_duplicate_work(plan, state)
        assert len(result) == 1

    def test_no_overlap_when_keys_differ(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(
            task_summary="Implement FEAT-5",
            target_files=["FEAT-5/x.py"],
        )
        state = _make_run_state(completed={"FEAT-99::repo": "2024-01-01T00:00:00"})
        result = verifier.check_duplicate_work(plan, state)
        assert result == []


# ---------------------------------------------------------------------------
# Run state persistence
# ---------------------------------------------------------------------------


class TestRunStatePersistence:
    def test_persist_adds_plan_marker(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(task_summary="Add feature Z")
        state = _make_run_state()
        assert len(state.planned) == 0
        verifier.persist_to_run_state(plan, state)
        assert len(state.planned) == 1
        assert state.planned[0].startswith("plan::")

    def test_persist_idempotent(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(task_summary="Add feature Z")
        state = _make_run_state()
        verifier.persist_to_run_state(plan, state)
        verifier.persist_to_run_state(plan, state)
        assert len(state.planned) == 1

    def test_persist_truncates_long_summary(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(task_summary="A" * 200)
        state = _make_run_state()
        verifier.persist_to_run_state(plan, state)
        marker = state.planned[0]
        # 80 char cap + "plan::" prefix
        assert len(marker) <= 86


# ---------------------------------------------------------------------------
# Evidence persistence
# ---------------------------------------------------------------------------


class TestEvidencePersistence:
    def test_persist_to_evidence_adds_decision_item(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bm = BundleManager(tmpdir)
            bundle = bm.create_bundle("run-test")
            verifier = _make_verifier(bundle_manager=bm)
            plan = verifier.create_plan(
                task_summary="Implement auth",
                target_files=["auth.py"],
                expected_tests=["test_auth"],
                risks=["session break"],
                done_criteria=["200 on login"],
            )
            verifier.persist_to_evidence(plan, bundle)
            assert len(bundle.items) == 1
            item = bundle.items[0]
            assert item.type == EvidenceItemType.decision
            assert "Verifiable plan" in item.content
            assert item.metadata["target_files"] == ["auth.py"]

    def test_persist_to_evidence_includes_approval_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bm = BundleManager(tmpdir)
            bundle = bm.create_bundle("run-test2")
            verifier = _make_verifier(bundle_manager=bm)
            plan = verifier.create_plan(task_summary="Approved work")
            verifier.approve(plan, approved_by="bob")
            verifier.persist_to_evidence(plan, bundle)
            meta = bundle.items[0].metadata
            assert meta["approved_by"] == "bob"
            assert meta["approved_at"] is not None

    def test_persist_without_bundle_manager_raises(self):
        verifier = _make_verifier()
        plan = verifier.create_plan(task_summary="No BM")
        bundle = EvidenceBundle(run_id="run-x")
        with pytest.raises(RuntimeError, match="BundleManager required"):
            verifier.persist_to_evidence(plan, bundle)

    def test_persist_writes_to_disk(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bm = BundleManager(tmpdir)
            bundle = bm.create_bundle("run-disk")
            verifier = _make_verifier(bundle_manager=bm)
            plan = verifier.create_plan(task_summary="Disk test")
            verifier.persist_to_evidence(plan, bundle)
            # Reload from disk
            loaded = bm.load_bundle("run-disk")
            assert loaded is not None
            assert len(loaded.items) == 1
            assert "Verifiable plan" in loaded.items[0].content


# ---------------------------------------------------------------------------
# Integration: full lifecycle
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    def test_create_approve_persist_no_duplicates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            bm = BundleManager(tmpdir)
            bundle = bm.create_bundle("run-full")
            verifier = _make_verifier(level="execute", bundle_manager=bm)
            state = _make_run_state()

            # 1. Create plan
            plan = verifier.create_plan(
                task_summary="TASK-10 add endpoint",
                target_files=["src/endpoint.py"],
                expected_tests=["test_endpoint_200"],
                risks=["rate limiting"],
                done_criteria=["GET /api returns 200"],
            )

            # 2. Check duplicates — none
            overlaps = verifier.check_duplicate_work(plan, state)
            assert overlaps == []

            # 3. Requires approval at execute level
            assert verifier.requires_approval() is True

            # 4. Approve
            verifier.approve(plan, approved_by="reviewer")
            verifier.assert_approved(plan)

            # 5. Persist
            verifier.persist_to_run_state(plan, state)
            verifier.persist_to_evidence(plan, bundle)

            assert len(state.planned) == 1
            assert len(bundle.items) == 1

    def test_unapproved_plan_blocks_at_high_autonomy(self):
        verifier = _make_verifier(level="pr")
        plan = verifier.create_plan(task_summary="Blocked plan")
        with pytest.raises(PlanNotApprovedError):
            verifier.assert_approved(plan)
