"""Publish delivery planning artifacts as GitHub Issues."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.issue_quality import IssueQualityReport, build_quality_comment
from sendsprint.planning import DeliveryPlan, PlannedDelivery
from sendsprint.policy import AutonomyPolicy
from sendsprint.trackers.github_issues import GitHubIssue, GitHubIssuesTracker

PlanningPublishMode = Literal["off", "umbrella", "per-delivery", "both"]
PlanningAction = Literal["created", "existing", "blocked", "dry-run"]


class PlanningPublishConfig(BaseModel):
    """Controls how planning issues are rendered and published."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    mode: PlanningPublishMode = "umbrella"
    dry_run: bool = False
    labels: list[str] = Field(default_factory=lambda: ["planning"])


class PlanningIssueDraft(BaseModel):
    """Issue payload ready for deduplication and publication."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    title: str
    body: str
    labels: list[str] = Field(default_factory=list)
    marker: str
    kind: Literal["umbrella", "delivery"]
    item_key: str | None = None


class PlanningPublishEntry(BaseModel):
    """Single dedupe/publish outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: PlanningAction
    title: str
    marker: str
    url: str | None = None
    reason: str | None = None


class PlanningPublishResult(BaseModel):
    """Aggregate planning issue publication outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entries: list[PlanningPublishEntry] = Field(default_factory=list)

    @property
    def created_count(self) -> int:
        return sum(1 for entry in self.entries if entry.action == "created")

    @property
    def blocked_count(self) -> int:
        return sum(1 for entry in self.entries if entry.action == "blocked")


def build_planning_issue_drafts(
    plan: DeliveryPlan,
    *,
    config: PlanningPublishConfig | None = None,
    quality_reports: dict[str, IssueQualityReport] | None = None,
) -> list[PlanningIssueDraft]:
    """Render umbrella and/or per-delivery planning issues from a delivery plan."""
    cfg = config or PlanningPublishConfig()
    if cfg.mode == "off":
        return []
    quality_reports = quality_reports or {}
    drafts: list[PlanningIssueDraft] = []
    if cfg.mode in {"umbrella", "both"}:
        marker = planning_marker(plan.sprint_id, kind="umbrella")
        drafts.append(
            PlanningIssueDraft(
                title=f"Planning: sprint {plan.sprint_id} - {plan.sprint_name}",
                body=_umbrella_body(plan, marker, quality_reports),
                labels=cfg.labels,
                marker=marker,
                kind="umbrella",
            )
        )
    if cfg.mode in {"per-delivery", "both"}:
        for delivery in plan.deliveries:
            marker = planning_marker(plan.sprint_id, item_key=delivery.item_key, kind="delivery")
            drafts.append(
                PlanningIssueDraft(
                    title=f"Planning: {delivery.item_key} -> {delivery.repo_role or 'repo'}",
                    body=_delivery_body(delivery, marker, quality_reports.get(delivery.item_key)),
                    labels=cfg.labels,
                    marker=marker,
                    kind="delivery",
                    item_key=delivery.item_key,
                )
            )
    return drafts


def publish_planning_issues(
    plan: DeliveryPlan,
    tracker: GitHubIssuesTracker,
    *,
    autonomy_policy: AutonomyPolicy | None = None,
    config: PlanningPublishConfig | None = None,
    quality_reports: dict[str, IssueQualityReport] | None = None,
    existing_issues: list[GitHubIssue] | None = None,
) -> PlanningPublishResult:
    """Create planning issues unless the policy blocks or dedupe finds existing ones."""
    cfg = config or PlanningPublishConfig()
    drafts = build_planning_issue_drafts(plan, config=cfg, quality_reports=quality_reports)
    policy = autonomy_policy or AutonomyPolicy()
    issues = existing_issues if existing_issues is not None else tracker.list_issues(state="all")
    entries: list[PlanningPublishEntry] = []

    for draft in drafts:
        existing = find_existing_issue(issues, draft)
        if existing is not None:
            entries.append(
                PlanningPublishEntry(
                    action="existing",
                    title=draft.title,
                    marker=draft.marker,
                    url=existing.url,
                    reason="matched by title or planning marker",
                )
            )
            continue
        if cfg.dry_run:
            entries.append(
                PlanningPublishEntry(
                    action="dry-run",
                    title=draft.title,
                    marker=draft.marker,
                    reason="dry-run enabled",
                )
            )
            continue
        if not policy.allows("comment-issue"):
            entries.append(
                PlanningPublishEntry(
                    action="blocked",
                    title=draft.title,
                    marker=draft.marker,
                    reason="autonomy policy blocks issue publication",
                )
            )
            continue
        url = tracker.create(draft.title, draft.body, labels=draft.labels)
        entries.append(
            PlanningPublishEntry(
                action="created",
                title=draft.title,
                marker=draft.marker,
                url=url,
            )
        )
    return PlanningPublishResult(entries=entries)


def find_existing_issue(
    issues: list[GitHubIssue],
    draft: PlanningIssueDraft,
) -> GitHubIssue | None:
    """Deduplicate by exact title or stable body marker."""
    for issue in issues:
        if issue.title.strip() == draft.title.strip():
            return issue
        if draft.marker and issue.body and draft.marker in issue.body:
            return issue
    return None


def planning_marker(sprint_id: str, *, kind: str, item_key: str | None = None) -> str:
    """Stable marker embedded in issue bodies for deduplication."""
    item_part = f":item={item_key}" if item_key else ""
    return f"<!-- sendsprint:planning:sprint={sprint_id}:kind={kind}{item_part} -->"


def build_planning_status_comment(
    *,
    event: str,
    pr_urls: list[str] | None = None,
    evidence_urls: list[str] | None = None,
    final_status: str | None = None,
) -> str:
    """Render an execution/progress update that can be posted back to a planning issue."""
    prs = "\n".join(f"- {url}" for url in pr_urls or []) or "- none yet"
    evidence = "\n".join(f"- {url}" for url in evidence_urls or []) or "- none yet"
    return f"""## SendSprint Execution Update

- Event: {event}
- Final status: {final_status or "in-progress"}

### Pull Requests
{prs}

### Evidence
{evidence}
"""


def _umbrella_body(
    plan: DeliveryPlan,
    marker: str,
    quality_reports: dict[str, IssueQualityReport],
) -> str:
    deliveries = []
    for delivery in plan.deliveries:
        quality = quality_reports.get(delivery.item_key)
        quality_line = (
            "; "
            f"quality={quality.score}/{quality.threshold}; "
            f"missing={', '.join(quality.missing_sections) or 'none'}"
            if quality
            else ""
        )
        deliveries.append(
            f"- {delivery.item_key}: {delivery.title} -> {delivery.repo} "
            f"(confidence={delivery.confidence}, branch={delivery.branch}){quality_line}"
        )
    warnings = "\n".join(f"- {warning}" for warning in plan.warnings) or "- none"
    delivery_lines = "\n".join(deliveries) or "- none"
    return f"""{marker}
## SendSprint Delivery Planning

Sprint: {plan.sprint_id} - {plan.sprint_name}
Source: {plan.source}
Autonomy: {plan.autonomy_level}

### Planned Deliveries
{delivery_lines}

### Warnings
{warnings}

### Execution Links
- Events: pending
- Pull requests: pending
- Evidence: pending
- Final status: pending
"""


def _delivery_body(
    delivery: PlannedDelivery,
    marker: str,
    quality_report: IssueQualityReport | None,
) -> str:
    validation = "\n".join(f"- `{command}`" for command in delivery.validation_commands) or "- none"
    quality_block = build_quality_comment(quality_report) if quality_report else ""
    return f"""{marker}
## SendSprint Delivery Planning

- Item: {delivery.item_key}
- Title: {delivery.title}
- Repo: {delivery.repo}
- Repo role: {delivery.repo_role or "n/a"}
- Branch: {delivery.branch}
- Target branch: {delivery.target_branch}
- Confidence: {delivery.confidence}
- Routing reason: {delivery.reason}
- Relationship: {delivery.relationship}
- Validation template: {delivery.validation_template or "n/a"}

### Validation Commands
{validation}

{quality_block}
### Execution Links
- Events: pending
- Pull requests: pending
- Evidence: pending
- Final status: pending
"""
