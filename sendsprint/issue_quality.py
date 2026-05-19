"""Issue quality scoring, acceptance parsing, and test intent generation."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

TestLevel = Literal["unit", "integration", "e2e", "smoke"]


class TestIntent(BaseModel):
    """Outcome-focused validation intent derived from issue context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    level: TestLevel
    rationale: str
    source: str


class IssueQualityReport(BaseModel):
    """Scored snapshot of whether an issue is ready for autonomous execution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    score: int
    threshold: int = 70
    passes: bool
    dimensions: dict[str, bool]
    missing_sections: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    suggested_acceptance_criteria: list[str] = Field(default_factory=list)
    suggested_test_plan: list[TestIntent] = Field(default_factory=list)
    planning_needed: bool = False
    summary: str


_FRONTEND_KEYWORDS = {
    "ui",
    "screen",
    "page",
    "browser",
    "modal",
    "button",
    "form",
    "dashboard",
    "frontend",
    "layout",
    "click",
    "navigation",
    "visual",
}
_BACKEND_KEYWORDS = {
    "api",
    "endpoint",
    "request",
    "response",
    "database",
    "query",
    "service",
    "backend",
    "webhook",
    "integration",
    "persist",
    "queue",
}
_CLI_KEYWORDS = {
    "cli",
    "command",
    "terminal",
    "stdout",
    "stderr",
    "exit code",
}
_DOCS_KEYWORDS = {"docs", "documentation", "readme", "guide", "tutorial", "example"}
_CONSTRAINT_PATTERNS = (
    r"\bwithout\b",
    r"\bmust not\b",
    r"\bdo not\b",
    r"\bavoid\b",
    r"\bpreserve\b",
    r"\bkeep\b",
    r"\bconstraint\b",
)
_EVIDENCE_PATTERNS = (
    r"\bscreenshot\b",
    r"\blog\b",
    r"\btrace\b",
    r"\berror\b",
    r"\bexception\b",
    r"\bactual\b",
    r"\bexpected\b",
)
_REPRO_PATTERNS = (
    r"steps to reproduce",
    r"repro",
    r"how to reproduce",
    r"1\.",
    r"2\.",
    r"given .* when .* then",
)
_TEST_PLAN_PATTERNS = (
    r"\btest plan\b",
    r"\bvalidation\b",
    r"\bpytest\b",
    r"\bplaywright\b",
    r"\bunit test\b",
    r"\be2e\b",
    r"\bintegration test\b",
    r"\bsmoke\b",
)


def parse_acceptance_criteria(raw: str | Iterable[str] | None) -> list[str]:
    """Normalize acceptance criteria from markdown, prose, or iterables."""
    if raw is None:
        return []
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return []
        lines = [line.strip() for line in text.splitlines() if line.strip()]
    else:
        lines = [str(item).strip() for item in raw if str(item).strip()]

    criteria: list[str] = []
    for line in lines:
        cleaned = re.sub(r"^(acceptance criteria|criteria|aceite)\s*:?\s*", "", line, flags=re.I)
        cleaned = re.sub(r"^[-*]\s*\[[ xX]?\]\s*", "", cleaned)
        cleaned = re.sub(r"^[-*+]\s*", "", cleaned)
        cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned)
        if not cleaned:
            continue
        parts = [
            part.strip(" .") for part in re.split(r"\s*;\s*|\s*\|\s*", cleaned) if part.strip()
        ]
        if parts:
            criteria.extend(parts)
        else:
            criteria.append(cleaned.strip(" ."))

    seen: set[str] = set()
    normalized: list[str] = []
    for item in criteria:
        key = _normalize(item)
        if key and key not in seen:
            seen.add(key)
            normalized.append(item)
    return normalized


def analyze_issue_quality(
    *,
    title: str,
    description: str | None = None,
    acceptance_criteria: str | Iterable[str] | None = None,
    labels: Iterable[str] | None = None,
    comments: Iterable[str] | None = None,
    attachments: Iterable[str] | None = None,
    issue_type: str | None = None,
    threshold: int = 70,
) -> IssueQualityReport:
    """Score issue readiness and propose missing planning details."""
    description = (description or "").strip()
    labels_list = [label for label in labels or [] if label]
    comment_list = [comment for comment in comments or [] if comment]
    attachment_list = [attachment for attachment in attachments or [] if attachment]
    criteria = parse_acceptance_criteria(acceptance_criteria)
    combined = "\n".join(
        part
        for part in [title, description, " ".join(labels_list), "\n".join(comment_list)]
        if part
    )

    dimensions = {
        "objective": bool(title.strip()),
        "scope": _has_scope_signal(description, labels_list),
        "acceptance_criteria": bool(criteria),
        "test_plan": _has_pattern(combined, _TEST_PLAN_PATTERNS) or bool(criteria),
        "constraints": _has_pattern(combined, _CONSTRAINT_PATTERNS),
        "evidence": bool(attachment_list) or _has_pattern(combined, _EVIDENCE_PATTERNS),
        "reproduction_steps": _has_pattern(combined, _REPRO_PATTERNS),
    }

    weights = {
        "objective": 15,
        "scope": 15,
        "acceptance_criteria": 20,
        "test_plan": 15,
        "constraints": 10,
        "evidence": 15,
        "reproduction_steps": 10,
    }
    score = sum(weights[name] for name, present in dimensions.items() if present)
    missing_sections = [name for name, present in dimensions.items() if not present]

    suggested_acceptance = criteria or suggest_acceptance_criteria(
        title=title,
        description=description,
        issue_type=issue_type,
    )
    suggested_test_plan = generate_test_intents(
        title=title,
        description=description,
        acceptance_criteria=suggested_acceptance,
        labels=labels_list,
    )
    passes = score >= threshold
    summary = (
        f"Issue quality score {score}/{sum(weights.values())}; "
        f"missing {', '.join(missing_sections) if missing_sections else 'no core sections'}"
    )
    return IssueQualityReport(
        score=score,
        threshold=threshold,
        passes=passes,
        dimensions=dimensions,
        missing_sections=missing_sections,
        acceptance_criteria=criteria,
        suggested_acceptance_criteria=suggested_acceptance,
        suggested_test_plan=suggested_test_plan,
        planning_needed=(not passes) or bool(missing_sections),
        summary=summary,
    )


def suggest_acceptance_criteria(
    *,
    title: str,
    description: str | None = None,
    issue_type: str | None = None,
) -> list[str]:
    """Generate concise, outcome-oriented acceptance criteria when missing."""
    context = " ".join(
        part for part in [title, description or "", issue_type or ""] if part
    ).lower()
    suggestions: list[str] = []
    if any(keyword in context for keyword in _FRONTEND_KEYWORDS):
        suggestions.append(
            "The user-facing flow completes successfully with the expected UI state."
        )
    if any(keyword in context for keyword in _BACKEND_KEYWORDS):
        suggestions.append(
            "The service/API returns the expected result and persists any required data."
        )
    if any(keyword in context for keyword in _CLI_KEYWORDS):
        suggestions.append(
            "The command exits successfully and prints the expected operator-facing output."
        )
    if any(keyword in context for keyword in _DOCS_KEYWORDS):
        suggestions.append(
            "The documentation/example is accurate, runnable, and points to the intended workflow."
        )
    suggestions.append(
        "A regression check proves the described behavior works without breaking adjacent flows."
    )
    suggestions.append("Any stated constraints or compatibility expectations remain preserved.")

    seen: set[str] = set()
    deduped: list[str] = []
    for item in suggestions:
        key = _normalize(item)
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    return deduped[:4]


def generate_test_intents(
    *,
    title: str,
    description: str | None = None,
    acceptance_criteria: str | Iterable[str] | None = None,
    labels: Iterable[str] | None = None,
) -> list[TestIntent]:
    """Turn acceptance criteria into focused validation intents."""
    criteria = parse_acceptance_criteria(acceptance_criteria)
    if not criteria:
        criteria = suggest_acceptance_criteria(title=title, description=description)

    context = " ".join(
        part
        for part in [title, description or "", " ".join(label for label in labels or [] if label)]
        if part
    ).lower()
    intents: list[TestIntent] = []
    for criterion in criteria:
        level = _classify_test_level(criterion.lower(), context)
        intents.append(
            TestIntent(
                title=_intent_title(criterion),
                level=level,
                rationale=_rationale_for_level(level),
                source=criterion,
            )
        )
    return intents


def build_quality_comment(report: IssueQualityReport) -> str:
    """Render a concise planning comment for weak issues."""
    suggested_criteria = (
        "\n".join(f"- [ ] {item}" for item in report.suggested_acceptance_criteria)
        or "- [ ] Refine acceptance criteria"
    )
    suggested_tests = (
        "\n".join(f"- {intent.level}: {intent.title}" for intent in report.suggested_test_plan)
        or "- Add focused validation checks"
    )
    missing = ", ".join(report.missing_sections) or "none"
    return f"""## SendSprint Issue Quality

- Score: {report.score}/{report.threshold}
- Missing sections: {missing}
- Planning needed: {report.planning_needed}

### Suggested Acceptance Criteria
{suggested_criteria}

### Suggested Validation Plan
{suggested_tests}
"""


def _has_scope_signal(description: str, labels: list[str]) -> bool:
    if len(description) >= 40:
        return True
    scope_labels = [
        label for label in labels if label.startswith(("scope:", "area:", "component:"))
    ]
    return bool(scope_labels)


def _has_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.I | re.S) for pattern in patterns)


def _classify_test_level(criterion: str, context: str) -> TestLevel:
    if any(keyword in criterion for keyword in _FRONTEND_KEYWORDS):
        return "e2e"
    if any(keyword in criterion for keyword in _BACKEND_KEYWORDS):
        return "integration"
    if any(keyword in criterion for keyword in _DOCS_KEYWORDS | _CLI_KEYWORDS):
        return "smoke"
    if any(keyword in context for keyword in _FRONTEND_KEYWORDS):
        return "e2e"
    if any(keyword in context for keyword in _BACKEND_KEYWORDS):
        return "integration"
    return "unit"


def _intent_title(criterion: str) -> str:
    text = criterion.strip().rstrip(".")
    if not text:
        return "Validate expected outcome"
    text = text[0].upper() + text[1:]
    return f"Validate that {text[0].lower() + text[1:]}"


def _rationale_for_level(level: TestLevel) -> str:
    reasons = {
        "unit": "Prefer a narrow assertion on the business rule instead of implementation details.",
        "integration": (
            "Exercise the contract between collaborating components and persisted state."
        ),
        "e2e": "Verify the operator or user-visible flow from the outside in.",
        "smoke": "Confirm the critical path stays runnable without over-specifying internals.",
    }
    return reasons[level]


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()
