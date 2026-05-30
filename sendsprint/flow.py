"""SendSprint orchestrator — the agent's end-to-end delivery flow.

SendSprint is the brain. It reads a sprint, scopes it to the operator's cards,
and for each item: opens an isolated worktree, hands the task to simplicio-cli
for the code edit, captures test + screen evidence, commits, pushes, opens a
draft PR, attaches the evidence, and updates the ticket. The PR review loop
(:meth:`SprintFlow.revise_pr`) feeds reviewer feedback back to simplicio.

simplicio-cli only ever runs one task → applied diff. Everything else here is
SendSprint's responsibility.
"""

from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from sendsprint.core import validate_sprint_plan
from sendsprint.delivery.evidence import EvidenceCollector
from sendsprint.delivery.git_ops import GitError, GitOps
from sendsprint.delivery.pr import PullRequestManager
from sendsprint.delivery.worktree import WorktreeError, WorktreeManager
from sendsprint.executor import SimplicioExecutor
from sendsprint.mapper import MapperAdapter
from sendsprint.models import RunReport, ScopeConfig, Sprint, SprintItem, StepReport, TestEvidence
from sendsprint.operators.base import BaseOperator, TransportUnavailable
from sendsprint.prompt import PromptFanout
from sendsprint.scope import apply_scope
from sendsprint.tech import TechFingerprint, detect_tech

logger = logging.getLogger(__name__)

DEFAULT_BRANCH_TEMPLATE = "feature/{number}-{title}"
IN_REVIEW_STATUS = "In Review"


@dataclass
class RepoTarget:
    """One repository SendSprint delivers against."""

    path: Path
    name: str = "repo"
    tech: str | None = None
    test_command: str | None = None
    base_branch: str = "develop"
    pr_provider: str = "github"
    repo_slug: str = ""  # owner/repo (github) or repository id (ado)
    frontend_url: str | None = None
    branch_template: str = DEFAULT_BRANCH_TEMPLATE
    organization: str = ""
    project: str = ""


@dataclass
class ItemOutcome:
    """Everything produced while delivering one sprint item."""

    item_key: str
    steps: list[StepReport] = field(default_factory=list)
    pr: object | None = None
    branch: str | None = None


class SprintFlow:
    """Drive a sprint from cards to draft PRs with evidence."""

    def __init__(
        self,
        operator: BaseOperator,
        target: RepoTarget,
        *,
        scope: ScopeConfig | None = None,
        simplicio_binary: str = "simplicio",
        draft_prs: bool = True,
        update_tickets: bool = True,
        write_specs: bool = True,
        fanout: PromptFanout | None = None,
    ) -> None:
        self.operator = operator
        self.target = target
        self.scope = scope
        self.simplicio_binary = simplicio_binary
        self.draft_prs = draft_prs
        self.update_tickets = update_tickets
        self.write_specs = write_specs
        self.fanout = fanout

    def run(
        self,
        *,
        validate_plan: bool = True,
        validate_only: bool = False,
        bootstrap_mapper: bool = True,
        retro: bool = True,
        **read_kwargs: object,
    ) -> RunReport:
        """Read the sprint, scope it, and deliver each item."""
        sprint = self.operator.read_sprint(**read_kwargs)
        if self.scope is not None:
            sprint = apply_scope(sprint, self.scope)
        report = RunReport(
            workspace=self.target.name,
            sprint_name=sprint.name,
            sprint_id=sprint.id,
            scope_mode=(self.scope.mode if self.scope else "all"),
            user=(self.scope.user_email if self.scope else None),
        )
        if validate_plan:
            validation_step, validation_notes = _validate_sprint(sprint)
            report.steps.append(validation_step)
            report.notes.extend(validation_notes)
            if validate_only or validation_step.status == "failed":
                report.failed = validation_step.status == "failed"
                report.summary = _validation_summary(sprint, validation_step, validation_notes)
                return report
        elif validate_only:
            report.steps.append(
                StepReport(
                    step=1,
                    name="validate:sprint",
                    status="skipped",
                    message="sprint validation disabled by --no-validate",
                )
            )
            report.summary = _validation_summary(sprint, report.steps[-1], [])
            return report
        if bootstrap_mapper and self.write_specs:
            bootstrap_step = self._ensure_mapper_bootstrap()
            report.steps.append(bootstrap_step)
            if bootstrap_step.status != "ok":
                report.notes.append(bootstrap_step.message or "mapper bootstrap skipped")
        logger.info(
            "run start: %s (%d item(s), scope=%s, transport=%s)",
            sprint.name,
            len(sprint.items),
            report.scope_mode,
            sprint.transport,
        )
        ordered_items = _topological_order(sprint.items)
        for index, item in enumerate(ordered_items, start=1):
            outcome = self.deliver_item(item, sprint=sprint, index=index)
            for step in outcome.steps:
                logger.info(
                    "step %s %s [%s] %s", step.step, step.name, step.status, step.message or ""
                )
            report.steps.extend(outcome.steps)
            if outcome.pr is not None:
                report.prs.append(outcome.pr)  # type: ignore[arg-type]
        report.failed = any(s.status == "failed" for s in report.steps)
        if retro and self.write_specs:
            retro_step = self._write_retrospective(sprint, report)
            report.steps.append(retro_step)
            if retro_step.status != "ok":
                report.notes.append(retro_step.message or "retrospective skipped")
            report.failed = any(s.status == "failed" for s in report.steps)
        report.summary = self._summarize(sprint, report)
        logger.info("run done: %s", report.summary)
        return report

    def deliver_item(
        self, item: SprintItem, *, sprint: Sprint | None = None, index: int = 1
    ) -> ItemOutcome:
        """Deliver one item end to end. Never raises — failures become reports."""
        outcome = ItemOutcome(item_key=item.key)
        branch = self._branch_name(item)
        outcome.branch = branch
        logger.info("deliver %s: %s -> branch %s", item.key, item.title, branch)
        wt_manager = WorktreeManager(self.target.path)
        try:
            work_dir = wt_manager.create(branch, base=self.target.base_branch)
        except WorktreeError as exc:
            outcome.steps.append(
                StepReport(step=2, name=f"worktree:{item.key}", status="failed", message=str(exc))
            )
            return outcome

        fingerprint: TechFingerprint | None = (
            None if self.target.tech else detect_tech(str(work_dir))
        )
        tech = self.target.tech or (fingerprint.primary_tech if fingerprint else None)

        context_parts: list[str] = []
        mapper_context: dict | None = None

        # Step 2b — adapt the card into the simplicio-mapper spec format.
        if self.write_specs:
            spec_step, spec_note, mapper_context = self._write_spec(work_dir, item, sprint, index)
            outcome.steps.append(spec_step)
            if spec_note:
                context_parts.append(spec_note)

        # Step 2c — optional simplicio-prompt subagent fan-out (brainstorm/plan).
        if self.fanout is not None:
            fan_step, fan_note = self._fan_out(item, mapper_context=mapper_context)
            outcome.steps.append(fan_step)
            if fan_note:
                context_parts.append(fan_note)

        # Step 3 — simplicio executes the task.
        executor = SimplicioExecutor(work_dir, binary=self.simplicio_binary)
        exec_step = executor.run_item(
            item,
            stack=tech,
            repo=self.target.name,
            extra_context="\n\n".join(context_parts) or None,
        )
        outcome.steps.append(exec_step)
        if exec_step.status != "ok":
            wt_manager.remove(branch)
            return outcome

        # Step 3b — collect evidence.
        evidence_step, evidence = self._collect_evidence(work_dir, item, tech, fingerprint)
        outcome.steps.append(evidence_step)

        # Step 4 — commit + push.
        git = GitOps(work_dir)
        try:
            committed = git.commit_all(self._commit_message(item))
            if not committed:
                outcome.steps.append(
                    StepReport(
                        step=4,
                        name=f"commit:{item.key}",
                        status="skipped",
                        message="simplicio produced no changes",
                    )
                )
                wt_manager.remove(branch)
                return outcome
            git.push(branch)
        except GitError as exc:
            outcome.steps.append(
                StepReport(step=4, name=f"commit:{item.key}", status="failed", message=str(exc))
            )
            return outcome
        outcome.steps.append(
            StepReport(step=4, name=f"commit:{item.key}", status="ok", message=f"pushed {branch}")
        )

        # Step 5 — open draft PR + attach evidence.
        pr_step, pr_info = self._open_pr(item, branch, evidence)
        outcome.steps.append(pr_step)
        outcome.pr = pr_info

        # Step 6 — update the ticket.
        if pr_info is not None and self.update_tickets:
            outcome.steps.append(self._update_ticket(item, pr_info))

        return outcome

    def revise_pr(self, pr_number: int, *, branch: str, item_key: str = "") -> list[StepReport]:
        """Review loop: pull reviewer feedback and have simplicio address it."""
        steps: list[StepReport] = []
        pr_manager = self._pr_manager()
        feedback = pr_manager.read_feedback(pr_number)
        if not feedback:
            steps.append(
                StepReport(
                    step=7, name="review:check", status="ok", message="no actionable feedback"
                )
            )
            return steps

        work_dir = WorktreeManager(self.target.path).worktree_dir(branch)
        if not work_dir.exists():
            steps.append(
                StepReport(
                    step=7,
                    name="review:revise",
                    status="failed",
                    message=f"worktree for {branch} not found; cannot revise",
                )
            )
            return steps

        feedback_text = self._review_feedback_text(feedback)
        executor = SimplicioExecutor(work_dir, binary=self.simplicio_binary)
        revise_step = executor.revise(feedback_text, stack=self.target.tech, repo=self.target.name)
        steps.append(revise_step)
        if revise_step.status != "ok":
            return steps

        # Re-collect fresh evidence and update the PR.
        item = SprintItem(id=item_key, key=item_key, type="Task", title=item_key, status="open")
        _, evidence = self._collect_evidence(work_dir, item, self.target.tech)
        git = GitOps(work_dir)
        try:
            if git.commit_all(f"fix: address review feedback on {branch}"):
                git.push(branch)
            pr_manager.post_evidence(
                pr_number,
                branch=branch,
                evidence=evidence,
                steps_completed=["revise", "evidence"],
                review_feedback=feedback,
            )
        except GitError as exc:
            steps.append(StepReport(step=7, name="review:push", status="failed", message=str(exc)))
            return steps
        steps.append(
            StepReport(step=7, name="review:revise", status="ok", message="pushed review fixes")
        )
        return steps

    # -- internals ----------------------------------------------------------

    def _write_spec(
        self, work_dir: Path, item: SprintItem, sprint: Sprint | None, index: int
    ) -> tuple[StepReport, str | None, dict | None]:
        """Materialize the card into ``.specs/`` and return a note for simplicio."""
        try:
            adapter = MapperAdapter(work_dir)
            path = adapter.write_item(item, sprint=sprint, index=index)
            mapper_context = adapter.mapper_context_for_item(item)
        except OSError as exc:  # best-effort; never abort the item
            return (
                StepReport(step=2, name=f"mapper:{item.key}", status="skipped", message=str(exc)),
                None,
                None,
            )
        rel = path.relative_to(work_dir)
        note = (
            f"A task spec was written to {rel} in the mapper format. Follow its "
            "Acceptance Criteria, Test plan, and Definition of Done."
        )
        structured = adapter.structured_context_for_item(item)
        if structured:
            note = f"{note}\n\nStructured mapper context:\n{structured}"
        return (
            StepReport(step=2, name=f"mapper:{item.key}", status="ok", message=f"spec at {rel}"),
            note,
            mapper_context or None,
        )

    def _ensure_mapper_bootstrap(self) -> StepReport:
        project_map = self.target.path / ".simplicio" / "project-map.json"
        if project_map.exists():
            return StepReport(
                step=2,
                name="mapper:index",
                repo=self.target.name,
                status="skipped",
                message=".simplicio/project-map.json already present",
            )
        executor = SimplicioExecutor(self.target.path, binary=self.simplicio_binary)
        return executor.index(self.target.path, repo=self.target.name)

    def _write_retrospective(self, sprint: Sprint, report: RunReport) -> StepReport:
        try:
            path = MapperAdapter(self.target.path).write_retrospective(sprint, report)
        except OSError as exc:
            return StepReport(
                step=8,
                name="retro:write",
                repo=self.target.name,
                status="failed",
                message=str(exc),
            )
        return StepReport(
            step=8,
            name="retro:write",
            repo=self.target.name,
            status="ok",
            message=f"retrospective at {path.relative_to(self.target.path)}",
        )

    def _fan_out(
        self, item: SprintItem, *, mapper_context: dict | None = None
    ) -> tuple[StepReport, str | None]:
        """Run the simplicio-prompt subagent fan-out for one card."""
        assert self.fanout is not None
        result = self.fanout.brainstorm(item, mapper_context=mapper_context)
        status = result.status if result.status in {"ok", "skipped", "failed"} else "skipped"
        note: str | None = None
        if result.status == "ok" and result.samples:
            joined = "\n".join(f"- {s.strip()}" for s in result.samples if s.strip())
            note = f"Subagent brainstorm ({result.completed} agents):\n{joined}"
        return (
            StepReport(
                step=3,
                name=f"fanout:{item.key}",
                tech=self.target.tech,
                status=status,  # type: ignore[arg-type]
                message=result.summary(),
            ),
            note,
        )

    def _collect_evidence(
        self,
        work_dir: Path,
        item: SprintItem,
        tech: str | None,
        fingerprint: TechFingerprint | None = None,
    ) -> tuple[StepReport, list]:
        collector = EvidenceCollector(work_dir, item_key=item.key or item.id or "item")
        evidence = (
            [collector.collect_tests(self.target.test_command)]
            if self.target.test_command is not None
            else collector.collect_detected(fingerprint or detect_tech(str(work_dir)))
        )
        if self.target.frontend_url:
            shot = collector.capture_screenshot(self.target.frontend_url, name="screen")
            if shot is not None:
                evidence.append(shot)
        passed = all(e.passed for e in evidence)
        manifest = collector.write_manifest(evidence, steps_completed=["evidence"])
        evidence.append(
            TestEvidence(
                kind="log",
                title="evidence manifest",
                passed=True,
                path=str(manifest),
                message="manifest.json",
            )
        )
        step = StepReport(
            step=5,
            name=f"evidence:{item.key}",
            repo=self.target.name,
            tech=tech,
            status="ok" if passed else "failed",
            message="tests + screen captured" if passed else "evidence shows failures",
            evidence=evidence,
        )
        return step, evidence

    def _review_feedback_text(self, feedback: list) -> str:
        lines: list[str] = []
        seen: set[tuple[str, str, str, int | None, str]] = set()
        for item in feedback:
            key = (
                getattr(item, "reviewer", "unknown"),
                str(getattr(item, "body", "") or "").strip(),
                getattr(item, "path", None) or "",
                getattr(item, "line", None),
                getattr(item, "state", ""),
            )
            if not key[1] or key in seen:
                continue
            seen.add(key)
            location = f" ({key[2]}:{key[3]})" if key[2] else ""
            lines.append(f"- @{key[0]}{location} [{key[4]}]: {key[1]}")
        return "\n".join(lines)

    def _open_pr(
        self, item: SprintItem, branch: str, evidence: list
    ) -> tuple[StepReport, object | None]:
        pr_manager = self._pr_manager()
        title = f"{item.key}: {item.title}".strip(": ")
        body = self._pr_body(item)
        try:
            pr_info = pr_manager.create_pr(
                title=title,
                body=body,
                head=branch,
                base=self.target.base_branch,
                draft=self.draft_prs,
            )
        except Exception as exc:  # noqa: BLE001 - any provider/network error is reported
            return (
                StepReport(step=6, name=f"pr:{item.key}", status="failed", message=str(exc)),
                None,
            )
        if pr_info.number is not None:
            try:
                pr_manager.post_evidence(
                    pr_info.number,
                    branch=branch,
                    evidence=evidence,
                    steps_completed=["execute", "evidence", "commit"],
                )
            except Exception as exc:  # noqa: BLE001 - evidence is best-effort
                logger.warning("failed to post evidence to PR %s: %s", pr_info.number, exc)
        return (
            StepReport(
                step=6,
                name=f"pr:{item.key}",
                status="ok",
                message=f"draft PR {pr_info.url or pr_info.number}",
                pr=pr_info,
            ),
            pr_info,
        )

    def _update_ticket(self, item: SprintItem, pr_info: object) -> StepReport:
        url = getattr(pr_info, "url", None)
        comment = f"SendSprint opened a draft PR: {url}" if url else "SendSprint opened a draft PR"
        try:
            self.operator.update_status(item.key, IN_REVIEW_STATUS, comment=comment)
        except (TransportUnavailable, Exception) as exc:  # noqa: BLE001
            return StepReport(
                step=7,
                name=f"ticket:{item.key}",
                status="skipped",
                message=f"ticket update skipped: {exc}",
            )
        return StepReport(
            step=7, name=f"ticket:{item.key}", status="ok", message=f"moved to {IN_REVIEW_STATUS}"
        )

    def _pr_manager(self) -> PullRequestManager:
        return PullRequestManager(
            self.target.pr_provider,
            self.target.repo_slug or self.target.name,
            organization=self.target.organization,
            project=self.target.project,
        )

    def _branch_name(self, item: SprintItem) -> str:
        template = self.target.branch_template or DEFAULT_BRANCH_TEMPLATE
        return template.format(number=item.key or item.id, title=_slug(item.title))

    def _commit_message(self, item: SprintItem) -> str:
        subject = f"{item.key}: {item.title}".strip(": ")
        return f"feat: {subject}"[:72]

    def _pr_body(self, item: SprintItem) -> str:
        lines = [item.description or item.title, ""]
        if item.acceptance_criteria:
            lines += ["## Acceptance criteria", item.acceptance_criteria, ""]
        if item.source_url:
            lines += [f"Ticket: {item.source_url}"]
        lines += [
            "",
            "_Delivered by SendSprint — code by simplicio-cli. Draft pending your review._",
        ]
        return "\n".join(lines)

    def _summarize(self, sprint: Sprint, report: RunReport) -> str:
        ok = sum(1 for s in report.steps if s.status == "ok")
        failed = sum(1 for s in report.steps if s.status == "failed")
        return (
            f"{sprint.name}: {len(sprint.items)} item(s), "
            f"{len(report.prs)} PR(s), {ok} ok / {failed} failed step(s)"
        )


def _slug(text: str, *, max_len: int = 40) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug[:max_len].strip("-") or "task"


def _validate_sprint(sprint: Sprint) -> tuple[StepReport, list[str]]:
    report = validate_sprint_plan(sprint)
    findings = list(report.get("findings") or [])
    errors = [f for f in findings if f.get("severity") == "error"]
    notes = [
        _format_validation_finding(f) for f in findings if f.get("severity") in {"warning", "info"}
    ]
    message = (
        _validation_message(report, errors) if errors else _validation_message(report, findings)
    )
    return (
        StepReport(
            step=1,
            name="validate:sprint",
            status="failed" if errors else "ok",
            message=message,
        ),
        notes,
    )


def _validation_message(report: dict, findings: list[dict]) -> str:
    counts = (
        f"{report.get('item_count', 0)} item(s), "
        f"{report.get('error_count', 0)} error(s), "
        f"{report.get('warning_count', 0)} warning(s), "
        f"{report.get('info_count', 0)} info"
    )
    if not findings:
        return f"sprint plan valid ({counts})"
    details = "; ".join(_format_validation_finding(f) for f in findings[:5])
    suffix = f"; +{len(findings) - 5} more" if len(findings) > 5 else ""
    return f"sprint plan has findings ({counts}): {details}{suffix}"


def _validation_summary(sprint: Sprint, step: StepReport, notes: list[str]) -> str:
    note_count = f", {len(notes)} note(s)" if notes else ""
    return f"{sprint.name}: validation {step.status}{note_count}: {step.message}"


def _format_validation_finding(finding: dict) -> str:
    item_key = finding.get("item_key")
    prefix = f"{item_key}: " if item_key else ""
    return f"{prefix}{finding.get('code', 'finding')} - {finding.get('message', '')}".strip()


def _topological_order(items: list[SprintItem]) -> list[SprintItem]:
    """Return items with parents before children while preserving source order."""
    if len(items) < 2:
        return list(items)

    keys = [item.key for item in items if item.key]
    if len(keys) != len(set(keys)):
        logger.warning("duplicate sprint item key; processing in source order")
        return list(items)

    node_ids = [item.key if item.key else f"__item_{index}" for index, item in enumerate(items)]
    by_node = dict(zip(node_ids, items, strict=True))
    key_to_node = {item.key: node for node, item in zip(node_ids, items, strict=True) if item.key}
    children: dict[str, list[str]] = {node: [] for node in node_ids}
    indegree: dict[str, int] = {node: 0 for node in node_ids}

    for node, item in zip(node_ids, items, strict=True):
        if not item.key:
            continue
        parent = item.parent_key
        if not parent or parent not in key_to_node or parent == item.key:
            continue
        parent_node = key_to_node[parent]
        children[parent_node].append(node)
        indegree[node] += 1

    ready = deque(node for node in node_ids if indegree[node] == 0)
    ordered_nodes: list[str] = []
    while ready:
        node = ready.popleft()
        ordered_nodes.append(node)
        for child_node in children.get(node, []):
            indegree[child_node] -= 1
            if indegree[child_node] == 0:
                ready.append(child_node)

    if len(ordered_nodes) != len(items):
        logger.warning("parent_key cycle detected during ordering; processing in source order")
        return list(items)

    return [by_node[node] for node in ordered_nodes]
