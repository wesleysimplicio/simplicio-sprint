"""Tests for SprintFlow helpers (branch naming per task)."""

from __future__ import annotations

import subprocess
from collections import defaultdict
from typing import Any
from unittest.mock import MagicMock

from sendsprint.flow.sprint_flow import SprintFlow
from sendsprint.models import ArchitectureReport
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
from sendsprint.yool.receipts import ReceiptStore


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


def test_branch_for_task_uses_profile_template_when_no_workspace() -> None:
    flow = SprintFlow(
        operator=MagicMock(),
        workspace=None,
        branch_name_template="release/{number}-{title}",
        default_base_branch="develop",
    )
    branch = flow._branch_for_task(_item("PROJ-42", "Add Login Flow"), _fp())
    assert branch == "release/42-add-login-flow"
    assert flow.default_base_branch == "develop"


def test_workspace_template_wins_over_profile_template() -> None:
    ws = WorkspaceConfig(root_path="/tmp", branch_name_template="bugfix/{key}")
    flow = SprintFlow(
        operator=MagicMock(),
        workspace=ws,
        branch_name_template="release/{number}-{title}",
    )
    branch = flow._branch_for_task(_item("PROJ-42", "Add Login Flow"), _fp())
    assert branch == "bugfix/proj-42"


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


def test_bootstrap_reuses_receipts_across_consecutive_runs(tmp_path, monkeypatch) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    counters: dict[str, int] = defaultdict(int)

    def fake_import_specs(self, sprint: Sprint, repo_path: str | None, report: RunReport) -> None:
        del self, sprint, repo_path
        report.steps.append(StepReport(step=1, name="import-specs", status="ok"))

    def fake_arch(self, repo, fp, report: RunReport):
        del self, fp
        report.steps.append(StepReport(step=2, name="architecture", repo=str(repo), status="ok"))
        return ArchitectureReport(
            repo_path=str(repo),
            has_readme=True,
            has_agentic_starter=True,
            score=1.0,
        ), None

    def fake_try_worktree(self, repo, branch):
        del self, repo, branch
        return None

    def fake_step3(self, dev, report: RunReport, repo_cfg):
        del self, dev, repo_cfg
        counters["dev"] += 1
        report.steps.append(StepReport(step=3, name="install", status="ok"))
        report.steps.append(StepReport(step=3, name="build", status="ok"))

    def fake_codegen(self, work_dir, item, report: RunReport):
        del self, work_dir, item
        step = StepReport(step=35, name="codegen", status="ok")
        report.steps.append(step)
        return step

    def fake_lint(self, linter, report: RunReport):
        del self, linter
        counters["lint"] += 1
        step = StepReport(step=4, name="lint", status="ok")
        report.steps.append(step)
        return step

    def fake_tests(self, runner, report: RunReport):
        del self, runner
        counters["test"] += 1
        steps = [
            StepReport(step=5, name="tests-unit", status="ok"),
            StepReport(step=5, name="tests-e2e", status="ok"),
        ]
        report.steps.extend(steps)
        return steps

    def fake_security(self, sec, report: RunReport):
        del self, sec
        counters["security"] += 1
        step = StepReport(step=6, name="security", status="ok")
        report.steps.append(step)
        return step

    def fake_fix_loop(
        self,
        dev,
        linter,
        runner,
        sec,
        lint_report,
        test_reports,
        sec_report,
        report,
    ):
        del self, dev, linter, runner, sec, lint_report, test_reports, sec_report
        report.steps.append(StepReport(step=7, name="fix-loop", status="ok"))

    def fake_commit(self, work_dir, task_sprint, report: RunReport, item):
        del self, work_dir, task_sprint, item
        report.steps.append(StepReport(step=8, name="commit", status="ok"))

    def fake_push(self, work_dir, branch):
        del self, work_dir, branch

    def fake_pr(
        self,
        work_dir,
        branch,
        target,
        provider,
        reviewers,
        required_reviewers,
        sprint,
        report,
        item,
    ):
        del self, work_dir, branch, target, provider, reviewers, required_reviewers, sprint, item
        counters["pr"] += 1
        step = StepReport(
            step=9,
            name="create-pr",
            status="ok",
            pr=PrInfo(
                provider="github",
                repo=str(tmp_path),
                title="PR",
                source_branch="feature/42",
                target_branch="main",
                url="https://example.test/pr/1",
            ),
        )
        report.steps.append(step)
        return step

    def fake_review(self, work_dir, branch, target, rpath, pr_report, report: RunReport):
        del self, work_dir, branch, target, rpath, pr_report
        report.steps.append(StepReport(step=10, name="review", status="ok"))
        report.steps.append(StepReport(step=10, name="delivered", status="ok"))

    def fake_deploy(self, item, pr_report, report: RunReport, run_id):
        del self, item, pr_report, run_id
        step = StepReport(step=11, name="deploy-trigger", status="ok")
        report.steps.append(step)
        return step

    monkeypatch.setattr(SprintFlow, "_step1_5_import_specs", fake_import_specs)
    monkeypatch.setattr(SprintFlow, "_step2_architecture", fake_arch)
    monkeypatch.setattr(SprintFlow, "_try_worktree", fake_try_worktree)
    monkeypatch.setattr(SprintFlow, "_step3_dev", fake_step3)
    monkeypatch.setattr(SprintFlow, "_step3_5_codegen", fake_codegen)
    monkeypatch.setattr(SprintFlow, "_step4_lint", fake_lint)
    monkeypatch.setattr(SprintFlow, "_step5_tests", fake_tests)
    monkeypatch.setattr(SprintFlow, "_step6_security", fake_security)
    monkeypatch.setattr(SprintFlow, "_step7_fix_loop", fake_fix_loop)
    monkeypatch.setattr(SprintFlow, "_step8_commit", fake_commit)
    monkeypatch.setattr(SprintFlow, "_push_branch", fake_push)
    monkeypatch.setattr(SprintFlow, "_step9_create_pr", fake_pr)
    monkeypatch.setattr(SprintFlow, "_step10_review_and_deliver", fake_review)
    monkeypatch.setattr(SprintFlow, "_step11_deploy", fake_deploy)

    flow = SprintFlow(
        operator=FakeOperator(transport="api"),
        autonomy_policy=AutonomyPolicy(level="deploy-callback"),
    )

    first = flow.bootstrap(repo_path=str(tmp_path), sprint_id=42, resume=False, run_id="run-a")
    receipt_store = ReceiptStore(tmp_path / ".sendsprint" / "receipts")
    receipt_count = len(list(receipt_store.all()))
    assert {k: counters[k] for k in ("dev", "lint", "test", "security", "pr")} == {
        "dev": 1,
        "lint": 1,
        "test": 1,
        "security": 1,
        "pr": 1,
    }

    second = flow.bootstrap(repo_path=str(tmp_path), sprint_id=42, resume=False, run_id="run-b")
    receipt_count_after = len(list(receipt_store.all()))

    assert receipt_count_after == receipt_count
    assert {k: counters[k] for k in ("dev", "lint", "test", "security", "pr")} == {
        "dev": 1,
        "lint": 1,
        "test": 1,
        "security": 1,
        "pr": 1,
    }
    assert first.run_report is not None
    assert second.run_report is not None
    assert first.run_report.summary == second.run_report.summary
    assert any(step.name == "create-pr" for step in second.run_report.steps)
