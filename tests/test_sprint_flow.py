"""Tests for SprintFlow helpers (branch naming per task)."""

from __future__ import annotations

import subprocess
from typing import Any
from unittest.mock import MagicMock

from sendsprint.flow.sprint_flow import SprintFlow
from sendsprint.models.reports import PrInfo, RunReport, StepReport
from sendsprint.models.sprint import Sprint, SprintItem
from sendsprint.models.workspace import (
    CodeGenerationConfig,
    DeployWorkflowConfig,
    RepoConfig,
    WorkspaceConfig,
)
from sendsprint.operators.base import BaseOperator
from sendsprint.policy import AutonomyPolicy
from sendsprint.tech import TechFingerprint


def _flow(workspace: WorkspaceConfig | None = None) -> SprintFlow:
    return SprintFlow(operator=MagicMock(), workspace=workspace)


def _item(key: str = "PROJ-42", title: str = "Add login") -> SprintItem:
    return SprintItem(id="1", key=key, type="Task", title=title, status="New")


def _fp() -> TechFingerprint:
    return TechFingerprint(repo_path="/tmp/x", languages=[], frameworks=[])


def test_branch_for_task_includes_key_and_title_slug() -> None:
    branch = _flow()._branch_for_task(_item("PROJ-42", "Add Login Flow"), _fp())
    assert branch.startswith("feature/")
    assert "42" in branch
    assert "add-login-flow" in branch


def test_branch_for_task_handles_missing_title() -> None:
    branch = _flow()._branch_for_task(_item("PROJ-7", ""), _fp())
    assert branch == "feature/7"


def test_branch_for_task_uses_id_when_key_missing() -> None:
    item = SprintItem(id="abc-123", key="", type="Task", title="x", status="New")
    branch = _flow()._branch_for_task(item, _fp())
    assert branch == "feature/123-x"


def test_branch_for_task_slugifies_special_chars() -> None:
    branch = _flow()._branch_for_task(_item("PROJ-1", "Fix: API/JSON 500!"), _fp())
    assert " " not in branch
    assert branch.count("/") == 1


def test_branch_for_task_uses_workspace_template() -> None:
    ws = WorkspaceConfig(root_path="/tmp", branch_name_template="bugfix/{key}")
    branch = _flow(ws)._branch_for_task(_item("PROJ-42", "Add Login Flow"), _fp())
    assert branch == "bugfix/proj-42"


def test_branch_for_task_uses_repo_template_over_workspace_template() -> None:
    ws = WorkspaceConfig(root_path="/tmp", branch_name_template="bugfix/{key}")
    repo = RepoConfig(name="api", path="api", branch_name_template="hotfix/{number}-{title}")
    branch = _flow(ws)._branch_for_task(_item("PROJ-42", "Add Login Flow"), _fp(), repo)
    assert branch == "hotfix/42-add-login-flow"


class FakeOperator(BaseOperator):
    source = "jira"

    def _api_available(self) -> bool:
        return True

    def _read_via_mcp(self, **kwargs: Any) -> Sprint:
        raise AssertionError("mcp should not be used")

    def _read_via_api(self, **kwargs: Any) -> Sprint:
        return Sprint(
            id="42",
            name="Sprint 42",
            source="jira",
            items=[_item("PROJ-42", "Criar tela de login")],
        )

    def _read_via_playwright(self, **kwargs: Any) -> Sprint:
        raise AssertionError("playwright should not be used")


def test_dry_run_builds_plan_without_importing_specs(tmp_path) -> None:
    flow = SprintFlow(operator=FakeOperator(transport="api"))

    result = flow.run(sprint_id=42, repo_path=str(tmp_path), dry_run=True)

    assert result.delivery_plan is not None
    assert result.delivery_plan.deliveries[0].branch == "feature/42-criar-tela-de-login"
    assert result.delivery_plan.deliveries[0].worktree_path is not None
    assert result.delivery_plan.deliveries[0].validation_template is not None
    assert result.delivery_plan.side_effects["push"] is False
    assert result.run_report is not None
    assert result.run_report.summary == "1 planned delivery item(s), 0 low-confidence route(s)"
    assert not (tmp_path / ".specs").exists()


def test_step_3_5_codegen_applies_generated_diff(tmp_path, monkeypatch) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    file_path = tmp_path / "foo.py"
    file_path.write_text("old\n", encoding="utf-8")

    diff = """diff --git a/foo.py b/foo.py
--- a/foo.py
+++ b/foo.py
@@ -1 +1 @@
-old
+new
"""

    class MockClient:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        def complete(self, prompt: str, system: str | None = None, max_tokens: int = 1024) -> str:
            del prompt, system, max_tokens
            return f"```diff\n{diff}```\n"

    monkeypatch.setattr("sendsprint.flow.sprint_flow.LlmClient", MockClient)
    flow = SprintFlow(
        operator=FakeOperator(transport="api"),
        code_generation=CodeGenerationConfig(enabled=True),
    )
    report = RunReport(workspace="ws")

    step = flow._step3_5_codegen(tmp_path, _item("PROJ-42", "Patch foo"), report)

    assert step is not None
    assert step.status == "ok"
    assert "generated diff applied" in (step.message or "")
    assert file_path.read_text(encoding="utf-8") == "new\n"


def test_step_11_deploy_uses_operator_ticket_updater(monkeypatch, tmp_path) -> None:
    captured: dict[str, Any] = {}

    class OperatorWithUpdater(FakeOperator):
        calls: list[tuple[str, str, str | None]]

        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.calls = []

        def update_status(self, item_key: str, status: str, comment: str | None = None) -> None:
            self.calls.append((item_key, status, comment))

    class FakeDeployTrigger:
        def __init__(self, config, *, ticket=None, http_client=None, sleep=None, max_attempts=4):
            del http_client, sleep, max_attempts
            captured["config"] = config
            captured["ticket"] = ticket

        def run(
            self,
            *,
            item_key: str,
            run_id: str,
            pr_url: str | None = None,
            deploy_url_override: str | None = None,
        ) -> StepReport:
            del deploy_url_override
            captured["run"] = (item_key, run_id, pr_url)
            if captured["ticket"] is not None:
                captured["ticket"].update_status(item_key, "Released", "Deploy comment")
            return StepReport(step=11, name="deploy-trigger", status="ok", message="deploy ok")

    monkeypatch.setattr("sendsprint.flow.sprint_flow.DeployTrigger", FakeDeployTrigger)
    operator = OperatorWithUpdater(transport="api")
    flow = SprintFlow(
        operator=operator,
        deploy=DeployWorkflowConfig(
            enabled=True,
            url="https://deploy.example.com/hook",
            final_status="Released",
        ),
        autonomy_policy=AutonomyPolicy(level="deploy-callback"),
    )
    pr_report = StepReport(
        step=9,
        name="create-pr",
        status="ok",
        pr=PrInfo(
            provider="github",
            repo=str(tmp_path),
            title="PR",
            source_branch="feature/x",
            target_branch="main",
            url="https://github.com/example/pr/1",
        ),
    )
    report = RunReport(workspace="ws")

    step = flow._step11_deploy(_item("PROJ-42", "Deploy"), pr_report, report, "run-42")

    assert step is not None
    assert step.status == "ok"
    assert captured["run"] == ("PROJ-42", "run-42", "https://github.com/example/pr/1")
    assert captured["config"].final_status == "Released"
    assert operator.calls == [("PROJ-42", "Released", "Deploy comment")]
