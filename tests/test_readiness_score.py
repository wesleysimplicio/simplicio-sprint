"""Tests for the delivery readiness score (#101)."""

from __future__ import annotations

import pytest

from sendsprint.readiness_score import (
    DEFAULT_AUTO_PUBLISH_THRESHOLD,
    DEFAULT_HUMAN_APPROVAL_THRESHOLD,
    DEFAULT_WEIGHTS,
    DeliveryReadinessScore,
    ReadinessVerdict,
    ScoreComponent,
    build_default_components,
)

# ---------------------------------------------------------------------------
# ScoreComponent model
# ---------------------------------------------------------------------------


class TestScoreComponent:
    def test_basic_creation(self) -> None:
        c = ScoreComponent(name="lint", weight=0.25, raw_score=90, details="ok")
        assert c.name == "lint"
        assert c.weight == 0.25
        assert c.raw_score == 90
        assert c.details == "ok"

    def test_weighted_score(self) -> None:
        c = ScoreComponent(name="x", weight=0.5, raw_score=80)
        assert c.weighted_score == 40.0

    def test_frozen(self) -> None:
        c = ScoreComponent(name="x", weight=0.1, raw_score=50)
        with pytest.raises(ValueError):
            c.raw_score = 99  # type: ignore[misc]

    def test_weight_bounds(self) -> None:
        with pytest.raises(ValueError):
            ScoreComponent(name="x", weight=1.5, raw_score=50)
        with pytest.raises(ValueError):
            ScoreComponent(name="x", weight=-0.1, raw_score=50)

    def test_raw_score_bounds(self) -> None:
        with pytest.raises(ValueError):
            ScoreComponent(name="x", weight=0.1, raw_score=101)
        with pytest.raises(ValueError):
            ScoreComponent(name="x", weight=0.1, raw_score=-1)

    def test_default_details_empty(self) -> None:
        c = ScoreComponent(name="x", weight=0.1, raw_score=50)
        assert c.details == ""


# ---------------------------------------------------------------------------
# ReadinessVerdict enum
# ---------------------------------------------------------------------------


class TestReadinessVerdict:
    def test_values(self) -> None:
        assert ReadinessVerdict.auto_publish.value == "auto_publish"
        assert ReadinessVerdict.needs_human_approval.value == "needs_human_approval"
        assert ReadinessVerdict.blocked.value == "blocked"

    def test_member_count(self) -> None:
        assert len(ReadinessVerdict) == 3


# ---------------------------------------------------------------------------
# DeliveryReadinessScore — calculate
# ---------------------------------------------------------------------------


class TestCalculate:
    def test_all_perfect(self) -> None:
        components = build_default_components(
            quality_gate_score=100,
            diff_verifier_score=100,
            validations_score=100,
            evidence_completeness_score=100,
            ci_status_score=100,
            review_status_score=100,
        )
        score = DeliveryReadinessScore.calculate(components)
        assert score == pytest.approx(100.0)

    def test_all_zero(self) -> None:
        components = build_default_components()
        score = DeliveryReadinessScore.calculate(components)
        assert score == pytest.approx(0.0)

    def test_mixed_scores(self) -> None:
        components = build_default_components(
            quality_gate_score=80,
            diff_verifier_score=60,
            validations_score=70,
            evidence_completeness_score=50,
            ci_status_score=90,
            review_status_score=40,
        )
        # 0.25*80 + 0.15*60 + 0.20*70 + 0.15*50 + 0.15*90 + 0.10*40
        expected = 20.0 + 9.0 + 14.0 + 7.5 + 13.5 + 4.0
        score = DeliveryReadinessScore.calculate(components)
        assert score == pytest.approx(expected)

    def test_empty_components(self) -> None:
        assert DeliveryReadinessScore.calculate([]) == 0.0

    def test_weights_must_sum_to_one(self) -> None:
        components = [
            ScoreComponent(name="a", weight=0.5, raw_score=100),
            ScoreComponent(name="b", weight=0.3, raw_score=100),
        ]
        with pytest.raises(ValueError, match="must sum to 1.0"):
            DeliveryReadinessScore.calculate(components)

    def test_deterministic(self) -> None:
        """Same inputs always produce the same score."""
        components = build_default_components(
            quality_gate_score=75,
            diff_verifier_score=85,
            validations_score=60,
            evidence_completeness_score=90,
            ci_status_score=70,
            review_status_score=55,
        )
        scores = [DeliveryReadinessScore.calculate(components) for _ in range(100)]
        assert all(s == scores[0] for s in scores)


# ---------------------------------------------------------------------------
# DeliveryReadinessScore — get_verdict
# ---------------------------------------------------------------------------


class TestGetVerdict:
    def test_auto_publish(self) -> None:
        drs = DeliveryReadinessScore()
        assert drs.get_verdict(95.0) == ReadinessVerdict.auto_publish
        assert drs.get_verdict(80.0) == ReadinessVerdict.auto_publish

    def test_needs_human_approval(self) -> None:
        drs = DeliveryReadinessScore()
        assert drs.get_verdict(79.9) == ReadinessVerdict.needs_human_approval
        assert drs.get_verdict(50.0) == ReadinessVerdict.needs_human_approval

    def test_blocked(self) -> None:
        drs = DeliveryReadinessScore()
        assert drs.get_verdict(49.9) == ReadinessVerdict.blocked
        assert drs.get_verdict(0.0) == ReadinessVerdict.blocked

    def test_custom_thresholds(self) -> None:
        drs = DeliveryReadinessScore(auto_publish_threshold=90, human_approval_threshold=60)
        assert drs.get_verdict(90.0) == ReadinessVerdict.auto_publish
        assert drs.get_verdict(89.9) == ReadinessVerdict.needs_human_approval
        assert drs.get_verdict(60.0) == ReadinessVerdict.needs_human_approval
        assert drs.get_verdict(59.9) == ReadinessVerdict.blocked

    def test_invalid_thresholds(self) -> None:
        with pytest.raises(ValueError, match="must be less than"):
            DeliveryReadinessScore(auto_publish_threshold=50, human_approval_threshold=50)
        with pytest.raises(ValueError, match="must be less than"):
            DeliveryReadinessScore(auto_publish_threshold=50, human_approval_threshold=60)


# ---------------------------------------------------------------------------
# DeliveryReadinessScore — format_summary
# ---------------------------------------------------------------------------


class TestFormatSummary:
    def test_contains_score_and_verdict(self) -> None:
        components = build_default_components(quality_gate_score=100)
        score = DeliveryReadinessScore.calculate(components)
        summary = DeliveryReadinessScore.format_summary(
            components, score, ReadinessVerdict.needs_human_approval
        )
        assert "25.0/100" in summary
        assert "needs_human_approval" in summary

    def test_contains_all_component_names(self) -> None:
        components = build_default_components()
        summary = DeliveryReadinessScore.format_summary(components, 0.0, ReadinessVerdict.blocked)
        for name in DEFAULT_WEIGHTS:
            assert name in summary

    def test_details_section_present(self) -> None:
        components = build_default_components(
            quality_gate_score=80,
            quality_gate_details="all checks passed",
        )
        score = DeliveryReadinessScore.calculate(components)
        summary = DeliveryReadinessScore.format_summary(components, score, ReadinessVerdict.blocked)
        assert "### Details" in summary
        assert "all checks passed" in summary

    def test_no_details_section_when_empty(self) -> None:
        components = build_default_components()
        summary = DeliveryReadinessScore.format_summary(components, 0.0, ReadinessVerdict.blocked)
        assert "### Details" not in summary


# ---------------------------------------------------------------------------
# evaluate convenience method
# ---------------------------------------------------------------------------


class TestEvaluate:
    def test_high_score_auto_publish(self) -> None:
        components = build_default_components(
            quality_gate_score=100,
            diff_verifier_score=100,
            validations_score=100,
            evidence_completeness_score=100,
            ci_status_score=100,
            review_status_score=100,
        )
        drs = DeliveryReadinessScore()
        score, verdict, summary = drs.evaluate(components)
        assert score == pytest.approx(100.0)
        assert verdict == ReadinessVerdict.auto_publish
        assert "auto_publish" in summary

    def test_medium_score_needs_approval(self) -> None:
        components = build_default_components(
            quality_gate_score=70,
            diff_verifier_score=60,
            validations_score=65,
            evidence_completeness_score=55,
            ci_status_score=70,
            review_status_score=50,
        )
        drs = DeliveryReadinessScore()
        score, verdict, _summary = drs.evaluate(components)
        assert DEFAULT_HUMAN_APPROVAL_THRESHOLD <= score < DEFAULT_AUTO_PUBLISH_THRESHOLD
        assert verdict == ReadinessVerdict.needs_human_approval

    def test_low_score_blocked(self) -> None:
        components = build_default_components(
            quality_gate_score=30,
            diff_verifier_score=20,
            validations_score=10,
            evidence_completeness_score=15,
            ci_status_score=25,
            review_status_score=10,
        )
        drs = DeliveryReadinessScore()
        score, verdict, _summary = drs.evaluate(components)
        assert score < DEFAULT_HUMAN_APPROVAL_THRESHOLD
        assert verdict == ReadinessVerdict.blocked


# ---------------------------------------------------------------------------
# build_default_components factory
# ---------------------------------------------------------------------------


class TestBuildDefaultComponents:
    def test_returns_six_components(self) -> None:
        components = build_default_components()
        assert len(components) == 6

    def test_weights_sum_to_one(self) -> None:
        components = build_default_components()
        total = sum(c.weight for c in components)
        assert total == pytest.approx(1.0)

    def test_default_scores_are_zero(self) -> None:
        components = build_default_components()
        assert all(c.raw_score == 0 for c in components)

    def test_names_match_default_weights(self) -> None:
        components = build_default_components()
        names = {c.name for c in components}
        assert names == set(DEFAULT_WEIGHTS.keys())

    def test_custom_scores_applied(self) -> None:
        components = build_default_components(quality_gate_score=95, ci_status_score=88)
        by_name = {c.name: c for c in components}
        assert by_name["quality_gate"].raw_score == 95
        assert by_name["ci_status"].raw_score == 88
        assert by_name["diff_verifier"].raw_score == 0


# ---------------------------------------------------------------------------
# DEFAULT_WEIGHTS constant
# ---------------------------------------------------------------------------


class TestDefaultWeights:
    def test_sum_to_one(self) -> None:
        assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)

    def test_six_components(self) -> None:
        assert len(DEFAULT_WEIGHTS) == 6

    def test_expected_keys(self) -> None:
        expected = {
            "quality_gate",
            "diff_verifier",
            "validations",
            "evidence_completeness",
            "ci_status",
            "review_status",
        }
        assert set(DEFAULT_WEIGHTS.keys()) == expected
