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
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from sendsprint.agents.dev import DevAgent
from sendsprint.agents.lint_runner import LintRunner
from sendsprint.agents.pr_creator import PrCreator
from sendsprint.agents.pr_reviewer import PrReviewer
from sendsprint.agents.security_reviewer import SecurityReviewer
from sendsprint.agents.test_runner import TestRunner
from sendsprint.agents.worktree import WorktreeError, WorktreeManager
from sendsprint.architecture import ArchitectureMapper, build_architecture
from sendsprint.models import ArchitectureReport, Sprint
from sendsprint.models.reports import PrInfo, RunReport, StepReport
from sendsprint.models.workspace import RepoConfig, ScopeConfig, WorkspaceConfig
from sendsprint.operators.base import BaseOperator
from sendsprint.scope import apply_scope
from sendsprint.tech import TechFingerprint, detect_tech
from sendsprint.workspace import resolve_repo_path

logger = logging.getLogger(__name__)

MAX_FIX_LOOPS = 3


class SprintFlowResult(BaseModel):
    sprint: Sprint
    architecture: ArchitectureReport | None = None
    repo_path: str | None = None
    notes: list[str] = Field(default_factory=list)
    run_report: RunReport | None = None

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
    ) -> None:
        self.operator = operator
        self.workspace = workspace
        self.scope = scope or ScopeConfig()
        self.mapper = ArchitectureMapper()

    def run(
        self,
        sprint_id: str | int | None = None,
        iteration_path: str | None = None,
        repo_path: str | None = None,
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

        notes: list[str] = []
        first_arch: ArchitectureReport | None = None

        repos = self._resolve_repos(repo_path)

        if not repos:
            skip = StepReport(step=2, name="no-repos", status="skipped")
            skip.message = "no repos resolved — steps 2-10 skipped"
            report.steps.append(skip)

        for repo_cfg, rpath in repos:
            fp = detect_tech(rpath)
            branch_name = f"sendsprint/{fp.primary_tech or 'dev'}"

            # --- Step 2: Architecture ---
            arch_report, build_result = self._step2_architecture(rpath, fp, report)
            if first_arch is None:
                first_arch = arch_report
            if build_result and build_result.created_files:
                notes.append(
                    f"[{rpath.name}] architecture docs created: "
                    + ", ".join(Path(f).name for f in build_result.created_files)
                )

            # --- Step 3: Dev (install + build) ---
            wt_path = self._try_worktree(rpath, branch_name)
            work_dir = wt_path or rpath
            dev = DevAgent(work_dir, fp)
            self._step3_dev(dev, report, repo_cfg)

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
                dev, linter, runner, sec,
                lint_report, test_reports, sec_report, report,
            )

            # --- Step 8: Commit ---
            self._step8_commit(work_dir, sprint, report)

            # --- Step 8b: Push branch ---
            self._push_branch(work_dir, branch_name)

            # --- Step 9: Create PR ---
            target = (repo_cfg.pr_target_branch if repo_cfg else None) or (
                self.workspace.default_base_branch if self.workspace else "main"
            )
            provider = self.workspace.pr_provider if self.workspace else "github"
            reviewers = self.workspace.pr_reviewers if self.workspace else []
            pr_report = self._step9_create_pr(
                work_dir, branch_name, target, provider, reviewers, sprint, report
            )

            # --- Step 10: PR review + delivered ---
            self._step10_review_and_deliver(
                work_dir, branch_name, target, rpath, pr_report, report
            )

        report.finished_at = datetime.now(tz=timezone.utc)
        report.failed = any(s.status == "failed" for s in report.steps)
        report.summary = self._build_summary(report)

        return SprintFlowResult(
            sprint=sprint,
            architecture=first_arch,
            repo_path=repo_path,
            notes=notes,
            run_report=report,
        )

    # ── Step implementations ──────────────────────────────────────────

    def _step1_read_sprint(
        self,
        sprint_id: str | int | None,
        iteration_path: str | None,
        report: RunReport,
        **kwargs: Any,
    ) -> Sprint:
        step = StepReport(step=1, name="read-sprint", status="running")
        step.started_at = datetime.now(tz=timezone.utc)
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
        step.finished_at = datetime.now(tz=timezone.utc)
        report.steps.append(step)
        return sprint

    def _step2_architecture(
        self, repo: Path, fp: TechFingerprint, report: RunReport
    ) -> tuple[ArchitectureReport, Any]:
        step = StepReport(step=2, name="architecture", repo=str(repo), status="running")
        step.started_at = datetime.now(tz=timezone.utc)
        arch = self.mapper.inspect(repo)
        build_result = None
        if not arch.is_mapped:
            build_result = build_architecture(repo, fingerprint=fp)
            arch = self.mapper.inspect(repo)
            step.message = (
                f"built {len(build_result.created_files)} doc(s), score {arch.score:.2f}"
            )
        else:
            step.message = f"already mapped, score {arch.score:.2f}"
        step.status = "ok" if arch.is_mapped else "failed"
        step.finished_at = datetime.now(tz=timezone.utc)
        report.steps.append(step)
        return arch, build_result

    def _step3_dev(
        self, dev: DevAgent, report: RunReport, repo_cfg: RepoConfig | None
    ) -> None:
        install_report = dev.install()
        report.steps.append(install_report)
        custom_build = repo_cfg.build_command if repo_cfg else None
        build_report = dev.build(custom_command=custom_build)
        report.steps.append(build_report)

    def _step4_lint(self, linter: LintRunner, report: RunReport) -> StepReport:
        result = linter.run()
        report.steps.append(result)
        return result

    def _step5_tests(self, runner: TestRunner, report: RunReport) -> list[StepReport]:
        results = runner.run_all()
        for r in results:
            report.steps.append(r)
        return results

    def _step6_security(
        self, sec: SecurityReviewer, report: RunReport
    ) -> StepReport:
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

            loop_step = StepReport(
                step=7, name=f"fix-loop-{attempt}", status="running"
            )
            loop_step.started_at = datetime.now(tz=timezone.utc)

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
                f"attempt {attempt}/{MAX_FIX_LOOPS}, "
                f"triggered by: {', '.join(failures)}"
            )
            loop_step.finished_at = datetime.now(tz=timezone.utc)
            report.steps.append(loop_step)

    def _step8_commit(
        self, work_dir: Path, sprint: Sprint, report: RunReport
    ) -> StepReport:
        step = StepReport(step=8, name="commit", repo=str(work_dir), status="running")
        step.started_at = datetime.now(tz=timezone.utc)
        try:
            subprocess.run(
                ["git", "add", "-A"],
                cwd=str(work_dir), capture_output=True, text=True, timeout=30,
            )
            result = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(work_dir), capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                step.status = "skipped"
                step.message = "no changes to commit"
            else:
                msg = f"[SendSprint] {sprint.name} — automated delivery"
                subprocess.run(
                    ["git", "commit", "-m", msg],
                    cwd=str(work_dir), capture_output=True, text=True,
                    timeout=30, check=True,
                )
                step.status = "ok"
                step.message = "changes committed"
        except subprocess.CalledProcessError as exc:
            step.status = "failed"
            step.message = f"git commit failed: {exc.stderr[:500]}"
        except Exception as exc:
            step.status = "failed"
            step.message = str(exc)[:500]
        step.finished_at = datetime.now(tz=timezone.utc)
        report.steps.append(step)
        return step

    def _step9_create_pr(
        self,
        work_dir: Path,
        branch: str,
        target: str,
        provider: str,
        reviewers: list[str],
        sprint: Sprint,
        report: RunReport,
    ) -> StepReport:
        creator = PrCreator(
            work_dir,
            provider=provider,
            target_branch=target,
            reviewers=reviewers,
        )
        title = f"[SendSprint] {sprint.name} — {work_dir.name}"
        body = (
            f"Automated PR by SendSprint.\n\n"
            f"Sprint: {sprint.name} ({sprint.id})\n"
            f"Items: {len(sprint.items)}\n"
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
        done.message = (
            f"PR for {rpath.name} delivered"
            + (f" -> {pr_report.pr.url}" if pr_report and pr_report.pr else "")
        )
        report.steps.append(done)
        if pr_report and pr_report.pr:
            report.prs.append(pr_report.pr)

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
            return [
                (r, resolve_repo_path(self.workspace, r)) for r in self.workspace.repos
            ]
        if repo_path:
            return [(None, Path(repo_path).resolve())]
        return []

    def _try_worktree(self, repo: Path, branch: str) -> Path | None:
        try:
            wm = WorktreeManager(repo)
            return wm.create(branch)
        except WorktreeError as exc:
            logger.warning("worktree skipped for %s: %s", repo.name, exc)
            return None

    def _build_summary(self, report: RunReport) -> str:
        ok = sum(1 for s in report.steps if s.status == "ok")
        fail = sum(1 for s in report.steps if s.status == "failed")
        skip = sum(1 for s in report.steps if s.status == "skipped")
        prs = len(report.prs)
        return f"{ok} ok, {fail} failed, {skip} skipped, {prs} PR(s)"
