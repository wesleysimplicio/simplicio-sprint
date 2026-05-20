"""SprintFlow v2.1: 10-step orchestration across a multi-repo workspace.

Improvements over v2.0:
- Step 3.5: Lint step between build and tests
- Step 6: Fix loop reports what failed (tests vs security vs lint)
- Step 7: Commits changes before creating PR
- Empty-repos guard with explicit report entry
- to_json() for structured output
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, Field

from sendsprint.agents.code_generator import CodegenBudget, CodeGenerator
from sendsprint.agents.deploy_trigger import DeployConfig, DeployTrigger
from sendsprint.agents.dev import DevAgent
from sendsprint.agents.lint_runner import LintRunner
from sendsprint.agents.pr_body_builder import PrBodyBuilder
from sendsprint.agents.pr_creator import PrCreator
from sendsprint.agents.pr_reviewer import PrReviewer
from sendsprint.agents.security_reviewer import SecurityReviewer
from sendsprint.agents.sprint_importer import SprintImporter, _slugify, _sprint_dir_name
from sendsprint.agents.story_task_planner import delivery_items, item_matches_repo, plan_story_tasks
from sendsprint.agents.test_runner import TestRunner
from sendsprint.agents.worktree import WorktreeError, WorktreeManager
from sendsprint.architecture import ArchitectureMapper, build_architecture
from sendsprint.llm import LlmClient
from sendsprint.models import ArchitectureReport, Sprint
from sendsprint.models.reports import PrInfo, RunReport, StepReport, StepStatus, TestEvidence
from sendsprint.models.sprint import SprintItem
from sendsprint.models.workspace import (
    CodeGenerationConfig,
    DeployWorkflowConfig,
    RepoConfig,
    ScopeConfig,
    WorkspaceConfig,
)
from sendsprint.operators.base import BaseOperator
from sendsprint.planning import DeliveryPlan, build_delivery_plan
from sendsprint.policy import AutonomyPolicy
from sendsprint.post_validation import validate_pr_step, validate_sprint_links
from sendsprint.run_state import RunState, RunStateStore, delivery_key, stable_run_id
from sendsprint.scope import apply_scope
from sendsprint.tech import TechFingerprint, detect_tech
from sendsprint.workspace import resolve_repo_path
from sendsprint.yool.bus import TupleBus
from sendsprint.yool.dispatcher import Dispatcher
from sendsprint.yool.receipts import ReceiptStore
from sendsprint.yool.runtime import run_worker_pool_async
from sendsprint.yool.tuples import Tuple, TupleLog, emit_tuple, make_run_id
from sendsprint.yool.workers import FollowUp, Worker, WorkerPool

logger = logging.getLogger(__name__)

MAX_FIX_LOOPS = 3
DEFAULT_BRANCH_NAME_TEMPLATE = "feature/{number}-{title}"


def _task_number(item: SprintItem) -> str:
    """Return the numeric task id used by the default branch convention."""
    for candidate in (item.key, item.id):
        if not candidate:
            continue
        matches = re.findall(r"\d+", candidate)
        if matches:
            return _slugify(matches[-1], 40)

    return _slugify(item.key or item.id or "task", 40)


def _clean_branch_template(branch: str) -> str:
    """Drop empty template fragments without changing intentional path segments."""
    parts = []
    for part in branch.split("/"):
        cleaned = re.sub(r"-{2,}", "-", part).strip("-")
        if cleaned:
            parts.append(cleaned)
    return "/".join(parts) or DEFAULT_BRANCH_NAME_TEMPLATE.replace("{number}", "task").replace(
        "-{title}", ""
    )


class SprintFlowResult(BaseModel):
    sprint: Sprint
    architecture: ArchitectureReport | None = None
    repo_path: str | None = None
    notes: list[str] = Field(default_factory=list)
    run_report: RunReport | None = None
    delivery_plan: DeliveryPlan | None = None

    def to_json(self, **kwargs: Any) -> str:
        return self.model_dump_json(indent=2, **kwargs)


class SprintFlow:
    """Full 10-step flow:

    1. Read sprint (Jira/ADO)
    2. Architecture mapping (inspect + build if missing)
    3. Dev: install + build per repo (parallel worktrees)
    4. Lint: static analysis per tech stack
    5. Tests: unit + Playwright E2E with screenshot evidence
    6. Security review (flag only)
    7. Fix loop: if lint/tests/security fail -> re-build -> re-run (max 3)
    8. Commit changes on worktree branch
    9. Create PR (GitHub or ADO)
    10. PR review (diff analysis) + Delivered
    """

    def __init__(
        self,
        operator: BaseOperator,
        *,
        workspace: WorkspaceConfig | None = None,
        scope: ScopeConfig | None = None,
        code_generation: CodeGenerationConfig | None = None,
        deploy: DeployWorkflowConfig | None = None,
        autonomy_policy: AutonomyPolicy | None = None,
    ) -> None:
        self.operator = operator
        self.workspace = workspace
        self.scope = scope or ScopeConfig()
        self.code_generation = code_generation
        self.deploy = deploy
        self.autonomy_policy = autonomy_policy or AutonomyPolicy(level="pr")
        self.mapper = ArchitectureMapper()

    def run(
        self,
        sprint_id: str | int | None = None,
        iteration_path: str | None = None,
        repo_path: str | None = None,
        dry_run: bool = False,
        resume: bool = False,
        run_id: str | None = None,
        no_cache: bool = False,
        **kwargs: Any,
    ) -> SprintFlowResult:
        return self.bootstrap(
            sprint_id=sprint_id,
            iteration_path=iteration_path,
            repo_path=repo_path,
            dry_run=dry_run,
            resume=resume,
            run_id=run_id,
            no_cache=no_cache,
            **kwargs,
        )

    def bootstrap(
        self,
        sprint_id: str | int | None = None,
        iteration_path: str | None = None,
        repo_path: str | None = None,
        dry_run: bool = False,
        resume: bool = False,
        run_id: str | None = None,
        no_cache: bool = False,
        **kwargs: Any,
    ) -> SprintFlowResult:
        report = RunReport(
            workspace=self.workspace.name if self.workspace else "single-repo",
            scope_mode=self.scope.mode,
            autonomy_level=self.autonomy_policy.level,
        )

        # --- Step 1: Read sprint ---
        sprint = self._step1_read_sprint(sprint_id, iteration_path, report, **kwargs)

        # --- Scope filter ---
        sprint = apply_scope(sprint, self.scope)
        if self.scope.mode == "mine":
            report.user = self.scope.user_email or self.scope.user_display_name

        # --- Step 1.25: Split User Stories without tasks into front/back tasks ---
        sprint, planning_report = plan_story_tasks(sprint, self.workspace)
        report.steps.append(planning_report)

        link_validation = validate_sprint_links(sprint)
        report.steps.append(link_validation)

        repos = self._resolve_repos(repo_path)
        default_target = self.workspace.default_base_branch if self.workspace else "main"
        plan_policy = AutonomyPolicy(level="plan") if dry_run else self.autonomy_policy
        plan = build_delivery_plan(
            sprint,
            repos,
            branch_for_task=self._branch_for_task,
            detect_fingerprint=detect_tech,
            default_target_branch=default_target,
            autonomy_policy=plan_policy,
            llm={
                "enabled": self._codegen_config().enabled,
                "provider": self._codegen_config().provider,
                "model": self._codegen_config().model,
                "max_usd": self._codegen_config().max_usd,
                "max_tokens": self._codegen_config().max_tokens,
            },
            deploy_callback={
                "enabled": self._deploy_config().enabled,
                "provider": self._deploy_config().provider,
                "url": self._deploy_config().url,
                "final_status": self._deploy_config().final_status,
            },
            workspace=self.workspace,
        )

        if dry_run:
            step = StepReport(step=0, name="dry-run-plan", status="ok")
            step.message = plan.summary()
            report.steps.append(step)
            report.finished_at = datetime.now(tz=UTC)
            report.failed = False
            report.summary = plan.summary()
            return SprintFlowResult(
                sprint=sprint,
                repo_path=repo_path,
                notes=plan.warnings,
                run_report=report,
                delivery_plan=plan,
            )

        # --- Step 1.5: Import sprint items as agentic-starter task specs ---
        self.autonomy_policy.require("write-files")
        self._step1_5_import_specs(sprint, repo_path, report)

        notes: list[str] = []
        first_arch: ArchitectureReport | None = None

        state_store: RunStateStore | None = None
        state: RunState | None = None
        resolved_run_id = run_id
        if resolved_run_id is None and (resume or self._deploy_config().enabled):
            identifier = sprint_id if sprint_id is not None else iteration_path
            state_scope = repo_path or (self.workspace.name if self.workspace else "")
            resolved_run_id = stable_run_id(
                self.operator.source,
                identifier,
                self.scope.mode,
                ",".join(self.scope.task_keys or []),
                state_scope,
            )
        if resume or run_id:
            state_root = self._state_root(repo_path)
            state_store = RunStateStore(state_root)
            state = state_store.load_or_create(
                resolved_run_id or "run",
                source=self.operator.source,
                sprint_id=str(sprint.id),
                autonomy_level=self.autonomy_policy.level,
            )
            state_store.save(state)
            resolved_run_id = state.run_id

        if not repos:
            skip = StepReport(step=2, name="no-repos", status="skipped")
            skip.message = "no repos resolved - steps 2-10 skipped"
            report.steps.append(skip)

        items_to_deliver = delivery_items(sprint)

        if not items_to_deliver and repos:
            skip = StepReport(step=2, name="no-tasks", status="skipped")
            skip.message = "sprint has 0 items after scope/status filter - steps 2-10 skipped"
            report.steps.append(skip)

        runtime_run_id = resolved_run_id or make_run_id("tuple")
        tuple_root = self._tuple_root(repo_path)
        tuple_log = TupleLog(runtime_run_id, tuple_root)
        tuple_bus = TupleBus(maxsize=max(len(items_to_deliver) * max(len(repos), 1), 1) + 1)
        delivery_tuples: list[Tuple] = []
        tuple_contexts: dict[str, dict[str, Any]] = {}

        for item in items_to_deliver:
            for repo_cfg, rpath in repos:
                if not item_matches_repo(item, repo_cfg.role if repo_cfg else None):
                    continue
                fp = detect_tech(rpath)
                branch_name = self._branch_for_task(item, fp, repo_cfg)
                dkey = delivery_key(item.key or item.id, repo_cfg.name if repo_cfg else rpath.name)
                if state:
                    state.mark_planned(dkey)
                    assert state_store is not None
                    state_store.save(state)
                    if state.is_completed(dkey):
                        skip = StepReport(step=0, name="resume-skip", repo=str(rpath))
                        skip.status = "skipped"
                        skip.message = f"{dkey} already completed in run {state.run_id}"
                        report.steps.append(skip)
                        continue
                arch_report, build_result = self._step2_architecture(rpath, fp, report)
                if first_arch is None:
                    first_arch = arch_report
                if build_result and build_result.created_files:
                    notes.append(
                        f"[{rpath.name}] architecture docs created: "
                        + ", ".join(Path(f).name for f in build_result.created_files)
                    )
                payload = self._make_delivery_payload(
                    item=item,
                    repo_cfg=repo_cfg,
                    repo_path=rpath,
                    branch_name=branch_name,
                    delivery_key_value=dkey,
                    target_branch=(repo_cfg.pr_target_branch if repo_cfg else None)
                    or default_target,
                    provider=self.workspace.pr_provider if self.workspace else "github",
                    reviewers=(list(self.workspace.pr_reviewers) if self.workspace else [])
                    + (list(repo_cfg.pr_reviewers) if repo_cfg else []),
                    required_reviewers=(
                        list(self.workspace.required_pr_reviewers) if self.workspace else []
                    )
                    + (list(repo_cfg.required_pr_reviewers) if repo_cfg else []),
                    no_cache=no_cache,
                    run_id=resolved_run_id,
                    fp=fp,
                )
                existing = self._pending_delivery_tuple(tuple_log, dkey)
                if existing is not None:
                    delivery_tuples.append(existing)
                    tuple_contexts[existing.id] = {"delivery_key": dkey}
                    continue
                delivery_tuple = emit_tuple(
                    yool_id="sendsprint.flow.dev",
                    lane="dev",
                    payload=payload,
                    run_id=runtime_run_id,
                    meta={"delivery_key": dkey, "repo_path": str(rpath)},
                )
                tuple_log.append(delivery_tuple)
                delivery_tuples.append(delivery_tuple)
                tuple_contexts[delivery_tuple.id] = {"delivery_key": dkey}

        runtime_step = StepReport(
            step=0,
            name="tuple-runtime-bootstrap",
            status="ok" if delivery_tuples else "skipped",
        )
        runtime_step.message = (
            f"bootstrapped tuple/bus runtime run_id={runtime_run_id} "
            f"with {len(delivery_tuples)} worker root tuple(s)"
        )
        report.steps.append(runtime_step)

        if delivery_tuples:
            first_arch = asyncio.run(
                self._run_delivery_runtime(
                    bus=tuple_bus,
                    log=tuple_log,
                    delivery_tuples=delivery_tuples,
                    tuple_contexts=tuple_contexts,
                    sprint=sprint,
                    report=report,
                    notes=notes,
                    resolved_run_id=resolved_run_id,
                    state=state,
                    state_store=state_store,
                    no_cache=no_cache,
                )
            )

        report.finished_at = datetime.now(tz=UTC)
        report.failed = any(s.status == "failed" for s in report.steps)
        report.summary = self._build_summary(report)

        return SprintFlowResult(
            sprint=sprint,
            architecture=first_arch,
            repo_path=repo_path,
            notes=notes,
            run_report=report,
            delivery_plan=plan,
        )

    # ── Step implementations ──────────────────────────────────────────

    def _make_delivery_payload(
        self,
        *,
        item: SprintItem,
        repo_cfg: RepoConfig | None,
        repo_path: Path,
        branch_name: str,
        delivery_key_value: str,
        target_branch: str,
        provider: str,
        reviewers: list[str],
        required_reviewers: list[str],
        no_cache: bool,
        run_id: str | None,
        fp: TechFingerprint,
    ) -> dict[str, Any]:
        del run_id
        return {
            "item": item.model_dump(mode="json"),
            "repo_cfg": repo_cfg.model_dump(mode="json") if repo_cfg else None,
            "repo_path": str(repo_path),
            "fp": fp.model_dump(mode="json"),
            "branch_name": branch_name,
            "delivery_key": delivery_key_value,
            "target_branch": target_branch,
            "provider": provider,
            "reviewers": reviewers,
            "required_reviewers": required_reviewers,
            "workspace_name": self.workspace.name if self.workspace else "single-repo",
            "scope_mode": self.scope.mode,
            "sprint_source": self.operator.source,
            "no_cache": no_cache,
        }

    def _pending_delivery_tuple(self, log: TupleLog, delivery_key_value: str) -> Tuple | None:
        for tup in log.pending():
            if tup.meta.get("delivery_key") == delivery_key_value:
                return tup
        return None

    async def _run_delivery_runtime(
        self,
        *,
        bus: TupleBus,
        log: TupleLog,
        delivery_tuples: list[Tuple],
        tuple_contexts: dict[str, dict[str, Any]],
        sprint: Sprint,
        report: RunReport,
        notes: list[str],
        resolved_run_id: str | None,
        state: RunState | None,
        state_store: RunStateStore | None,
        no_cache: bool,
    ) -> ArchitectureReport | None:
        del tuple_contexts, sprint, resolved_run_id, no_cache
        receipt_root = log.root.parent / "receipts"
        store = ReceiptStore(receipt_root)
        catalog = self._runtime_catalog()
        dispatcher = Dispatcher(store=store, executor=self._execute_runtime_yool)
        pool = WorkerPool()
        for lane in ("dev", "lint", "test", "security", "pr"):
            pool.add(
                Worker(
                    lane=lane,
                    bus=bus,
                    log=log,
                    catalog=catalog,
                    dispatcher=dispatcher,
                    run_id=log.run_id,
                    follow_up=self._runtime_follow_up,
                )
            )

        inspected = await run_worker_pool_async(
            pool,
            bus=bus,
            run_id=log.run_id,
            tuple_root=log.root,
            receipt_root=receipt_root,
            seed=delivery_tuples,
        )
        by_receipt = {receipt["id"]: receipt for receipt in inspected["receipts"]}
        for tup in inspected["tuples"]:
            receipt_id = tup.get("receipt_id")
            if not receipt_id:
                continue
            receipt = by_receipt.get(receipt_id)
            if receipt is None:
                continue
            output = receipt.get("output_payload")
            if isinstance(output, dict):
                self._apply_runtime_output(
                    report,
                    output,
                    notes=notes,
                    state=state,
                    state_store=state_store,
                )
        total_cost = inspected["cost"]["total"]
        if total_cost["usd"] or total_cost["wall_ms"]:
            cost_step = StepReport(step=0, name="tuple-runtime-cost", status="ok")
            cost_step.message = json.dumps(total_cost, sort_keys=True)
            report.steps.append(cost_step)
        return None

    def _runtime_catalog(self) -> dict[str, Any]:
        entries = {
            "sendsprint.flow.dev": {"authority": "sendsprint", "lane": "dev"},
            "sendsprint.flow.lint": {"authority": "sendsprint", "lane": "lint"},
            "sendsprint.flow.test": {"authority": "sendsprint", "lane": "test"},
            "sendsprint.flow.security": {"authority": "sendsprint", "lane": "security"},
            "sendsprint.flow.pr": {"authority": "sendsprint", "lane": "pr"},
        }
        return {
            "flat": {
                key: {
                    "hash": "",
                    "hash_hex": "",
                    "slots": [],
                    "tuple": {
                        **value,
                        "description": key,
                        "guardrails": {},
                    },
                }
                for key, value in entries.items()
            }
        }

    def _runtime_follow_up(self, tup: Tuple, output: Any) -> list[FollowUp]:
        if not isinstance(output, dict):
            return []
        payload = dict(output.get("payload") or tup.payload)
        next_map = {
            "sendsprint.flow.dev": ("sendsprint.flow.lint", "lint"),
            "sendsprint.flow.lint": ("sendsprint.flow.test", "test"),
            "sendsprint.flow.test": ("sendsprint.flow.security", "security"),
            "sendsprint.flow.security": ("sendsprint.flow.pr", "pr"),
        }
        target = next_map.get(tup.yool_id)
        if target is None:
            return []
        return [(target[0], target[1], payload)]

    def _execute_runtime_yool(self, entry: Any, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise TypeError("runtime payload must be a mapping")
        handlers = {
            "sendsprint.flow.dev": self._execute_dev_yool,
            "sendsprint.flow.lint": self._execute_lint_yool,
            "sendsprint.flow.test": self._execute_test_yool,
            "sendsprint.flow.security": self._execute_security_yool,
            "sendsprint.flow.pr": self._execute_pr_yool,
        }
        handler = handlers.get(entry.yool_id)
        if handler is None:
            raise ValueError(f"unknown runtime yool: {entry.yool_id}")
        return handler(payload)

    def _execute_dev_yool(self, payload: dict[str, Any]) -> dict[str, Any]:
        item, repo_cfg, repo_path, work_dir, fp = self._runtime_context(payload)
        local = self._runtime_report_template(payload)
        wt_path = work_dir if work_dir != repo_path else None
        local.steps.append(
            self._worktree_step(repo_path, work_dir, payload["branch_name"], wt_path)
        )
        dev = DevAgent(work_dir, fp)
        self._step3_dev(dev, local, repo_cfg)
        self._step3_5_codegen(work_dir, item, local)
        next_payload = {**payload, "work_dir": str(work_dir)}
        return self._runtime_output(next_payload, local)

    def _execute_lint_yool(self, payload: dict[str, Any]) -> dict[str, Any]:
        _, repo_cfg, _, work_dir, fp = self._runtime_context(payload)
        local = self._runtime_report_template(payload)
        lint_cmd = repo_cfg.lint_command if repo_cfg else None
        linter = LintRunner(work_dir, fp, custom_command=lint_cmd)
        lint_report = self._step4_lint(linter, local)
        next_payload = {**payload, "lint_report": lint_report.model_dump(mode="json")}
        return self._runtime_output(next_payload, local)

    def _execute_test_yool(self, payload: dict[str, Any]) -> dict[str, Any]:
        _, repo_cfg, _, work_dir, fp = self._runtime_context(payload)
        local = self._runtime_report_template(payload)
        runner = TestRunner(
            work_dir,
            fp,
            custom_unit_cmd=repo_cfg.test_command if repo_cfg else None,
            custom_e2e_cmd=repo_cfg.e2e_command if repo_cfg else None,
        )
        test_reports = self._step5_tests(runner, local)
        next_payload = {
            **payload,
            "test_reports": [step.model_dump(mode="json") for step in test_reports],
        }
        return self._runtime_output(next_payload, local)

    def _execute_security_yool(self, payload: dict[str, Any]) -> dict[str, Any]:
        _, repo_cfg, _, work_dir, fp = self._runtime_context(payload)
        local = self._runtime_report_template(payload)
        sec = SecurityReviewer(work_dir, fp)
        sec_report = self._step6_security(sec, local)
        dev = DevAgent(work_dir, fp)
        lint_cmd = repo_cfg.lint_command if repo_cfg else None
        linter = LintRunner(work_dir, fp, custom_command=lint_cmd)
        runner = TestRunner(
            work_dir,
            fp,
            custom_unit_cmd=repo_cfg.test_command if repo_cfg else None,
            custom_e2e_cmd=repo_cfg.e2e_command if repo_cfg else None,
        )
        lint_report = StepReport.model_validate(
            payload.get("lint_report") or sec_report.model_dump()
        )
        test_reports = [
            StepReport.model_validate(raw) for raw in (payload.get("test_reports") or [])
        ]
        self._step7_fix_loop(
            dev,
            linter,
            runner,
            sec,
            lint_report,
            test_reports,
            sec_report,
            local,
        )
        next_payload = {**payload, "security_report": sec_report.model_dump(mode="json")}
        return self._runtime_output(next_payload, local)

    def _execute_pr_yool(self, payload: dict[str, Any]) -> dict[str, Any]:
        item, _, repo_path, work_dir, _ = self._runtime_context(payload)
        local = self._runtime_report_template(payload)
        task_sprint = Sprint(
            id=str(payload.get("run_id") or item.id),
            name=item.title,
            source=payload.get("sprint_source", self.operator.source),
            items=[item],
        )
        self.autonomy_policy.require("commit")
        self._step8_commit(work_dir, task_sprint, local, item=item)
        self.autonomy_policy.require("push")
        self._push_branch(work_dir, payload["branch_name"])
        self.autonomy_policy.require("create-pr")
        pr_report = self._step9_create_pr(
            work_dir,
            payload["branch_name"],
            payload["target_branch"],
            str(payload.get("provider") or "github"),
            list(payload.get("reviewers") or []),
            list(payload.get("required_reviewers") or []),
            task_sprint,
            local,
            item=item,
        )
        pr_validation = validate_pr_step(pr_report)
        local.steps.append(pr_validation)
        self._step10_review_and_deliver(
            work_dir,
            payload["branch_name"],
            payload["target_branch"],
            repo_path,
            pr_report,
            local,
        )
        self._step11_deploy(item, pr_report, local, payload.get("run_id"))
        state_status = (
            "completed" if pr_report.status == "ok" and pr_validation.status == "ok" else "failed"
        )
        return self._runtime_output(
            payload,
            local,
            state_update={
                "delivery_key": payload["delivery_key"],
                "status": state_status,
                "message": pr_report.message or "PR validation failed",
            },
        )

    def _runtime_context(
        self, payload: dict[str, Any]
    ) -> tuple[SprintItem, RepoConfig | None, Path, Path, TechFingerprint]:
        item = SprintItem.model_validate(payload["item"])
        repo_cfg = (
            RepoConfig.model_validate(payload["repo_cfg"]) if payload.get("repo_cfg") else None
        )
        repo_path = Path(str(payload["repo_path"]))
        branch_name = str(payload["branch_name"])
        work_dir = self._runtime_work_dir(repo_path, branch_name)
        fp = (
            TechFingerprint.model_validate(payload["fp"])
            if payload.get("fp") is not None
            else detect_tech(repo_path)
        )
        return item, repo_cfg, repo_path, work_dir, fp

    def _runtime_work_dir(self, repo_path: Path, branch_name: str) -> Path:
        try:
            worktree_dir = WorktreeManager(repo_path).worktree_dir(branch_name)
        except WorktreeError:
            return repo_path
        return worktree_dir if worktree_dir.exists() else repo_path

    def _runtime_report_template(self, payload: dict[str, Any]) -> RunReport:
        raw_scope = payload.get("scope_mode") or self.scope.mode
        scope_mode = cast(Literal["all", "mine"], "mine" if raw_scope == "mine" else "all")
        return RunReport(
            workspace=str(payload.get("workspace_name") or "single-repo"),
            scope_mode=scope_mode,
            autonomy_level=self.autonomy_policy.level,
        )

    def _runtime_output(
        self,
        payload: dict[str, Any],
        report: RunReport,
        *,
        state_update: dict[str, Any] | None = None,
        notes: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "payload": payload,
            "steps": [step.model_dump(mode="json") for step in report.steps],
            "prs": [pr.model_dump(mode="json") for pr in report.prs],
            "notes": notes or [],
            "state_update": state_update,
        }

    def _apply_runtime_output(
        self,
        report: RunReport,
        output: dict[str, Any],
        *,
        notes: list[str],
        state: RunState | None,
        state_store: RunStateStore | None,
    ) -> None:
        for raw in output.get("steps") or []:
            report.steps.append(StepReport.model_validate(raw))
        for raw in output.get("prs") or []:
            report.prs.append(PrInfo.model_validate(raw))
        notes.extend(str(note) for note in (output.get("notes") or []))
        if state and state_store and isinstance(output.get("state_update"), dict):
            update = output["state_update"]
            if update.get("status") == "completed":
                state.mark_completed(str(update["delivery_key"]))
            else:
                state.mark_failed(
                    str(update["delivery_key"]),
                    str(update.get("message") or "runtime failure"),
                )
            state_store.save(state)

    def _tuple_root(self, repo_path: str | None) -> Path:
        return self._state_root(repo_path) / ".sendsprint" / "tuples"

    def _receipt_root(self, repo_path: str | None) -> Path:
        return self._state_root(repo_path) / ".sendsprint" / "receipts"

    def _step1_5_import_specs(
        self,
        sprint: Sprint,
        repo_path: str | None,
        report: RunReport,
    ) -> None:
        """Materialize sprint items as `.specs/sprints/sprint-<id>/<key>.task.md`."""
        root: Path
        if self.workspace and self.workspace.root_path:
            root = Path(self.workspace.root_path)
        elif repo_path:
            root = Path(repo_path).resolve()
        else:
            root = Path.cwd()
        importer = SprintImporter(root)
        step = importer.import_sprint(sprint)
        report.steps.append(step)

    def _step1_read_sprint(
        self,
        sprint_id: str | int | None,
        iteration_path: str | None,
        report: RunReport,
        **kwargs: Any,
    ) -> Sprint:
        step = StepReport(step=1, name="read-sprint", status="running")
        step.started_at = datetime.now(tz=UTC)
        identifier = sprint_id if sprint_id is not None else iteration_path
        if identifier is None:
            raise ValueError("provide sprint_id (Jira) or iteration_path (Azure DevOps)")
        read_kw = (
            {"sprint_id": identifier} if sprint_id is not None else {"iteration_path": identifier}
        )
        sprint = self.operator.read_sprint(**read_kw, **kwargs)
        report.sprint_name = sprint.name
        report.sprint_id = sprint.id
        step.status = "ok"
        step.message = f"{len(sprint.items)} items read via {self.operator.source}"
        step.finished_at = datetime.now(tz=UTC)
        report.steps.append(step)
        return sprint

    def _step2_architecture(
        self, repo: Path, fp: TechFingerprint, report: RunReport
    ) -> tuple[ArchitectureReport, Any]:
        step = StepReport(step=2, name="architecture", repo=str(repo), status="running")
        step.started_at = datetime.now(tz=UTC)
        arch = self.mapper.inspect(repo)
        build_result = None
        if not arch.is_mapped:
            build_result = build_architecture(repo, fingerprint=fp)
            arch = self.mapper.inspect(repo)
            step.message = (
                f"built {len(build_result.created_files)} doc(s), "
                f"score {arch.score:.2f}, substrate {arch.mapping_substrate}"
            )
        else:
            step.message = (
                f"already mapped, score {arch.score:.2f}, substrate {arch.mapping_substrate}"
            )
        step.status = "ok" if arch.is_mapped else "failed"
        step.finished_at = datetime.now(tz=UTC)
        report.steps.append(step)
        return arch, build_result

    def _step3_dev(self, dev: DevAgent, report: RunReport, repo_cfg: RepoConfig | None) -> None:
        install_report = dev.install()
        report.steps.append(install_report)
        custom_build = repo_cfg.build_command if repo_cfg else None
        build_report = dev.build(custom_command=custom_build)
        report.steps.append(build_report)

    def _step3_5_codegen(
        self,
        work_dir: Path,
        item: SprintItem,
        report: RunReport,
    ) -> StepReport | None:
        config = self._codegen_config()
        if not config.enabled:
            return None
        self.autonomy_policy.require("llm-codegen")

        generator = CodeGenerator(
            work_dir,
            item_title=item.title,
            item_description=item.description or "",
            acceptance=self._acceptance_lines(item),
            client=LlmClient(provider=config.provider, model=config.model),
            budget=CodegenBudget(max_usd=config.max_usd, max_tokens=config.max_tokens),
        )
        codegen_report = generator.generate()
        if codegen_report.status == "ok":
            diff = self._codegen_diff(codegen_report)
            applied, message = self._apply_generated_diff(work_dir, diff)
            if applied:
                codegen_report.message = f"{codegen_report.message}; {message}"
            else:
                codegen_report.status = "failed"
                codegen_report.message = f"{codegen_report.message}; {message}"
        report.steps.append(codegen_report)
        return codegen_report

    def _step4_lint(self, linter: LintRunner, report: RunReport) -> StepReport:
        result = linter.run()
        report.steps.append(result)
        return result

    def _step5_tests(self, runner: TestRunner, report: RunReport) -> list[StepReport]:
        results = runner.run_all()
        for r in results:
            report.steps.append(r)
        return results

    def _step6_security(self, sec: SecurityReviewer, report: RunReport) -> StepReport:
        result = sec.scan()
        report.steps.append(result)
        return result

    def _step7_fix_loop(
        self,
        dev: DevAgent,
        linter: LintRunner,
        runner: TestRunner,
        sec: SecurityReviewer,
        lint_report: StepReport,
        test_reports: list[StepReport],
        sec_report: StepReport,
        report: RunReport,
    ) -> None:
        for attempt in range(1, MAX_FIX_LOOPS + 1):
            lint_fail = lint_report.status == "failed"
            test_fail = any(r.status == "failed" for r in test_reports)
            sec_fail = sec_report.status == "failed"
            if not lint_fail and not test_fail and not sec_fail:
                break

            failures = []
            if lint_fail:
                failures.append("lint")
            if test_fail:
                failures.append("tests")
            if sec_fail:
                failures.append("security")

            loop_step = StepReport(step=7, name=f"fix-loop-{attempt}", status="running")
            loop_step.started_at = datetime.now(tz=UTC)

            dev.build()
            lint_report = linter.run()
            report.steps.append(lint_report)
            test_reports = runner.run_all()
            for r in test_reports:
                report.steps.append(r)
            sec_report = sec.scan()
            report.steps.append(sec_report)

            still_failing = (
                lint_report.status == "failed"
                or any(r.status == "failed" for r in test_reports)
                or sec_report.status == "failed"
            )
            loop_step.status = "failed" if still_failing else "ok"
            loop_step.message = (
                f"attempt {attempt}/{MAX_FIX_LOOPS}, triggered by: {', '.join(failures)}"
            )
            loop_step.finished_at = datetime.now(tz=UTC)
            report.steps.append(loop_step)

    def _step8_commit(
        self,
        work_dir: Path,
        sprint: Sprint,
        report: RunReport,
        item: SprintItem | None = None,
    ) -> StepReport:
        step = StepReport(step=8, name="commit", repo=str(work_dir), status="running")
        step.started_at = datetime.now(tz=UTC)
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=30,
            )
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode == 0:
                step.status = "skipped"
                step.message = "no changes to commit"
            else:
                if item:
                    msg = f"feat({item.key}): {item.title} [SendSprint {sprint.name}]"
                else:
                    msg = f"[SendSprint] {sprint.name} — automated delivery"
                subprocess.run(
                    ["git", "commit", "-m", msg],
                    cwd=str(work_dir),
                    capture_output=True,
                    text=True,
                    timeout=30,
                    check=True,
                )
                step.status = "ok"
                step.message = "changes committed"
        except subprocess.CalledProcessError as exc:
            step.status = "failed"
            step.message = f"git commit failed: {exc.stderr[:500]}"
        except Exception as exc:
            step.status = "failed"
            step.message = str(exc)[:500]
        step.finished_at = datetime.now(tz=UTC)
        report.steps.append(step)
        return step

    def _step9_create_pr(
        self,
        work_dir: Path,
        branch: str,
        target: str,
        provider: str,
        reviewers: list[str],
        required_reviewers: list[str],
        sprint: Sprint,
        report: RunReport,
        item: SprintItem | None = None,
    ) -> StepReport:
        creator = PrCreator(
            work_dir,
            provider=provider,
            target_branch=target,
            reviewers=reviewers,
            required_reviewers=required_reviewers,
        )
        if item:
            title = f"[{item.key}] {item.title} — {work_dir.name}"
        else:
            title = f"[SendSprint] {sprint.name} — {work_dir.name}"
        sprint_slug = _sprint_dir_name(sprint)
        body = PrBodyBuilder(work_dir).build(
            sprint=sprint,
            repo_name=work_dir.name,
            steps=report.steps,
            sprint_slug=sprint_slug,
        )
        result = creator.create(source_branch=branch, title=title, body=body)
        report.steps.append(result)
        return result

    def _step10_review_and_deliver(
        self,
        work_dir: Path,
        branch: str,
        target: str,
        rpath: Path,
        pr_report: StepReport,
        report: RunReport,
    ) -> None:
        reviewer = PrReviewer(work_dir)
        review_result = reviewer.review(source_branch=branch, target_branch=target)
        report.steps.append(review_result)

        done = StepReport(step=10, name="delivered", repo=str(rpath), status="ok")
        done.message = f"PR for {rpath.name} delivered" + (
            f" -> {pr_report.pr.url}" if pr_report and pr_report.pr else ""
        )
        report.steps.append(done)
        if pr_report and pr_report.pr:
            report.prs.append(pr_report.pr)

    def _step11_deploy(
        self,
        item: SprintItem,
        pr_report: StepReport,
        report: RunReport,
        run_id: str | None,
    ) -> StepReport | None:
        config = self._deploy_config()
        if not config.enabled:
            return None
        self.autonomy_policy.require("deploy-callback")
        if pr_report.pr is None:
            skipped = StepReport(step=11, name="deploy-trigger", status="skipped")
            skipped.message = "deploy skipped because no PR was created"
            report.steps.append(skipped)
            return skipped
        deploy = DeployTrigger(
            DeployConfig(
                enabled=config.enabled,
                provider=config.provider,
                url=config.url,
                method=config.method,
                headers=config.headers,
                final_status=config.final_status,
            ),
            ticket=self._ticket_updater(),
        )
        deploy_report = deploy.run(
            item_key=item.key or item.id,
            run_id=run_id or f"manual-{item.key or item.id}",
            pr_url=pr_report.pr.url,
        )
        report.steps.append(deploy_report)
        return deploy_report

    def _push_branch(self, work_dir: Path, branch: str) -> None:
        try:
            subprocess.run(
                ["git", "push", "-u", "origin", branch, "--force-with-lease"],
                cwd=str(work_dir),
                capture_output=True,
                text=True,
                timeout=120,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired) as exc:
            logger.warning("git push failed for %s: %s", branch, exc)

    # ── Helpers ────────────────────────────────────────────────────────

    def _resolve_repos(self, repo_path: str | None) -> list[tuple[RepoConfig | None, Path]]:
        if self.workspace and self.workspace.repos:
            return [(r, resolve_repo_path(self.workspace, r)) for r in self.workspace.repos]
        if repo_path:
            return [(None, Path(repo_path).resolve())]
        return []

    def _state_root(self, repo_path: str | None) -> Path:
        if self.workspace and self.workspace.root_path:
            return Path(self.workspace.root_path)
        if repo_path:
            return Path(repo_path).resolve()
        return Path.cwd()

    def _branch_for_task(
        self,
        item: SprintItem,
        fp: TechFingerprint,
        repo_cfg: RepoConfig | None = None,
    ) -> str:
        template = (
            repo_cfg.branch_name_template
            if repo_cfg and repo_cfg.branch_name_template
            else self.workspace.branch_name_template
            if self.workspace
            else DEFAULT_BRANCH_NAME_TEMPLATE
        )
        key = _slugify(item.key or item.id or "task", 40)
        number = _task_number(item)
        raw_title = (item.title or "").strip()
        values = {
            "number": number,
            "key": key,
            "id": _slugify(item.id or item.key or "task", 40),
            "title": _slugify(raw_title, 30) if raw_title else "",
            "repo": _slugify(fp.repo_path or "repo", 30),
        }
        return _clean_branch_template(template.format(**values))

    def _try_worktree(self, repo: Path, branch: str) -> Path | None:
        try:
            wm = WorktreeManager(repo)
            return wm.create(branch)
        except WorktreeError as exc:
            logger.warning("worktree skipped for %s: %s", repo.name, exc)
            return None

    def _worktree_step(
        self,
        repo: Path,
        work_dir: Path,
        branch: str,
        wt_path: Path | None,
    ) -> StepReport:
        status: StepStatus = "ok" if wt_path else "skipped"
        base_commit = self._git_rev_parse(repo, "HEAD")
        if wt_path:
            message = (
                f"isolated worktree branch={branch} path={work_dir} "
                f"base={base_commit or 'unknown'} cleanup=preserved-for-review"
            )
        else:
            message = f"worktree unavailable; using repo directly branch={branch}"
        step = StepReport(step=3, name="worktree-isolation", repo=str(repo), status=status)
        step.message = message
        step.evidence.append(
            TestEvidence(
                kind="log",
                title="worktree-isolation",
                passed=wt_path is not None,
                message=message,
            )
        )
        return step

    def _git_rev_parse(self, repo: Path, ref: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", ref],
                cwd=str(repo),
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return None
        if result.returncode != 0:
            return None
        return result.stdout.strip()

    def _codegen_config(self) -> CodeGenerationConfig:
        if self.code_generation is not None:
            return self.code_generation
        if self.workspace is not None:
            return self.workspace.code_generation
        return CodeGenerationConfig()

    def _deploy_config(self) -> DeployWorkflowConfig:
        if self.deploy is not None:
            return self.deploy
        if self.workspace is not None:
            return self.workspace.deploy
        return DeployWorkflowConfig()

    def _acceptance_lines(self, item: SprintItem) -> list[str]:
        acceptance = (item.acceptance_criteria or "").strip()
        if not acceptance:
            return [item.title]
        lines = []
        for raw in acceptance.splitlines():
            line = raw.strip().lstrip("-*").strip()
            if line:
                lines.append(line)
        return lines or [acceptance]

    def _codegen_diff(self, report: StepReport) -> str:
        for evidence in report.evidence:
            if evidence.title == "llm-codegen.diff" and evidence.message:
                return evidence.message
        return ""

    def _apply_generated_diff(self, work_dir: Path, diff: str) -> tuple[bool, str]:
        patch_file: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                suffix=".diff",
                delete=False,
            ) as handle:
                handle.write(diff)
                patch_file = Path(handle.name)
            for command in (
                ["git", "apply", "--whitespace=nowarn", str(patch_file)],
                ["git", "apply", "--3way", "--whitespace=nowarn", str(patch_file)],
            ):
                result = subprocess.run(
                    command,
                    cwd=str(work_dir),
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    return True, "generated diff applied"
            error = (result.stderr or result.stdout or "git apply failed").strip()
            return False, error[:500]
        except Exception as exc:
            return False, str(exc)[:500]
        finally:
            if patch_file is not None:
                patch_file.unlink(missing_ok=True)

    def _ticket_updater(self) -> Any | None:
        updater = getattr(self.operator, "update_status", None)
        if callable(updater):
            return self.operator
        return None

    def _build_summary(self, report: RunReport) -> str:
        ok = sum(1 for s in report.steps if s.status == "ok")
        fail = sum(1 for s in report.steps if s.status == "failed")
        skip = sum(1 for s in report.steps if s.status == "skipped")
        prs = len(report.prs)
        files_modified = sum(len(s.evidence) for s in report.steps if s.evidence)
        tests_status = "PASSING" if fail == 0 else "FAILING"
        flow_status = "COMPLETE" if fail == 0 else "BLOCKED"
        exit_signal = "true" if fail == 0 else "false"
        head = f"{ok} ok, {fail} failed, {skip} skipped, {prs} PR(s)"
        ralph_block = (
            "\n---RALPH_STATUS---\n"
            f"STATUS: {flow_status}\n"
            f"TASKS_COMPLETED_THIS_LOOP: {ok}\n"
            f"FILES_MODIFIED: {files_modified}\n"
            f"TESTS_STATUS: {tests_status}\n"
            "WORK_TYPE: IMPLEMENTATION\n"
            f"EXIT_SIGNAL: {exit_signal}\n"
            f"RECOMMENDATION: {'deliver' if fail == 0 else 'inspect failed steps'}\n"
            "---END_RALPH_STATUS---"
        )
        return head + ralph_block
