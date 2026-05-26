"""Tests for the simplicio-cli executor wrapper."""

from __future__ import annotations

import subprocess
from types import SimpleNamespace

from sendsprint.executor import SimplicioExecutor, SimplicioTask
from sendsprint.models.sprint import SprintItem


def _item(**kw) -> SprintItem:
    base = {"id": "1", "key": "ABC-1", "type": "Task", "title": "Hide delete button", "status": "open"}
    base.update(kw)
    return SprintItem(**base)


def _runner(returncode: int = 0, stdout: str = "", stderr: str = ""):
    calls: list[list[str]] = []

    def run(argv, **kwargs):  # noqa: ANN001
        calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_task_argv_builds_all_flags():
    task = SimplicioTask(
        description="do it", stack="angular", target="a.html", criteria="c", constraints="x"
    )
    argv = task.argv()
    assert argv[:3] == ["simplicio", "task", "do it"]
    assert "--stack" in argv and "angular" in argv
    assert "--target" in argv and "--criteria" in argv and "--constraints" in argv


def test_task_from_item_uses_title_description_and_criteria():
    ex = SimplicioExecutor(".")
    task = ex.task_from_item(_item(description="more detail", acceptance_criteria="must work"))
    assert "Hide delete button" in task.description
    assert "more detail" in task.description
    assert task.criteria == "must work"


def test_run_ok(monkeypatch):
    runner = _runner(returncode=0, stdout="done")
    ex = SimplicioExecutor(".", runner=runner)
    monkeypatch.setattr(ex, "is_available", lambda: True)
    result = ex.run(SimplicioTask(description="do it", stack="python"))
    assert result.status == "ok"
    assert runner.calls[0][:2] == ["simplicio", "task"]


def test_run_failed(monkeypatch):
    ex = SimplicioExecutor(".", runner=_runner(returncode=2, stderr="boom"))
    monkeypatch.setattr(ex, "is_available", lambda: True)
    result = ex.run(SimplicioTask(description="do it"))
    assert result.status == "failed"
    assert result.returncode == 2


def test_run_skipped_when_not_installed(monkeypatch):
    ex = SimplicioExecutor(".", runner=_runner())
    monkeypatch.setattr(ex, "is_available", lambda: False)
    result = ex.run(SimplicioTask(description="do it"))
    assert result.status == "skipped"


def test_run_timeout(monkeypatch):
    def boom(*a, **k):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd="simplicio", timeout=1)

    ex = SimplicioExecutor(".", runner=boom)
    monkeypatch.setattr(ex, "is_available", lambda: True)
    result = ex.run(SimplicioTask(description="do it"))
    assert result.status == "failed"
    assert "timed out" in result.message


def test_run_item_returns_step(monkeypatch):
    ex = SimplicioExecutor(".", runner=_runner(returncode=0))
    monkeypatch.setattr(ex, "is_available", lambda: True)
    step = ex.run_item(_item(), stack="python", repo="r")
    assert step.step == 3
    assert step.status == "ok"
    assert step.name == "execute:ABC-1"


def test_revise_builds_feedback_task(monkeypatch):
    captured = SimpleNamespace(task=None)

    ex = SimplicioExecutor(".", runner=_runner(returncode=0))
    monkeypatch.setattr(ex, "is_available", lambda: True)
    orig_run = ex.run

    def spy(task):  # noqa: ANN001
        captured.task = task
        return orig_run(task)

    monkeypatch.setattr(ex, "run", spy)
    step = ex.revise("- @bob: rename the variable", stack="python")
    assert step.status == "ok"
    assert "review feedback" in captured.task.description
    assert "@bob" in captured.task.description
