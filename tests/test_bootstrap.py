"""Tests for the tool updater (simplicio-cli / -prompt / -mapper)."""

from __future__ import annotations

import subprocess

from sendsprint.bootstrap import Updater
from sendsprint.profile import Profile, RuntimeProfile


def _runner(returncode: int = 0, stdout: str = "", stderr: str = ""):
    calls: list[list[str]] = []

    def run(argv, **kwargs):  # noqa: ANN001
        calls.append(argv)
        return subprocess.CompletedProcess(argv, returncode, stdout, stderr)

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_update_cli_ok(tmp_path):
    runner = _runner(returncode=0)
    res = Updater(runner=runner, cache=tmp_path).update_simplicio_cli()
    assert res.status == "ok"
    assert runner.calls[0][1:] == ["-m", "pip", "install", "-U", "simplicio-cli"]


def test_update_cli_failed(tmp_path):
    updater = Updater(runner=_runner(returncode=1, stderr="boom"), cache=tmp_path)
    res = updater.update_simplicio_cli()
    assert res.status == "failed"
    assert "boom" in res.detail


def test_prompt_clone_when_absent_sets_env(tmp_path, monkeypatch):
    monkeypatch.delenv("SIMPLICIO_PROMPT_KERNEL", raising=False)
    runner = _runner(returncode=0)
    res = Updater(runner=runner, cache=tmp_path).update_simplicio_prompt()
    assert res.status == "ok"
    assert "cloned" in res.detail
    # No existing .git -> clone path used.
    assert runner.calls[0][:2] == ["git", "clone"]
    # The kernel path is exported for PromptFanout discovery.
    import os

    assert os.environ["SIMPLICIO_PROMPT_KERNEL"].endswith("kernel/subagent_runtime.py")


def test_prompt_pull_when_present(tmp_path):
    dest = tmp_path / "simplicio-prompt"
    (dest / ".git").mkdir(parents=True)
    runner = _runner(returncode=0)
    res = Updater(runner=runner, cache=tmp_path).update_simplicio_prompt()
    assert res.status == "ok"
    assert runner.calls[0][:2] == ["git", "-C"]
    assert "pull" in runner.calls[0]


def test_update_all_aggregates(tmp_path):
    report = Updater(runner=_runner(returncode=0), cache=tmp_path).update_all()
    assert [r.name for r in report.results] == [
        "simplicio-cli",
        "simplicio-prompt",
        "simplicio-mapper",
    ]
    assert report.ok


def test_run_startup_respects_profile_flags(tmp_path):
    runner = _runner(returncode=0)
    updater = Updater(runner=runner, cache=tmp_path)
    profile = Profile(
        runtime=RuntimeProfile(
            verify_dependencies_on_start=False,
            update_simplicio_prompt_on_start=True,
            update_llm_project_mapper_on_start=False,
        )
    )
    report = updater.run_startup(profile)
    assert [r.name for r in report.results] == ["simplicio-prompt"]


def test_run_startup_all_off_is_empty(tmp_path):
    updater = Updater(runner=_runner(returncode=0), cache=tmp_path)
    profile = Profile(
        runtime=RuntimeProfile(
            verify_dependencies_on_start=False,
            update_simplicio_prompt_on_start=False,
            update_llm_project_mapper_on_start=False,
        )
    )
    assert updater.run_startup(profile).results == []


def test_verify_dependencies_reports_git_and_kernel(tmp_path, monkeypatch):
    monkeypatch.setenv("SIMPLICIO_PROMPT_KERNEL", str(tmp_path / "missing.py"))
    results = {r.name: r for r in Updater(cache=tmp_path).verify_dependencies()}
    assert "git" in results
    assert results["simplicio-prompt kernel"].status == "skipped"
