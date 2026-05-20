"""Domain-agnostic action playbook catalog."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ActionDomain = Literal["software", "marketing", "finance-content", "sales", "operations"]
ApprovalPolicy = Literal["none", "human-before-publish", "human-for-risky-actions"]


class ActionValidationRecipe(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    required_checks: list[str] = Field(default_factory=list)
    blocking_checks: list[str] = Field(default_factory=list)
    evidence_required: list[str] = Field(default_factory=list)


class ActionPlaybook(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    key: str
    domain: ActionDomain
    title: str
    description: str
    required_inputs: list[str] = Field(default_factory=list)
    optional_inputs: list[str] = Field(default_factory=list)
    default_steps: list[str] = Field(default_factory=list)
    validation: ActionValidationRecipe = Field(default_factory=ActionValidationRecipe)
    approval_policy: ApprovalPolicy = "human-before-publish"
    output_format: str = "evidence-bundle"
    publish_targets: list[str] = Field(default_factory=list)


BUILTIN_ACTIONS: tuple[ActionPlaybook, ...] = (
    ActionPlaybook(
        key="software.pr-delivery",
        domain="software",
        title="Validated pull-request delivery",
        description="Plan, implement, validate, evidence, publish PR, monitor review, and rework.",
        required_inputs=["repository", "issue_or_task", "definition_of_done"],
        optional_inputs=["target_branch", "workspace_file", "autonomy_level"],
        default_steps=[
            "inspect project map",
            "deduplicate related work",
            "plan implementation",
            "implement focused patch",
            "run focused validation",
            "prepare PR evidence",
            "monitor CI and review",
        ],
        validation=ActionValidationRecipe(
            required_checks=["lint", "tests", "diff-review", "duplicate-risk"],
            blocking_checks=["failing-tests", "unrelated-diff", "duplicate-pr"],
            evidence_required=["commands", "test-output", "diff-summary"],
        ),
        approval_policy="human-for-risky-actions",
        output_format="pull-request",
        publish_targets=["github"],
    ),
    ActionPlaybook(
        key="marketing.campaign-launch",
        domain="marketing",
        title="Campaign launch package",
        description="Build a measurable campaign package from brief to creative evidence.",
        required_inputs=["campaign_brief", "audience", "offer", "channels"],
        optional_inputs=["brand_voice", "budget", "deadline", "approval_owner"],
        default_steps=[
            "research market and competitors",
            "define positioning and offer",
            "draft landing-page copy",
            "generate creative variants",
            "write email and ad variants",
            "run compliance checklist",
            "prepare metrics and UTM plan",
        ],
        validation=ActionValidationRecipe(
            required_checks=["brand-check", "claims-review", "link-check", "utm-plan"],
            blocking_checks=["unsupported-claim", "missing-disclosure", "external-publish"],
            evidence_required=["brief", "drafts", "creative-assets", "approval-notes"],
        ),
        approval_policy="human-before-publish",
        output_format="campaign-evidence-bundle",
        publish_targets=["draft", "ads-manager", "cms", "email-platform"],
    ),
)


def list_action_playbooks(source: str | Path | None = None) -> list[ActionPlaybook]:
    if source is None:
        return list(BUILTIN_ACTIONS)
    target = Path(source)
    data = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("action catalog must be a JSON list")
    return [ActionPlaybook.model_validate(item) for item in data]


def find_action_playbook(key: str, source: str | Path | None = None) -> ActionPlaybook | None:
    for item in list_action_playbooks(source):
        if item.key == key:
            return item
    return None


def write_action_catalog(path: str | Path, playbooks: list[ActionPlaybook] | None = None) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    items = playbooks or list(BUILTIN_ACTIONS)
    target.write_text(
        json.dumps([item.model_dump(mode="json") for item in items], indent=2) + "\n",
        encoding="utf-8",
    )
    return target
