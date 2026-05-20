"""Tests for deterministic task-to-repo routing."""

from __future__ import annotations

from pathlib import Path

import pytest

from sendsprint.models.sprint import Sprint, SprintItem
from sendsprint.models.workspace import RepoConfig
from sendsprint.operational_memory import OperationalMemoryStore
from sendsprint.planning import build_delivery_plan
from sendsprint.policy import AutonomyPolicy
from sendsprint.routing import (
    RoutingConfidenceError,
    confidence_gate_warnings,
    route_item_to_repo,
)
from sendsprint.tech import TechFingerprint


def _item(
    *,
    key: str = "APP-1",
    title: str = "Update task",
    labels: list[str] | None = None,
    acceptance_criteria: str | None = None,
    description: str | None = None,
) -> SprintItem:
    return SprintItem(
        id=key,
        key=key,
        type="Task",
        title=title,
        description=description,
        status="New",
        labels=labels or [],
        acceptance_criteria=acceptance_criteria,
    )


def _fp(
    repo_path: str = "/tmp/repo",
    *,
    roles: list[str] | None = None,
    techs: list[str] | None = None,
) -> TechFingerprint:
    return TechFingerprint(
        repo_path=repo_path,
        roles=roles or [],
        techs=techs or [],
    )


def test_explicit_repo_rule_routes_only_named_repository() -> None:
    item = _item(labels=["repo:web-app"])
    web = RepoConfig(name="web-app", path="web", role="front", tech="react")
    api = RepoConfig(name="orders-api", path="api", role="api", tech="fastapi")

    web_decision = route_item_to_repo(
        item,
        web,
        _fp("/tmp/web", roles=["front"], techs=["react"]),
        repo_path=Path("/tmp/web"),
    )
    api_decision = route_item_to_repo(
        item,
        api,
        _fp("/tmp/api", roles=["back"], techs=["fastapi"]),
        repo_path=Path("/tmp/api"),
    )

    assert web_decision.match is True
    assert web_decision.confidence == "high"
    assert "explicit repo/project" in web_decision.reason
    assert api_decision.match is False


def test_capability_match_uses_title_and_acceptance_criteria() -> None:
    item = _item(
        title="Reconcile refund ledger",
        acceptance_criteria="Payments API returns the refund balance by transaction.",
    )
    repo = RepoConfig(name="payments-api", path="services/payments-api", role="api")

    decision = route_item_to_repo(
        item,
        repo,
        _fp("/tmp/services/payments-api", roles=["back"], techs=["fastapi"]),
        repo_path=Path("/tmp/services/payments-api"),
    )

    assert decision.match is True
    assert decision.confidence == "medium"
    assert decision.reason == "task text matched repo capability"


def test_operational_memory_routing_override_adds_capability_terms(tmp_path) -> None:
    repo_path = tmp_path / "billing-service"
    repo_path.mkdir()
    store = OperationalMemoryStore(tmp_path)
    store.remember("billing-service", "routing.capabilities", "invoice, receivables")
    item = _item(title="Fix invoice aging calculation")
    repo = RepoConfig(name="billing-service", path="billing-service", role="api")

    decision = route_item_to_repo(
        item,
        repo,
        _fp(str(repo_path), roles=["back"], techs=["python"]),
        repo_path=repo_path,
    )

    assert decision.match is True
    assert decision.confidence == "medium"
    assert "capability" in decision.reason


def test_low_confidence_route_warns_in_plan_and_blocks_execution(tmp_path) -> None:
    item = _item(title="Update wording")
    repo = RepoConfig(name="api", path="api", role="api")
    repo_path = tmp_path / "api"
    repo_path.mkdir()

    def detect(path: Path) -> TechFingerprint:
        return _fp(str(path), roles=["back"], techs=["python"])

    def branch_for_task(
        task: SprintItem,
        fp: TechFingerprint,
        repo_cfg: RepoConfig | None,
    ) -> str:
        del task, fp, repo_cfg
        return "feature/app-1"

    plan = build_delivery_plan(
        Sprint(id="1", name="Sprint 1", items=[item]),
        [(repo, repo_path)],
        branch_for_task=branch_for_task,
        detect_fingerprint=detect,
        default_target_branch="main",
        autonomy_policy=AutonomyPolicy(level="plan"),
    )

    assert plan.deliveries[0].confidence == "medium"
    assert plan.warnings == []

    decision = route_item_to_repo(
        item,
        repo,
        detect(repo_path),
        repo_path=repo_path,
        single_repo=False,
    )
    assert decision.confidence == "low"
    assert confidence_gate_warnings([decision], AutonomyPolicy(level="plan"))
    with pytest.raises(RoutingConfidenceError):
        confidence_gate_warnings([decision], AutonomyPolicy(level="execute"))


def test_low_confidence_multi_repo_plan_blocks_execution_policy(tmp_path) -> None:
    item = _item(title="Update wording")
    repo = RepoConfig(name="api", path="api", role="api")
    repo_path = tmp_path / "api"
    repo_path.mkdir()
    web_path = tmp_path / "web"
    web_path.mkdir()

    def detect(path: Path) -> TechFingerprint:
        return _fp(str(path), roles=["back"], techs=["python"])

    def branch_for_task(
        task: SprintItem,
        fp: TechFingerprint,
        repo_cfg: RepoConfig | None,
    ) -> str:
        del task, fp, repo_cfg
        return "feature/app-1"

    plan = build_delivery_plan(
        Sprint(id="1", name="Sprint 1", items=[item]),
        [(repo, repo_path), (RepoConfig(name="web", path="web", role="front"), web_path)],
        branch_for_task=branch_for_task,
        detect_fingerprint=detect,
        default_target_branch="main",
        autonomy_policy=AutonomyPolicy(level="plan"),
    )

    assert [delivery.confidence for delivery in plan.deliveries] == ["low", "low"]
    assert len(plan.warnings) == 2

    with pytest.raises(RoutingConfidenceError):
        build_delivery_plan(
            Sprint(id="1", name="Sprint 1", items=[item]),
            [(repo, repo_path), (RepoConfig(name="web", path="web", role="front"), web_path)],
            branch_for_task=branch_for_task,
            detect_fingerprint=detect,
            default_target_branch="main",
            autonomy_policy=AutonomyPolicy(level="execute"),
        )


def test_backwards_role_fallback_matches_inferred_front_scope() -> None:
    item = _item(title="Ajustar tela de aprovacao")
    front = RepoConfig(name="web", path="web", role="front", tech="react")
    api = RepoConfig(name="api", path="api", role="api", tech="fastapi")

    front_decision = route_item_to_repo(
        item,
        front,
        _fp("/tmp/web", roles=["front"], techs=["react"]),
        repo_path=Path("/tmp/web"),
    )
    api_decision = route_item_to_repo(
        item,
        api,
        _fp("/tmp/api", roles=["back"], techs=["fastapi"]),
        repo_path=Path("/tmp/api"),
    )

    assert front_decision.match is True
    assert front_decision.confidence == "medium"
    assert "backwards-compatible role fallback" in front_decision.reason
    assert api_decision.match is False
