"""SprintFlow v2.1: 10-step orchestration across a multi-repo workspace.

Improvements over v2.0:
- Step 3.5: Lint step between build and tests
- Step 6: Fix loop reports what failed (tests vs security vs lint)
- Step 7: Commits changes before creating PR
- Empty-repos guard with explicit report entry
- to_json() for structured output
"""

from __future__ import annotations

import logging
import re
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
from sendsprint.models.reports import RunReport, StepReport, StepStatus, TestEvidence
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
from sendsprint.run_state import RunStateStore, delivery_key, stable_run_id
from sendsprint.scope import apply_scope
from sendsprint.tech import TechFingerprint, detect_tech
from sendsprint.workspace import resolve_repo_path

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
        **kwargs: Any,
    ) -> SprintFlowResult:
        report = RunReport(
            workspace=self.workspace.name if self.workspace else "single-repo",
            scope_mode=self.scope.mode,
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

        state_store = None
        state = None
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
            )
            state_store.save(state)
            resolved_run_id = state.run_id

        if not repos:
            skip = StepReport(step=2, name="no-repos", status="skipped")
            skip.message = "no repos resolved — steps 2-10 skipped"
            report.steps.append(skip)

        items_to_deliver = delivery_items(sprint)

        if not items_to_deliver and repos:
            skip = StepReport(step=2, name="no-tasks", status="skipped")
            skip.message = "sprint has 0 items after scope/status filter — steps 2-10 skipped"
            report.steps.append(skip)

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
                task_sprint = sprint.model_copy(update={"items": [item]})

                # --- Step 2: Architecture (per repo, once per task — cheap, idempotent) ---
                arch_report, build_result = self._step2_architecture(rpath, fp, report)
                if first_arch is None:
                    first_arch = arch_report
                if build_result and build_result.created_files:
                    notes.append(
                        f"[{rpath.name}] architecture docs created: "
                        + ", ".join(Path(f).name for f in build_result.created_files)
                    )

                # --- Step 3: Dev (install + build) on isolated task worktree ---
                wt_path = self._try_worktree(rpath, branch_name)
                work_dir = wt_path or rpath
                report.steps.append(self._worktree_step(rpath, work_dir, branch_name, wt_path))
                dev = DevAgent(work_dir, fp)
                self._step3_dev(dev, report, repo_cfg)
                self._step3_5_codegen(work_dir, item, report)

                # --- Step 4: Lint ---
                lint_cmd = repo_cfg.lint_command if repo_cfg else None
                linter = LintRunner(work_dir, fp, custom_command=lint_cmd)
                lint_report = self._step4_lint(linter, report)

                # --- Step 5: Tests ---
                runner = TestRunner(
                    work_dir,
                    fp,
                    custom_unit_cmd=repo_cfg.test_command if repo_cfg else None,
                    custom_e2e_cmd=repo_cfg.e2e_command if repo_cfg else None,
                )
                test_reports = self._step5_tests(runner, report)

                # --- Step 6: Security (flag only) ---
                sec = SecurityReviewer(work_dir, fp)
                sec_report = self._step6_security(sec, report)

                # --- Step 7: Fix loop ---
                self._step7_fix_loop(
                    dev,
                    linter,
                    runner,
                    sec,
                    lint_report,
                    test_reports,
                    sec_report,
                    report,
                )

                # --- Step 8: Commit ---
                self.autonomy_policy.require("commit")
                self._step8_commit(work_dir, task_sprint, report, item=item)

                # --- Step 8b: Push branch ---
                self.autonomy_policy.require("push")
                self._push_branch(work_dir, branch_name)

                # --- Step 9: Create PR (per task, per repo) ---
                self.autonomy_policy.require("create-pr")
                target = (repo_cfg.pr_target_branch if repo_cfg else None) or (
                    self.workspace.default_base_branch if self.workspace else "main"
                )
                provider = self.workspace.pr_provider if self.workspace else "github"
                reviewers = list(self.workspace.pr_reviewers) if self.workspace else []
                required_reviewers = (
                    list(self.workspace.required_pr_reviewers) if self.workspace else []
                )
                if repo_cfg:
                    reviewers.extend(repo_cfg.pr_reviewers)
                    required_reviewers.extend(repo_cfg.required_pr_reviewers)
                pr_report = self._step9_create_pr(
                    work_dir,
                    branch_name,
                    target,
                    provider,
                    reviewers,
                    required_reviewers,
                    task_sprint,
                    report,
                    item=item,
                )
                pr_validation = validate_pr_step(pr_report)
                report.steps.append(pr_validation)

                # --- Step 10: PR review + delivered ---
                self._step10_review_and_deliver(
                    work_dir,
                    branch_name,
                    target,
                    rpath,
                    pr_report,
                    report,
                )
                self._step11_deploy(item, pr_report, report, resolved_run_id)
                if state:
                    if pr_report.status == "ok" and pr_validation.status == "ok":
                        state.mark_completed(dkey)
                    else:
                        state.mark_failed(dkey, pr_report.message or "PR validation failed")
                    assert state_store is not None
                    state_store.save(state)

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
