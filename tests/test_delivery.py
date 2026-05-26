"""Tests for the delivery layer: git ops, evidence, pull requests."""

from __future__ import annotations

import subprocess

import httpx
import pytest

from sendsprint.delivery.evidence import EvidenceCollector
from sendsprint.delivery.git_ops import GitError, GitOps
from sendsprint.delivery.pr import PullRequestManager
from sendsprint.models.reports import TestEvidence


# -- git_ops ----------------------------------------------------------------


def _git_runner(script):
    """script: dict mapping a command-suffix to (returncode, stdout)."""
    calls: list[list[str]] = []

    def run(argv, **kwargs):  # noqa: ANN001
        calls.append(argv)
        key = argv[1] if len(argv) > 1 else ""
        rc, out = script.get(key, (0, ""))
        if rc != 0:
            raise subprocess.CalledProcessError(rc, argv, output=out, stderr="err")
        return subprocess.CompletedProcess(argv, rc, out, "")

    run.calls = calls  # type: ignore[attr-defined]
    return run


def test_commit_all_skips_when_no_changes():
    git = GitOps(".", runner=_git_runner({"status": (0, "")}))
    assert git.commit_all("msg") is False


def test_commit_all_commits_when_dirty():
    runner = _git_runner({"status": (0, " M file.py")})
    git = GitOps(".", runner=runner)
    assert git.commit_all("feat: x") is True
    assert ["git", "add", "-A"] in runner.calls


def test_push_retries_then_raises():
    sleeps: list[float] = []
    runner = _git_runner({"push": (1, ""), "rev-parse": (0, "branch\n")})
    git = GitOps(".", runner=runner, sleep=sleeps.append)
    with pytest.raises(GitError):
        git.push("feature/x", retries=3)
    assert len(sleeps) == 2  # backoff between 3 attempts


def test_push_succeeds_first_try():
    runner = _git_runner({"push": (0, "")})
    git = GitOps(".", runner=runner)
    git.push("feature/x")
    assert any(c[:2] == ["git", "push"] for c in runner.calls)


# -- evidence ---------------------------------------------------------------


def test_collect_tests_no_command_skips(tmp_path):
    ev = EvidenceCollector(tmp_path, item_key="ABC-1").collect_tests(None)
    assert ev.passed is True
    assert "skipped" in (ev.message or "")


def test_collect_tests_runs_and_records(tmp_path):
    def runner(cmd, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(cmd, 0, "3 passed", "")

    ev = EvidenceCollector(tmp_path, item_key="ABC-1", runner=runner).collect_tests("pytest -q")
    assert ev.passed is True
    assert ev.path is not None
    assert (tmp_path / ".sendsprint/evidence/ABC-1/tests.log").exists()


def test_collect_tests_failure(tmp_path):
    def runner(cmd, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(cmd, 1, "", "1 failed")

    ev = EvidenceCollector(tmp_path, item_key="ABC-1", runner=runner).collect_tests("pytest")
    assert ev.passed is False


def test_capture_screenshot_with_injected_fn(tmp_path):
    def fake_shot(url, out):  # noqa: ANN001
        from pathlib import Path

        Path(out).write_bytes(b"PNG")
        return True

    ev = EvidenceCollector(tmp_path, item_key="ABC-1").capture_screenshot(
        "http://localhost:4200", screenshot_fn=fake_shot
    )
    assert ev is not None and ev.passed is True
    assert ev.kind == "screenshot"


def test_capture_screenshot_unavailable(tmp_path):
    ev = EvidenceCollector(tmp_path, item_key="ABC-1").capture_screenshot(
        "http://x", screenshot_fn=lambda u, o: False
    )
    assert ev is not None and ev.passed is False


# -- pr ---------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeClient:
    def __init__(self, payload):
        self._payload = payload
        self.posted: list[tuple[str, dict]] = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None):  # noqa: ANN001
        self.posted.append((url, json))
        return _FakeResponse(self._payload)


def test_create_github_pr_draft():
    fake = _FakeClient({"number": 7, "html_url": "https://github.com/o/r/pull/7"})
    pr = PullRequestManager("github", "o/r", token="t", client_factory=lambda: fake)
    info = pr.create_pr(title="ABC-1: x", body="body", head="feature/x", base="develop", draft=True)
    assert info.number == 7
    assert info.state == "draft"
    assert fake.posted[0][1]["draft"] is True


def test_render_evidence_embeds_screenshot():
    pr = PullRequestManager("github", "owner/repo", token="t")
    evidence = [
        TestEvidence(kind="unit", title="pytest", passed=True, message="exit 0"),
        TestEvidence(
            kind="screenshot",
            title="http://x",
            passed=True,
            path="/wt/.sendsprint/evidence/ABC-1/screen.png",
        ),
    ]
    body = pr._render_evidence("feature/x", evidence, ["execute"])
    assert "![http://x](" in body
    assert "raw.githubusercontent.com/owner/repo/feature/x/.sendsprint/evidence/ABC-1/screen.png" in body
