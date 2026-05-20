"""Delivery readiness score — objective, deterministic 0-100 score
combining quality gate, diff verifier, validations, evidence, CI, and
review signals into a publish/approval/block verdict.

Issue: #101
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class ScoreComponent(BaseModel):
    """A single scored dimension contributing to the overall readiness."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    weight: float = Field(ge=0.0, le=1.0)
    raw_score: int = Field(ge=0, le=100)
    details: str = ""

    @property
    def weighted_score(self) -> float:
        return self.weight * self.raw_score


class ReadinessVerdict(StrEnum):
    """Outcome derived from the aggregate readiness score."""

    auto_publish = "auto_publish"
    needs_human_approval = "needs_human_approval"
    blocked = "blocked"


# ---------------------------------------------------------------------------
# Default thresholds
# ---------------------------------------------------------------------------

DEFAULT_AUTO_PUBLISH_THRESHOLD = 80
DEFAULT_HUMAN_APPROVAL_THRESHOLD = 50

# ---------------------------------------------------------------------------
# Default component weights (must sum to 1.0)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "quality_gate": 0.25,
    "diff_verifier": 0.15,
    "validations": 0.20,
    "evidence_completeness": 0.15,
    "ci_status": 0.15,
    "review_status": 0.10,
}


# ---------------------------------------------------------------------------
# DeliveryReadinessScore
# ---------------------------------------------------------------------------


class DeliveryReadinessScore:
    """Calculate a deterministic delivery readiness score from components.

    Parameters
    ----------
    auto_publish_threshold:
        Minimum aggregate score for ``auto_publish`` verdict (default 80).
    human_approval_threshold:
        Minimum aggregate score for ``needs_human_approval`` verdict (default 50).
        Scores below this threshold produce ``blocked``.
    """

    def __init__(
        self,
        *,
        auto_publish_threshold: int = DEFAULT_AUTO_PUBLISH_THRESHOLD,
        human_approval_threshold: int = DEFAULT_HUMAN_APPROVAL_THRESHOLD,
    ) -> None:
        if human_approval_threshold >= auto_publish_threshold:
            raise ValueError("human_approval_threshold must be less than auto_publish_threshold")
        self.auto_publish_threshold = auto_publish_threshold
        self.human_approval_threshold = human_approval_threshold

    # -- calculation --------------------------------------------------------

    @staticmethod
    def calculate(components: list[ScoreComponent]) -> float:
        """Return the weighted aggregate score (0-100).

        Deterministic: same components always produce the same score.
        Weights must sum to 1.0 (within floating-point tolerance).
        """
        if not components:
            return 0.0

        total_weight = sum(c.weight for c in components)
        if abs(total_weight - 1.0) > 1e-6:
            raise ValueError(f"Component weights must sum to 1.0, got {total_weight:.6f}")

        return sum(c.weighted_score for c in components)

    # -- verdict ------------------------------------------------------------

    def get_verdict(self, score: float) -> ReadinessVerdict:
        """Map an aggregate score to a verdict."""
        if score >= self.auto_publish_threshold:
            return ReadinessVerdict.auto_publish
        if score >= self.human_approval_threshold:
            return ReadinessVerdict.needs_human_approval
        return ReadinessVerdict.blocked

    # -- formatting ---------------------------------------------------------

    @staticmethod
    def format_summary(
        components: list[ScoreComponent],
        score: float,
        verdict: ReadinessVerdict,
    ) -> str:
        """Build a human-readable Markdown summary of the score breakdown."""
        lines: list[str] = [
            f"## Delivery Readiness Score: {score:.1f}/100",
            f"**Verdict:** {verdict.value}",
            "",
            "| Component | Weight | Raw | Weighted |",
            "|-----------|--------|-----|----------|",
        ]
        for c in components:
            lines.append(f"| {c.name} | {c.weight:.0%} | {c.raw_score} | {c.weighted_score:.1f} |")
        lines.append("")

        details = [c for c in components if c.details]
        if details:
            lines.append("### Details")
            for c in details:
                lines.append(f"- **{c.name}:** {c.details}")

        return "\n".join(lines)

    # -- convenience --------------------------------------------------------

    def evaluate(self, components: list[ScoreComponent]) -> tuple[float, ReadinessVerdict, str]:
        """One-shot: calculate score, derive verdict, format summary."""
        score = self.calculate(components)
        verdict = self.get_verdict(score)
        summary = self.format_summary(components, score, verdict)
        return score, verdict, summary


# ---------------------------------------------------------------------------
# Factory helpers
# ---------------------------------------------------------------------------


def build_default_components(
    *,
    quality_gate_score: int = 0,
    quality_gate_details: str = "",
    diff_verifier_score: int = 0,
    diff_verifier_details: str = "",
    validations_score: int = 0,
    validations_details: str = "",
    evidence_completeness_score: int = 0,
    evidence_completeness_details: str = "",
    ci_status_score: int = 0,
    ci_status_details: str = "",
    review_status_score: int = 0,
    review_status_details: str = "",
) -> list[ScoreComponent]:
    """Build the standard six components with default weights."""
    return [
        ScoreComponent(
            name="quality_gate",
            weight=DEFAULT_WEIGHTS["quality_gate"],
            raw_score=quality_gate_score,
            details=quality_gate_details,
        ),
        ScoreComponent(
            name="diff_verifier",
            weight=DEFAULT_WEIGHTS["diff_verifier"],
            raw_score=diff_verifier_score,
            details=diff_verifier_details,
        ),
        ScoreComponent(
            name="validations",
            weight=DEFAULT_WEIGHTS["validations"],
            raw_score=validations_score,
            details=validations_details,
        ),
        ScoreComponent(
            name="evidence_completeness",
            weight=DEFAULT_WEIGHTS["evidence_completeness"],
            raw_score=evidence_completeness_score,
            details=evidence_completeness_details,
        ),
        ScoreComponent(
            name="ci_status",
            weight=DEFAULT_WEIGHTS["ci_status"],
            raw_score=ci_status_score,
            details=ci_status_details,
        ),
        ScoreComponent(
            name="review_status",
            weight=DEFAULT_WEIGHTS["review_status"],
            raw_score=review_status_score,
            details=review_status_details,
        ),
    ]
