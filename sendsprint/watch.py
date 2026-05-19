"""Polling autopilot for assigned Jira/Azure DevOps tasks."""

from __future__ import annotations

import subprocess
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from sendsprint.agents.sprint_importer import _slugify
from sendsprint.agents.story_task_planner import item_matches_repo
from sendsprint.evidence import create_evidence_bundle
from sendsprint.flow import SprintFlow
from sendsprint.flow.sprint_flow import (
    DEFAULT_BRANCH_NAME_TEMPLATE,
    _clean_branch_template,
    _task_number,
)
from sendsprint.models import Sprint, SprintItem
from sendsprint.models.workspace import WorkspaceConfig
from sendsprint.operators import AzureDevopsOperator, JiraOperator
from sendsprint.operators.base import BaseOperator, Transport
from sendsprint.policy import AutonomyPolicy
from sendsprint.scope import build_scope
from sendsprint.watch_state import WatchStateStore, normalize_revision
from sendsprint.workspace import resolve_repo_path

WatchAction = Literal["eligible", "blocked", "skipped", "processed"]


class WatchTaskDecision(BaseModel):
    """Decision for one task observed by the watcher."""

    action: WatchAction
    task_id: str
    key: str
    revision: str | None = None
    status: str
    reason: str | None = None
    run_id: str | None = None
    branch: str | None = None
    pr_url: str | None = None


class WatchCycleResult(BaseModel):
    """One polling cycle output."""

    provider: str
    sprint_id: str
    checked: int = 0
    eligible: list[WatchTaskDecision] = Field(default_factory=list)
    skipped: list[WatchTaskDecision] = Field(default_factory=list)
    blocked: list[WatchTaskDecision] = Field(default_factory=list)
    processed: list[WatchTaskDecision] = Field(default_factory=list)
    dry_run: bool = False

    def summary(self) -> str:
        return (
            f"checked={self.checked} eligible={len(self.eligible)} "
            f"processed={len(self.processed)} skipped={len(self.skipped)} "
            f"blocked={len(self.blocked)}"
        )


class Watcher:
    """Poll a tracker and dispatch eligible work items through SendSprint."""

    def __init__(
        self,
        *,
        workspace: WorkspaceConfig,
        operator: BaseOperator | None = None,
        autonomy_policy: AutonomyPolicy | None = None,
        transport: Transport = "auto",
        flow_factory: Callable[..., SprintFlow] = SprintFlow,
        state_store: WatchStateStore | None = None,
    ) -> None:
        self.workspace = workspace
        self.config = workspace.watch
        self.operator = operator or self._build_operator(transport)
        self.autonomy_policy = autonomy_policy or AutonomyPolicy(level="plan")
        self.flow_factory = flow_factory
        self.state_store = state_store or WatchStateStore(self._state_path())

    def run_forever(
        self,
        *,
        interval_minutes: int | None = None,
        dry_run: bool = False,
        force: bool = False,
        max_cycles: int | None = None,
    ) -> list[WatchCycleResult]:
        """Run polling cycles until interrupted or ``max_cycles`` is reached."""
        results: list[WatchCycleResult] = []
        interval = interval_minutes or self.config.interval_minutes
        cycles = 0
        while True:
            results.append(self.run_once(dry_run=dry_run, force=force))
            cycles += 1
            if max_cycles is not None and cycles >= max_cycles:
                return results
            time.sleep(interval * 60)

    def run_once(self, *, dry_run: bool = False, force: bool = False) -> WatchCycleResult:
        """Run a single polling cycle."""
        sprint = self._read_sprint()
        state = self.state_store.load()
        result = WatchCycleResult(
            provider=self.config.provider,
            sprint_id=str(sprint.id),
            checked=len(sprint.items),
            dry_run=dry_run,
        )
        candidates = self._eligible_candidates(sprint, result, force=force)
        candidates = candidates[: self.config.max_tasks_per_cycle]
        for item in candidates:
            revision = item_revision(item)
            run_id = watch_run_id(item)
            branch = self._branch_for_item(item)
            result.eligible.append(
                WatchTaskDecision(
                    action="eligible",
                    task_id=item.id,
                    key=item.key,
                    revision=normalize_revision(revision),
                    status=item.status,
                    run_id=run_id,
                    branch=branch,
                )
            )
            if dry_run:
                continue
            if self.autonomy_policy.level == "observe":
                result.skipped.append(
                    WatchTaskDecision(
                        action="skipped",
                        task_id=item.id,
                        key=item.key,
                        revision=normalize_revision(revision),
                        status=item.status,
                        reason="autonomy observe lists eligible tasks only",
                        run_id=run_id,
                        branch=branch,
                    )
                )
                continue
            if self.config.require_clean_worktree and self.autonomy_policy.allows("write-files"):
                dirty = self._dirty_repos()
                if dirty:
                    reason = "dirty worktree: " + ", ".join(dirty)
                    self.state_store.mark(
                        state,
                        task_id=item.id,
                        revision=revision,
                        status=item.status,
                        final_status="blocked",
                        run_id=run_id,
                        branch=branch,
                        skip_reason=reason,
                    )
                    result.blocked.append(
                        WatchTaskDecision(
                            action="blocked",
                            task_id=item.id,
                            key=item.key,
                            revision=normalize_revision(revision),
                            status=item.status,
                            reason=reason,
                            run_id=run_id,
                            branch=branch,
                        )
                    )
                    continue
            try:
                flow_result = self._run_flow_for_item(item, run_id)
                pr_url = None
                if flow_result.run_report and flow_result.run_report.prs:
                    pr_url = flow_result.run_report.prs[0].url
                self._write_evidence(run_id, flow_result)
                self.state_store.mark(
                    state,
                    task_id=item.id,
                    revision=revision,
                    status=item.status,
                    final_status="ok",
                    run_id=run_id,
                    branch=branch,
                    pr_url=pr_url,
                )
                result.processed.append(
                    WatchTaskDecision(
                        action="processed",
                        task_id=item.id,
                        key=item.key,
                        revision=normalize_revision(revision),
                        status=item.status,
                        run_id=run_id,
                        branch=branch,
                        pr_url=pr_url,
                    )
                )
            except Exception as exc:  # pragma: no cover - exercised through tests with RuntimeError
                message = str(exc)[:1000]
                self.state_store.mark(
                    state,
                    task_id=item.id,
                    revision=revision,
                    status=item.status,
                    final_status="failed",
                    run_id=run_id,
                    branch=branch,
                    failure_reason=message,
                )
                result.blocked.append(
                    WatchTaskDecision(
                        action="blocked",
                        task_id=item.id,
                        key=item.key,
                        revision=normalize_revision(revision),
                        status=item.status,
                        reason=message,
                        run_id=run_id,
                        branch=branch,
                    )
                )
        if not dry_run:
            self.state_store.save(state)
        return result

    def _eligible_candidates(
        self,
        sprint: Sprint,
        result: WatchCycleResult,
        *,
        force: bool,
    ) -> list[SprintItem]:
        candidates: list[SprintItem] = []
        state = self.state_store.load()
        for item in sorted(sprint.items, key=lambda i: (i.status.lower(), i.key or i.id)):
            reason = self._ineligibility_reason(item)
            revision = item_revision(item)
            if reason is None:
                should, skip_reason = self.state_store.should_process(
                    state,
                    task_id=item.id,
                    revision=revision,
                    status=item.status,
                    force=force,
                )
                if not should:
                    reason = skip_reason
            if reason is not None:
                result.skipped.append(
                    WatchTaskDecision(
                        action="skipped",
                        task_id=item.id,
                        key=item.key,
                        revision=normalize_revision(revision),
                        status=item.status,
                        reason=reason,
                    )
                )
                continue
            repo_reason = self._repo_inference_reason(item)
            if repo_reason is not None:
                result.blocked.append(
                    WatchTaskDecision(
                        action="blocked",
                        task_id=item.id,
                        key=item.key,
                        revision=normalize_revision(revision),
                        status=item.status,
                        reason=repo_reason,
                    )
                )
                continue
            candidates.append(item)
        return candidates

    def _ineligibility_reason(self, item: SprintItem) -> str | None:
        if item.status.strip().lower() in normalized_set(self.config.ignored_states):
            return f"state ignored: {item.status}"
        allowed_states = normalized_set(self.config.allowed_states)
        if allowed_states and item.status.strip().lower() not in allowed_states:
            return f"state not allowed: {item.status}"
        work_item_types = normalized_set(self.config.work_item_types)
        if work_item_types and item.type.strip().lower() not in work_item_types:
            return f"type not allowed: {item.type}"
        if self.config.scope == "assigned_to_me" and not self._is_assigned_to_operator(item):
            return "not assigned to configured user"
        if not has_enough_description(item):
            return "description is insufficient and no parent/acceptance criteria is available"
        return None

    def _repo_inference_reason(self, item: SprintItem) -> str | None:
        if len(self.workspace.repos) <= 1:
            return None
        matches = [
            repo
            for repo in self.workspace.repos
            if item_matches_repo(item, repo.role) or scope_label_matches(item, repo.role)
        ]
        if matches:
            return None
        return "target repository cannot be inferred safely"

    def _is_assigned_to_operator(self, item: SprintItem) -> bool:
        identities = {
            self.workspace.user_email,
            self.workspace.user_display_name,
            self.workspace.user_account_id,
            self.workspace.user_descriptor,
        }
        if not any(identities):
            current_user: dict[str, str | None] = getattr(
                self.operator, "current_user", lambda: {}
            )()
            identities.update(
                {
                    current_user.get("emailAddress"),
                    current_user.get("displayName"),
                    current_user.get("accountId"),
                    current_user.get("descriptor"),
                }
            )
        item_identities = {
            item.assignee_email,
            item.assignee,
            item.assignee_account_id,
            item.assignee_descriptor,
        }
        normalized = {str(value).strip().lower() for value in identities if value}
        return bool(normalized & {str(value).strip().lower() for value in item_identities if value})

    def _run_flow_for_item(self, item: SprintItem, run_id: str) -> Any:
        scope = build_scope(
            mode="all",
            task_keys=[item.key or item.id],
            allowed_statuses=self.config.allowed_states,
        )
        flow = self.flow_factory(
            operator=self.operator,
            workspace=self.workspace,
            scope=scope,
            autonomy_policy=self.autonomy_policy,
        )
        dry_run = not self.autonomy_policy.allows("write-files")
        return flow.run(
            sprint_id=self.config.sprint_id,
            iteration_path=self.config.iteration_path,
            dry_run=dry_run,
            resume=True,
            run_id=run_id,
        )

    def _write_evidence(self, run_id: str, flow_result: Any) -> None:
        run_dir = self._runs_root() / run_id
        run_dir.mkdir(parents=True, exist_ok=True)
        if getattr(flow_result, "run_report", None):
            report = flow_result.run_report
            (run_dir / "run-report.json").write_text(
                report.model_dump_json(indent=2), encoding="utf-8"
            )
            (run_dir / "summary.md").write_text(report.summary or "No summary", encoding="utf-8")
            create_evidence_bundle(report, run_dir / "evidence")

    def _read_sprint(self) -> Sprint:
        if self.config.provider == "jira":
            return self.operator.read_sprint(sprint_id=self.config.sprint_id)
        return self.operator.read_sprint(iteration_path=self.config.iteration_path)

    def _build_operator(self, transport: Transport) -> BaseOperator:
        if self.config.provider == "jira":
            return JiraOperator(transport=transport)
        return AzureDevopsOperator(transport=transport)

    def _branch_for_item(self, item: SprintItem) -> str:
        template = self.workspace.branch_name_template or DEFAULT_BRANCH_NAME_TEMPLATE
        values = {
            "number": _task_number(item),
            "key": _slugify(item.key or item.id or "task", 40),
            "id": _slugify(item.id or item.key or "task", 40),
            "title": _slugify(item.title or "", 30),
            "repo": self.workspace.name,
        }
        return _clean_branch_template(template.format(**values))

    def _dirty_repos(self) -> list[str]:
        dirty: list[str] = []
        for repo in self.workspace.repos:
            path = resolve_repo_path(self.workspace, repo)
            if not path.exists():
                dirty.append(f"{repo.name}: missing")
                continue
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(path),
                capture_output=True,
                text=True,
                timeout=15,
                check=False,
            )
            if result.returncode != 0 or result.stdout.strip():
                dirty.append(repo.name)
        return dirty

    def _state_path(self) -> Path:
        configured = Path(self.config.state_path).expanduser()
        if configured.is_absolute():
            return configured
        return Path(self.workspace.root_path).expanduser() / configured

    def _runs_root(self) -> Path:
        return self._state_path().parent


def item_revision(item: SprintItem) -> str | int | None:
    if item.revision is not None:
        return item.revision
    return item.updated_at.isoformat() if item.updated_at else None


def watch_run_id(item: SprintItem) -> str:
    timestamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    return f"watch-{_slugify(item.key or item.id, 50)}-{timestamp}"


def normalized_set(values: list[str]) -> set[str]:
    return {value.strip().lower() for value in values if value.strip()}


def has_enough_description(item: SprintItem) -> bool:
    text = " ".join(
        value for value in (item.description, item.acceptance_criteria, item.parent_key) if value
    )
    return len(text.strip()) >= 10


def scope_label_matches(item: SprintItem, repo_role: str) -> bool:
    labels = normalized_set(item.labels)
    if repo_role == "front":
        return bool(labels & {"scope:front", "front", "frontend"})
    if repo_role in {"api", "back"}:
        return bool(labels & {"scope:back", "scope:api", "back", "backend", "api"})
    return f"scope:{repo_role}" in labels


__all__ = ["WatchCycleResult", "WatchTaskDecision", "Watcher"]
