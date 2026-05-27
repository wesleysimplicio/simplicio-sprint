"""Tests for the simplicio-prompt subagent fan-out wrapper."""

from __future__ import annotations

import json
import subprocess

from sendsprint.models.sprint import SprintItem
from sendsprint.prompt import PromptFanout

REPORT = json.dumps(
    {
        "task": "t",
        "provider": "deepseek",
        "model": "deepseek-chat",
        "requested": 600,
        "completed": 600,
        "failed": 0,
        "elapsed_s": 1.2,
        "usage": {"cost_usd": 0.045},
        "results": [
            {"agent_id": 0, "ok": True, "text": "edge case A"},
            {"agent_id": 1, "ok": True, "text": "edge case B"},
        ],
    }
)


def _runner(returncode: int = 0, stdout: str = "", stderr: str = ""):
    calls: list[list[str]] = []

    def run(argv, **kwargs):  # noqa: ANN001
        calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    run.calls = calls  # type: ignore[attr-defined]
    return run


def _kernel(tmp_path):
    kernel = tmp_path / "subagent_runtime.py"
    kernel.write_text("# stub")
    return kernel


def test_skipped_when_kernel_missing(tmp_path):
    fan = PromptFanout(kernel_path=tmp_path / "nope.py", runner=_runner())
    res = fan.run("brainstorm", subagents=10)
    assert res.status == "skipped"
    assert res.requested == 10


def test_run_ok_parses_report(tmp_path):
    runner = _runner(returncode=0, stdout=REPORT)
    fan = PromptFanout(kernel_path=_kernel(tmp_path), runner=runner, subagents=600)
    res = fan.run("brainstorm")
    assert res.status == "ok"
    assert res.requested == 600 and res.completed == 600
    assert res.cost_usd == 0.045
    assert res.samples[:2] == ["edge case A", "edge case B"]
    argv = runner.calls[0]
    assert "--subagents" in argv and "600" in argv
    assert "--json" in argv
    assert "--dry-run" not in argv


def test_run_failed_on_nonzero(tmp_path):
    fan = PromptFanout(kernel_path=_kernel(tmp_path), runner=_runner(returncode=2, stderr="boom"))
    res = fan.run("x", subagents=5)
    assert res.status == "failed"
    assert "2" in res.message


def test_run_failed_on_bad_json(tmp_path):
    runner = _runner(returncode=0, stdout="not json")
    fan = PromptFanout(kernel_path=_kernel(tmp_path), runner=runner)
    res = fan.run("x", subagents=5)
    assert res.status == "failed"


def test_dry_run_adds_flag(tmp_path):
    runner = _runner(returncode=0, stdout=REPORT)
    fan = PromptFanout(kernel_path=_kernel(tmp_path), runner=runner, dry_run=True)
    fan.run("x", subagents=3)
    assert "--dry-run" in runner.calls[0]


def test_timeout_is_failed(tmp_path):
    def boom(*a, **k):  # noqa: ANN002, ANN003
        raise subprocess.TimeoutExpired(cmd="python", timeout=1)

    fan = PromptFanout(kernel_path=_kernel(tmp_path), runner=boom)
    res = fan.run("x", subagents=5)
    assert res.status == "failed"
    assert "timed out" in res.message


def test_brainstorm_builds_task_from_item(tmp_path):
    captured: dict[str, list[str]] = {}

    def run(argv, **kwargs):  # noqa: ANN001
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, 0, REPORT, "")

    fan = PromptFanout(kernel_path=_kernel(tmp_path), runner=run)
    item = SprintItem(
        id="1",
        key="ABC-1",
        type="Task",
        title="Add login",
        status="open",
        acceptance_criteria="works under load",
    )
    res = fan.brainstorm(item, subagents=4)
    assert res.status == "ok"
    task_arg = captured["argv"][captured["argv"].index("--task") + 1]
    assert "Add login" in task_arg
    assert "works under load" in task_arg
