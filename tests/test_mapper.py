"""Tests for the simplicio-mapper .specs/ adapter."""

from __future__ import annotations

from sendsprint.mapper import MapperAdapter
from sendsprint.models.sprint import Sprint, SprintItem


def _item(**kw) -> SprintItem:
    base = dict(id="1", key="ABC-12", type="Task", title="Add login button", status="open")
    base.update(kw)
    return SprintItem(**base)  # type: ignore[arg-type]


def test_materialize_sprint_writes_specs(tmp_path):
    sprint = Sprint(
        id="7",
        name="Sprint 7",
        source="jira",
        items=[
            _item(),
            _item(id="2", key="ABC-13", title="Fix logout", status="in progress"),
        ],
    )
    out = MapperAdapter(tmp_path).materialize_sprint(sprint)
    assert out.sprint_dir.name == "sprint-07"
    assert out.sprint_md.exists()
    assert out.backlog_md.exists()
    assert [p.name for p in out.tasks] == [
        "01-add-login-button.task.md",
        "02-fix-logout.task.md",
    ]
    body = out.tasks[0].read_text()
    assert body.startswith("---")
    assert "id: TASK-ABC-12" in body
    assert "sprint: sprint-07" in body
    assert "## Acceptance Criteria" in body
    assert "## Definition of Done" in body
    sprint_md = out.sprint_md.read_text()
    assert "# Sprint 7" in sprint_md
    assert "01-add-login-button.task.md" in sprint_md


def test_status_mapping_and_acceptance(tmp_path):
    item = _item(
        status="In Review",
        acceptance_criteria="- user can click\n- shows spinner",
        assignee="alice",
        source_url="https://j/ABC-12",
    )
    path = MapperAdapter(tmp_path).write_item(item, index=3)
    body = path.read_text()
    assert "status: doing" in body
    assert "owner: @alice" in body
    assert "AC-1 — user can click" in body
    assert "AC-2 — shows spinner" in body
    assert "Ticket: https://j/ABC-12" in body
    assert path.name == "03-add-login-button.task.md"


def test_done_status(tmp_path):
    body = MapperAdapter(tmp_path).write_item(_item(status="Closed")).read_text()
    assert "status: done" in body


def test_write_item_without_sprint_synthesizes(tmp_path):
    path = MapperAdapter(tmp_path).write_item(_item())
    assert path.exists()
    assert path.parent.name.startswith("sprint")
    assert (path.parent / "SPRINT.md").exists()


def test_default_acceptance_when_missing(tmp_path):
    body = MapperAdapter(tmp_path).write_item(_item(acceptance_criteria=None)).read_text()
    assert "AC-1 — Add login button is implemented" in body
