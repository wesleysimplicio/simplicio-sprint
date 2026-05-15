"""Tests for SprintFlow helpers (branch naming per task)."""

from __future__ import annotations

from unittest.mock import MagicMock

from sendsprint.flow.sprint_flow import SprintFlow
from sendsprint.models.sprint import SprintItem
from sendsprint.models.workspace import RepoConfig, WorkspaceConfig
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
