"""Delivery planning helpers for dry-run, routing, and confidence scoring."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

from sendsprint.agents.story_task_planner import (
    delivery_items,
)
from sendsprint.models import Sprint
from sendsprint.models.sprint import SprintItem
from sendsprint.models.workspace import RepoConfig, WorkspaceConfig
from sendsprint.policy import AutonomyPolicy
from sendsprint.routing import (
    Confidence,
    confidence_gate_warnings,
    route_item_to_repo,
)
from sendsprint.routing import (
    confidence_for_item as routing_confidence_for_item,
)
from sendsprint.task_understanding import TaskUnderstandingReport, understand_sprint_item
from sendsprint.tech import TechFingerprint
from sendsprint.templates import select_validation_template


class PlannedDelivery(BaseModel):
    """One item/repo pair SendSprint intends to deliver."""

    item_key: str
    item_type: str
    title: str
    repo: str
    repo_role: str | None = None
    branch: str
    target_branch: str
    confidence: Confidence
    reason: str
    relationship: str = "none"
    worktree_path: str | None = None
    validation_template: str | None = None
    validation_commands: list[str] = Field(default_factory=list)
    task_understanding: TaskUnderstandingReport | None = None


class DeliveryPlan(BaseModel):
    """Structured dry-run output used by CLI and reports."""

    schema_version: str = "1.0"
    source: str
    sprint_id: str
    sprint_name: str
    deliveries: list[PlannedDelivery] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    autonomy_level: str = "plan"
    side_effects: dict[str, bool] = Field(default_factory=dict)
    llm: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    deploy_callback: dict[str, str | bool | None] = Field(default_factory=dict)
    release: dict[str, str | bool | None] = Field(default_factory=dict)

    @property
    def low_confidence_count(self) -> int:
        return sum(1 for delivery in self.deliveries if delivery.confidence == "low")

    def summary(self) -> str:
        return (
            f"{len(self.deliveries)} planned delivery item(s), "
            f"{self.low_confidence_count} low-confidence route(s)"
        )


def build_delivery_plan(
    sprint: Sprint,
    repos: list[tuple[RepoConfig | None, Path]],
    *,
    branch_for_task: Callable[[SprintItem, TechFingerprint, RepoConfig | None], str],
    detect_fingerprint: Callable[[Path], TechFingerprint],
    default_target_branch: str,
    autonomy_policy: AutonomyPolicy | None = None,
    llm: dict[str, str | int | float | bool | None] | None = None,
    deploy_callback: dict[str, str | bool | None] | None = None,
    release: dict[str, str | bool | None] | None = None,
    workspace: WorkspaceConfig | None = None,
) -> DeliveryPlan:
    """Build a read-only plan for item/repo delivery."""
    policy = autonomy_policy or AutonomyPolicy()
    plan = DeliveryPlan(
        source=sprint.source,
        sprint_id=sprint.id,
        sprint_name=sprint.name,
        autonomy_level=policy.level,
        side_effects=policy.side_effects(),
        llm=llm or {},
        deploy_callback=deploy_callback or {},
        release=release or {"enabled": False},
    )
    for item in delivery_items(sprint):
        matched = False
        repo_count = len(repos)
        understanding = understand_sprint_item(item, workspace)
        for repo_cfg, repo_path in repos:
            repo_role = repo_cfg.role if repo_cfg else None
            fp = detect_fingerprint(repo_path)
            decision = route_item_to_repo(
                item,
                repo_cfg,
                fp,
                repo_path=repo_path,
                task_understanding=understanding.model_dump(),
                single_repo=repo_count == 1,
            )
            if not decision.match:
                continue
            plan.warnings.extend(confidence_gate_warnings([decision], policy))
            matched = True
            branch = branch_for_task(item, fp, repo_cfg)
            target = (
                repo_cfg.pr_target_branch
                if repo_cfg and repo_cfg.pr_target_branch
                else default_target_branch
            )
            relationship = "parent" if item.parent_key else "related" if item.links else "none"
            template = select_validation_template(fp, repo_path)
            worktree_path = str(
                repo_path.parent / f"{repo_path.name}-wt-{branch.replace('/', '-')}"
            )
            plan.deliveries.append(
                PlannedDelivery(
                    item_key=item.key or item.id,
                    item_type=item.type,
                    title=item.title,
                    repo=str(repo_path),
                    repo_role=repo_role,
                    branch=branch,
                    target_branch=target,
                    confidence=decision.confidence,
                    reason=decision.reason,
                    relationship=relationship,
                    worktree_path=worktree_path,
                    validation_template=template.name,
                    validation_commands=template.commands(),
                    task_understanding=understanding,
                )
            )
        if not matched:
            plan.warnings.append(f"{item.key}: no compatible repository matched")
    return plan


def confidence_for_item(
    item: SprintItem,
    repo_role: str | None,
    fp: TechFingerprint,
) -> tuple[Confidence, str]:
    """Score how safely an item can be routed to a repo."""
    return routing_confidence_for_item(item, repo_role, fp)
