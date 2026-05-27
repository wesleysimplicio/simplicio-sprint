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


def test_tuple_runtime_uses_prompt_fanout_adapter(tmp_path):
    prompt_repo = tmp_path / "simplicio-prompt"
    examples = prompt_repo / "examples/python"
    examples.mkdir(parents=True)
    (examples / "prompt_fanout.py").write_text(
        """
class Receipt:
    def __init__(self, depth, branching):
        self.depth = depth
        self.branching = branching
        self.virtual_agents = branching ** depth
        self.receipt_id = "receipt-123"


class PromptFanout:
    def __init__(self, repo, authority="simplicio", policy=None, space=None):
        self.repo = repo
        self.receipt = None
        self.recorded = []

    def spawn_task(self, goal, *, mapper_context=None, lane="analysis", depth=2, branching=8, compression_threshold=None):
        self.mapper_context = mapper_context
        self.receipt = Receipt(depth, branching)
        return {"goal": goal}, self.receipt

    def record_tokens(self, lane, *, prompt_tokens=0, completion_tokens=0, cost_usd=0.0, reason="fanout"):
        self.recorded.append((lane, prompt_tokens, completion_tokens, cost_usd, reason))

    def snapshot(self):
        return {
            "active_agents": 1,
            "virtual_agents": self.receipt.virtual_agents,
            "total_agents": self.receipt.virtual_agents + 1,
            "token_usage": {
                "total_cost_usd": 0.0123,
                "lanes": {
                    "analysis": {
                        "prompt_tokens": 12,
                        "completion_tokens": 3,
                        "cost_usd": 0.0123,
                    }
                },
            },
        }
""",
        encoding="utf-8",
    )

    fan = PromptFanout(
        prompt_repo=prompt_repo,
        repo="owner/repo",
        mapper_context={"relevant_files": ["src/auth/login.py"]},
        subagents=64,
        dry_run=True,
    )
    res = fan.run("Implement login")
    assert res.status == "ok"
    assert res.runtime == "tuple"
    assert res.requested == 64
    assert res.completed == 64
    assert res.cost_usd == 0.0123
    assert res.token_usage["lanes"]["analysis"]["prompt_tokens"] == 12
    assert any("batch_spawn" in sample for sample in res.samples)
