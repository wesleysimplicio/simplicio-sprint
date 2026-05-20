"""Tests for the marketing domain adapter and action templates."""

from __future__ import annotations

import json
from typing import Any

import pytest

from sendsprint.actions.lifecycle import (
    Action,
    ActionPhase,
    ActionStatus,
    Objective,
)
from sendsprint.actions.marketing_adapter import (
    CAMPAIGN_BRIEF,
    COMPETITOR_SCAN,
    CONTENT_CALENDAR,
    EMAIL_SEQUENCE,
    LANDING_PAGE_COPY,
    LAUNCH_CHECKLIST,
    MARKETING_DOMAIN,
    MARKETING_TEMPLATES,
    SOCIAL_POSTS,
    MarketingActionTemplate,
    MarketingDomainAdapter,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_marketing_action(template_name: str | None = None, **meta: Any) -> Action:
    metadata: dict[str, Any] = {**meta}
    if template_name:
        metadata["template"] = template_name
    return Action(
        domain=MARKETING_DOMAIN,
        objective=Objective(
            summary="Run Q3 product launch campaign",
            acceptance_criteria=["All assets produced", "Brand review passed"],
            context={"campaign": "q3-launch"},
        ),
        metadata=metadata,
    )


# ---------------------------------------------------------------------------
# Domain descriptor
# ---------------------------------------------------------------------------


class TestMarketingDomain:
    def test_domain_name(self) -> None:
        assert MARKETING_DOMAIN.name == "marketing"

    def test_domain_label(self) -> None:
        assert MARKETING_DOMAIN.label == "Marketing"

    def test_domain_version(self) -> None:
        assert MARKETING_DOMAIN.version == "1.0"

    def test_domain_frozen(self) -> None:
        with pytest.raises(ValueError):
            MARKETING_DOMAIN.name = "other"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Template constants
# ---------------------------------------------------------------------------


class TestMarketingTemplates:
    EXPECTED_TEMPLATES = [
        "campaign_brief",
        "landing_page_copy",
        "email_sequence",
        "social_posts",
        "competitor_scan",
        "content_calendar",
        "launch_checklist",
    ]

    def test_all_seven_templates_registered(self) -> None:
        assert len(MARKETING_TEMPLATES) == 7

    @pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
    def test_template_exists(self, name: str) -> None:
        assert name in MARKETING_TEMPLATES

    @pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
    def test_template_has_required_inputs(self, name: str) -> None:
        t = MARKETING_TEMPLATES[name]
        assert len(t.required_inputs) > 0

    @pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
    def test_template_has_validation_checklist(self, name: str) -> None:
        t = MARKETING_TEMPLATES[name]
        assert len(t.validation_checklist) > 0

    @pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
    def test_template_has_evidence_kinds(self, name: str) -> None:
        t = MARKETING_TEMPLATES[name]
        assert len(t.evidence_kinds) > 0

    @pytest.mark.parametrize("name", EXPECTED_TEMPLATES)
    def test_template_is_frozen(self, name: str) -> None:
        t = MARKETING_TEMPLATES[name]
        with pytest.raises(ValueError):
            t.name = "hacked"  # type: ignore[misc]

    def test_campaign_brief_inputs(self) -> None:
        assert "audience" in CAMPAIGN_BRIEF.required_inputs
        assert "offer" in CAMPAIGN_BRIEF.required_inputs
        assert "budget" in CAMPAIGN_BRIEF.required_inputs

    def test_landing_page_has_seo_keywords(self) -> None:
        assert "seo_keywords" in LANDING_PAGE_COPY.required_inputs

    def test_email_sequence_has_utm_check(self) -> None:
        assert "utm-parameters-set" in EMAIL_SEQUENCE.validation_checklist

    def test_social_posts_has_platform_specs(self) -> None:
        assert "platform-specs-met" in SOCIAL_POSTS.validation_checklist

    def test_competitor_scan_has_sources_cited(self) -> None:
        assert "sources-cited" in COMPETITOR_SCAN.validation_checklist

    def test_content_calendar_has_owner_assignment(self) -> None:
        assert "owner-assigned-per-item" in CONTENT_CALENDAR.validation_checklist

    def test_launch_checklist_requires_human_approval(self) -> None:
        assert "human-approval-obtained" in LAUNCH_CHECKLIST.validation_checklist

    def test_template_json_serializable(self) -> None:
        for t in MARKETING_TEMPLATES.values():
            data = json.loads(t.model_dump_json())
            assert data["name"] == t.name


# ---------------------------------------------------------------------------
# MarketingActionTemplate model
# ---------------------------------------------------------------------------


class TestMarketingActionTemplateModel:
    def test_extra_fields_forbidden(self) -> None:
        with pytest.raises(ValueError):
            MarketingActionTemplate(name="x", label="X", bogus="y")  # type: ignore[call-arg]

    def test_minimal_construction(self) -> None:
        t = MarketingActionTemplate(name="test", label="Test")
        assert t.required_inputs == []
        assert t.validation_checklist == []
        assert t.evidence_kinds == []


# ---------------------------------------------------------------------------
# Adapter metadata
# ---------------------------------------------------------------------------


class TestMarketingAdapterMetadata:
    def test_domain_name(self) -> None:
        adapter = MarketingDomainAdapter()
        assert adapter.domain_name == "marketing"

    def test_no_required_credentials(self) -> None:
        adapter = MarketingDomainAdapter()
        assert adapter.required_credentials == []

    def test_no_required_tools(self) -> None:
        adapter = MarketingDomainAdapter()
        assert adapter.required_tools == []

    def test_approval_policy_requires_human(self) -> None:
        adapter = MarketingDomainAdapter()
        policy = adapter.approval_policy
        assert policy.auto_approve is False
        assert policy.required_approvers == 1
        assert "marketing-lead" in policy.approver_roles


# ---------------------------------------------------------------------------
# Adapter helpers
# ---------------------------------------------------------------------------


class TestAdapterHelpers:
    def test_get_template_known(self) -> None:
        t = MarketingDomainAdapter.get_template("campaign_brief")
        assert t is CAMPAIGN_BRIEF

    def test_get_template_unknown_raises(self) -> None:
        with pytest.raises(KeyError):
            MarketingDomainAdapter.get_template("nonexistent")

    def test_list_templates_returns_sorted(self) -> None:
        names = MarketingDomainAdapter.list_templates()
        assert names == sorted(names)
        assert len(names) == 7


# ---------------------------------------------------------------------------
# Plan phase
# ---------------------------------------------------------------------------


class TestPlanPhase:
    def test_plan_with_template(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("campaign_brief")
        steps = adapter.plan(action)
        assert len(steps) == 3
        assert steps[0].name == "gather-inputs"
        assert "audience" in steps[0].description
        assert steps[1].name == "draft-artifact"
        assert steps[2].name == "run-validations"

    def test_plan_without_template(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        steps = adapter.plan(action)
        assert len(steps) == 2
        assert steps[0].name == "define-deliverables"
        assert steps[1].name == "draft-content"


# ---------------------------------------------------------------------------
# Execute phase
# ---------------------------------------------------------------------------


class TestExecutePhase:
    def test_execute_with_template(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("email_sequence")
        steps = adapter.execute(action)
        assert len(steps) == 2
        assert steps[0].name == "produce-artifact"
        assert "Email Sequence" in steps[0].description
        assert steps[1].name == "internal-review"

    def test_execute_without_template(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        steps = adapter.execute(action)
        assert "marketing content" in steps[0].description


# ---------------------------------------------------------------------------
# Validate phase
# ---------------------------------------------------------------------------


class TestValidatePhase:
    def test_validate_with_template_all_pass(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("landing_page_copy")
        result = adapter.validate(action)
        assert result.passed is True
        assert len(result.checks) == len(LANDING_PAGE_COPY.validation_checklist)
        assert all(c["passed"] for c in result.checks)

    def test_validate_without_template_uses_defaults(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        result = adapter.validate(action)
        assert result.passed is True
        check_names = [c["name"] for c in result.checks]
        assert "brand-checklist-passed" in check_names
        assert "claims-risk-review" in check_names
        assert "link-checks-passed" in check_names

    def test_validate_message_on_pass(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("social_posts")
        result = adapter.validate(action)
        assert result.message == "All marketing validations passed"


# ---------------------------------------------------------------------------
# Evidence phase
# ---------------------------------------------------------------------------


class TestEvidencePhase:
    def test_evidence_with_template(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("competitor_scan")
        records = adapter.gather_evidence(action)
        kinds = [r.kind for r in records]
        assert "scan-report" in kinds
        assert "source-links" in kinds
        assert "comparison-matrix" in kinds

    def test_evidence_includes_validation_report(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("competitor_scan")
        action.validation = adapter.validate(action)
        records = adapter.gather_evidence(action)
        kinds = [r.kind for r in records]
        assert "validation-report" in kinds

    def test_evidence_without_template(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        records = adapter.gather_evidence(action)
        assert any(r.kind == "marketing-artifact" for r in records)


# ---------------------------------------------------------------------------
# Publish phase
# ---------------------------------------------------------------------------


class TestPublishPhase:
    def test_publish_disabled_by_default(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("campaign_brief")
        pubs = adapter.publish(action)
        assert pubs == []

    def test_publish_enabled_returns_internal_channel(self) -> None:
        adapter = MarketingDomainAdapter(publish_enabled=True)
        action = _make_marketing_action("campaign_brief")
        pubs = adapter.publish(action)
        assert len(pubs) == 1
        assert pubs[0].channel == "internal-dashboard"
        assert pubs[0].metadata["requires_human_approval_for_external"] is True

    def test_publish_enabled_explicit_opt_in(self) -> None:
        disabled = MarketingDomainAdapter(publish_enabled=False)
        enabled = MarketingDomainAdapter(publish_enabled=True)
        action = _make_marketing_action()
        assert disabled.publish(action) == []
        assert len(enabled.publish(action)) == 1


# ---------------------------------------------------------------------------
# Monitor phase
# ---------------------------------------------------------------------------


class TestMonitorPhase:
    def test_monitor_disabled_when_publish_off(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        assert adapter.monitor(action) == []

    def test_monitor_returns_signal_when_publish_on(self) -> None:
        adapter = MarketingDomainAdapter(publish_enabled=True)
        action = _make_marketing_action()
        entries = adapter.monitor(action)
        assert len(entries) == 1
        assert entries[0].signal == "internal-review-complete"


# ---------------------------------------------------------------------------
# Rework phase
# ---------------------------------------------------------------------------


class TestReworkPhase:
    def test_rework_increments_count(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        adapter.rework(action, "Tone too aggressive")
        assert action.rework_count == 1
        adapter.rework(action, "Missing CTA")
        assert action.rework_count == 2

    def test_rework_returns_revise_and_revalidate(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        steps = adapter.rework(action, "Needs softer tone")
        assert len(steps) == 2
        assert steps[0].name == "revise-artifact"
        assert "softer tone" in steps[0].description
        assert steps[1].name == "re-validate"

    def test_rework_truncates_long_feedback(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        long_feedback = "x" * 200
        steps = adapter.rework(action, long_feedback)
        assert len(steps[0].description) < 200


# ---------------------------------------------------------------------------
# Learn phase
# ---------------------------------------------------------------------------


class TestLearnPhase:
    def test_learn_no_lessons_when_clean(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        action.mark_done()
        assert adapter.learn(action) == []

    def test_learn_captures_rework_count(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        action.rework_count = 3
        action.mark_done()
        lessons = adapter.learn(action)
        assert len(lessons) == 1
        assert "3 revision(s)" in lessons[0].lesson
        assert "marketing" in lessons[0].tags

    def test_learn_captures_failure(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action()
        action.mark_failed("Brand review rejected")
        lessons = adapter.learn(action)
        assert any("Brand review rejected" in lesson.lesson for lesson in lessons)


# ---------------------------------------------------------------------------
# Full lifecycle integration (fixture-based plan test per AC)
# ---------------------------------------------------------------------------


class TestFullLifecycle:
    """Fixture-based test walking a marketing action through all phases."""

    def test_campaign_brief_full_lifecycle(self) -> None:
        adapter = MarketingDomainAdapter(publish_enabled=True)
        action = _make_marketing_action("campaign_brief")

        # Plan
        plan_steps = adapter.plan(action)
        action.plan = plan_steps
        action.advance_phase(ActionPhase.execute)
        assert len(plan_steps) == 3

        # Execute
        exec_steps = adapter.execute(action)
        action.execution_log = exec_steps
        action.advance_phase(ActionPhase.validate)
        assert len(exec_steps) == 2

        # Validate
        validation = adapter.validate(action)
        action.validation = validation
        action.advance_phase(ActionPhase.evidence)
        assert validation.passed is True

        # Evidence
        evidence = adapter.gather_evidence(action)
        action.evidence = evidence
        action.advance_phase(ActionPhase.publish)
        assert len(evidence) > 0

        # Publish
        pubs = adapter.publish(action)
        action.publications = pubs
        action.advance_phase(ActionPhase.monitor)
        assert len(pubs) == 1

        # Monitor
        monitors = adapter.monitor(action)
        action.monitors = monitors
        action.advance_phase(ActionPhase.learn)

        # Learn
        action.mark_done()
        lessons = adapter.learn(action)
        action.learnings = lessons

        # Final assertions
        assert action.status == ActionStatus.done
        assert action.phase == ActionPhase.learn
        assert action.domain.name == "marketing"

    def test_action_without_pr_assumptions(self) -> None:
        """Marketing actions work without GitHub PR concepts (AC from #122)."""
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("social_posts")

        steps = adapter.plan(action)
        exec_steps = adapter.execute(action)
        adapter.validate(action)

        # No step references git, PR, or GitHub
        all_descriptions = [s.description or "" for s in steps + exec_steps]
        for desc in all_descriptions:
            lower = desc.lower()
            assert "github" not in lower
            assert "pull request" not in lower
            assert "git " not in lower


# ---------------------------------------------------------------------------
# Snapshot / serialization tests (per AC: snapshot test for evidence/report)
# ---------------------------------------------------------------------------


class TestSnapshotSerialization:
    def test_evidence_snapshot(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("launch_checklist")
        action.validation = adapter.validate(action)
        evidence = adapter.gather_evidence(action)

        serialized = [json.loads(e.model_dump_json()) for e in evidence]
        kinds = [e["kind"] for e in serialized]
        assert "checklist-document" in kinds
        assert "approval-sign-off" in kinds
        assert "link-test-results" in kinds
        assert "validation-report" in kinds

    def test_validation_report_snapshot(self) -> None:
        adapter = MarketingDomainAdapter()
        action = _make_marketing_action("email_sequence")
        result = adapter.validate(action)

        data = json.loads(result.model_dump_json())
        assert data["passed"] is True
        check_names = [c["name"] for c in data["checks"]]
        assert "brand-checklist-passed" in check_names
        assert "claims-risk-review" in check_names
        assert "utm-parameters-set" in check_names

    def test_full_action_json_round_trip(self) -> None:
        adapter = MarketingDomainAdapter(publish_enabled=True)
        action = _make_marketing_action("content_calendar")
        action.plan = adapter.plan(action)
        action.execution_log = adapter.execute(action)
        action.validation = adapter.validate(action)
        action.evidence = adapter.gather_evidence(action)
        action.publications = adapter.publish(action)

        dump = json.loads(action.model_dump_json())
        restored = Action.model_validate(dump)
        assert restored.domain.name == "marketing"
        assert restored.metadata["template"] == "content_calendar"
        assert len(restored.evidence) > 0
