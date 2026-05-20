"""Tests for ``sendsprint watch`` polling autopilot."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from sendsprint.cli import app
from sendsprint.models.sprint import Sprint, SprintItem
from sendsprint.models.workspace import RepoConfig, WorkspaceConfig
from sendsprint.policy import AutonomyPolicy
from sendsprint.watch import Watcher
from sendsprint.watch_config import parse_interval_minutes


class FakeOperator:
    source = "azuredevops"

    def __init__(self, sprint: Sprint) -> None:
        self.sprint = sprint
        self.calls: list[dict[str, object]] = []

    def read_sprint(self, **kwargs):
        self.calls.append(kwargs)
        return self.sprint

    def current_user(self):
        return {"emailAddress": "dev@example.com", "displayName": "Dev User"}


class FakeFlow:
    calls: list[dict[str, object]] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def run(self, **kwargs):
        self.calls.append({"init": self.kwargs, "run": kwargs})
        return SimpleNamespace(run_report=None, delivery_plan=None, notes=[])


class FakeBootstrapRuntime:
    init_calls: list[dict[str, object]] = []
    bootstrap_calls: list[dict[str, object]] = []

    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.init_calls.append(kwargs)

    def bootstrap(self, **kwargs):
        self.bootstrap_calls.append({"init": self.kwargs, "bootstrap": kwargs})
        return SimpleNamespace(run_report=None, delivery_plan=None, notes=[])


def _item(
    key: str,
    *,
    revision: int = 1,
    status: str = "New",
    item_type: str = "Task",
    assignee_email: str | None = "dev@example.com",
) -> SprintItem:
    return SprintItem(
        id=key,
        key=key,
        type=item_type,  # type: ignore[arg-type]
        title="Fix project search",
        description="Detailed enough task description",
        status=status,
        revision=revision,
        assignee_email=assignee_email,
    )


def _workspace(tmp_path: Path, *, max_tasks_per_cycle: int = 1) -> WorkspaceConfig:
    return WorkspaceConfig(
        name="fatura-ip",
        root_path=str(tmp_path),
        user_email="dev@example.com",
        branch_name_template="feature/{number}_{title}",
        repos=[RepoConfig(name="api", path="api", role="api")],
        watch={
            "enabled": True,
            "provider": "azuredevops",
            "iteration_path": "Team\\Sprint 29",
            "max_tasks_per_cycle": max_tasks_per_cycle,
            "allowed_states": ["New"],
            "ignored_states": ["Removed", "Closed", "Done"],
            "work_item_types": ["Task"],
        },
    )


def test_parse_interval_minutes() -> None:
    assert parse_interval_minutes("15m") == 15
    assert parse_interval_minutes("1h") == 60
    assert parse_interval_minutes(2) == 2


def test_watch_filters_eligibility_by_user_state_type_and_limit(tmp_path: Path) -> None:
    sprint = Sprint(
        id="sprint-29",
        name="Sprint 29",
        source="azuredevops",
        items=[
            _item("179851"),
            _item("179852", status="Closed"),
            _item("179853", assignee_email="other@example.com"),
            _item("179854", item_type="Bug"),
        ],
    )
    FakeFlow.calls = []
    watcher = Watcher(
        workspace=_workspace(tmp_path, max_tasks_per_cycle=1),
        operator=FakeOperator(sprint),
        autonomy_policy=AutonomyPolicy(level="plan"),
        flow_factory=FakeFlow,
    )

    result = watcher.run_once()

    assert [d.key for d in result.eligible] == ["179851"]
    assert len(result.processed) == 1
    assert len(FakeFlow.calls) == 1
    assert FakeFlow.calls[0]["run"]["dry_run"] is True
    assert result.eligible[0].branch == "feature/179851_fix-project-search"
    skipped = {d.key: d.reason for d in result.skipped}
    assert skipped["179852"] == "state ignored: Closed"
    assert skipped["179853"] == "not assigned to configured user"
    assert skipped["179854"] == "type not allowed: Bug"


def test_watch_deduplicates_and_reprocesses_when_revision_changes(tmp_path: Path) -> None:
    item = _item("179851", revision=1)
    sprint = Sprint(id="sprint-29", name="Sprint 29", source="azuredevops", items=[item])
    operator = FakeOperator(sprint)
    FakeFlow.calls = []
    watcher = Watcher(
        workspace=_workspace(tmp_path),
        operator=operator,
        autonomy_policy=AutonomyPolicy(level="plan"),
        flow_factory=FakeFlow,
    )

    first = watcher.run_once()
    second = watcher.run_once()
    operator.sprint = sprint.model_copy(update={"items": [_item("179851", revision=2)]})
    third = watcher.run_once()

    assert len(first.processed) == 1
    assert len(second.processed) == 0
    assert second.skipped[0].reason == "already processed for this status and revision"
    assert len(third.processed) == 1
    assert len(FakeFlow.calls) == 2


def test_watch_dry_run_lists_without_writing_state(tmp_path: Path) -> None:
    sprint = Sprint(
        id="sprint-29",
        name="Sprint 29",
        source="azuredevops",
        items=[_item("179851")],
    )
    watcher = Watcher(
        workspace=_workspace(tmp_path),
        operator=FakeOperator(sprint),
        autonomy_policy=AutonomyPolicy(level="plan"),
        flow_factory=FakeFlow,
    )

    result = watcher.run_once(dry_run=True)

    assert len(result.eligible) == 1
    assert len(result.processed) == 0
    assert not (tmp_path / ".sendsprint" / "runs" / "watch-state.json").exists()


def test_watch_accepts_runtime_bootstrap_instead_of_legacy_run(tmp_path: Path) -> None:
    sprint = Sprint(
        id="sprint-29",
        name="Sprint 29",
        source="azuredevops",
        items=[_item("179851")],
    )
    FakeBootstrapRuntime.init_calls = []
    FakeBootstrapRuntime.bootstrap_calls = []
    watcher = Watcher(
        workspace=_workspace(tmp_path),
        operator=FakeOperator(sprint),
        autonomy_policy=AutonomyPolicy(level="plan"),
        flow_factory=FakeBootstrapRuntime,
    )

    result = watcher.run_once()

    assert len(result.processed) == 1
    assert len(FakeBootstrapRuntime.init_calls) == 1
    assert len(FakeBootstrapRuntime.bootstrap_calls) == 1
    assert FakeBootstrapRuntime.bootstrap_calls[0]["bootstrap"]["resume"] is True
    assert FakeBootstrapRuntime.bootstrap_calls[0]["bootstrap"]["run_id"].startswith("watch-")


def test_watch_cli_help_documents_command() -> None:
    result = CliRunner().invoke(app, ["watch", "--help"])

    assert result.exit_code == 0
    assert "Watch Jira/Azure DevOps periodically" in result.output
    normalized = result.output.replace("\n", "").replace(" ", "")
    assert "--dry-run" in normalized


def test_watch_cli_dry_run_lists_tasks(monkeypatch, tmp_path: Path) -> None:
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text("name: ws\nroot_path: .\n", encoding="utf-8")

    class FakeWatcher:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def run_once(self, *, dry_run: bool, force: bool):
            del force
            assert dry_run is True
            return SimpleNamespace(
                provider="azuredevops",
                sprint_id="sprint-29",
                eligible=[
                    SimpleNamespace(
                        action="eligible",
                        task_id="179851",
                        key="179851",
                        revision="1",
                        status="New",
                        run_id="run",
                        branch="feature/179851-task",
                        reason=None,
                        pr_url=None,
                    )
                ],
                processed=[],
                skipped=[],
                blocked=[],
                summary=lambda: "checked=1 eligible=1 processed=0 skipped=0 blocked=0",
            )

    monkeypatch.setattr("sendsprint.cli.Watcher", FakeWatcher)

    result = CliRunner().invoke(app, ["watch", "--workspace", str(ws_file), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert "179851" in result.output
    assert "feature/179851-task" in result.output
