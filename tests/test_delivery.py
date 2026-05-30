"""Tests for the delivery layer: git ops, evidence, pull requests."""

from __future__ import annotations

import json
import subprocess

import pytest

from sendsprint.delivery.evidence import EvidenceCollector, select_evidence_commands
from sendsprint.delivery.git_ops import GitError, GitOps
from sendsprint.delivery.pr import PullRequestManager
from sendsprint.github_integration import ReviewFeedback, ReviewReader
from sendsprint.models.reports import TestEvidence
from sendsprint.tech import TechFingerprint, detect_tech

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


def test_collect_detected_node_vitest_runs_no_pytest(tmp_path):
    calls: list[str] = []

    def runner(cmd, **kwargs):  # noqa: ANN001
        calls.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    fp = TechFingerprint(repo_path=str(tmp_path), techs=["node", "vitest", "eslint"])
    evidence = EvidenceCollector(tmp_path, item_key="ABC-1", runner=runner).collect_detected(fp)

    assert calls == ["npx vitest run", "npx eslint ."]
    assert all(ev.passed for ev in evidence)
    assert not any("pytest" in cmd for cmd in calls)
    assert (tmp_path / ".sendsprint/evidence/ABC-1/tests-vitest.log").exists()
    assert (tmp_path / ".sendsprint/evidence/ABC-1/lint-eslint.log").exists()


def test_collect_detected_monorepo_runs_python_and_node_suites(tmp_path):
    calls: list[tuple[str, str]] = []

    def runner(cmd, **kwargs):  # noqa: ANN001
        calls.append((cmd, kwargs["cwd"]))
        return subprocess.CompletedProcess(cmd, 0, "ok", "")

    fp = TechFingerprint(
        repo_path=str(tmp_path),
        techs=["python", "vitest", "eslint"],
        tech_roots={"python": "backend", "vitest": "frontend", "eslint": "frontend"},
    )
    evidence = EvidenceCollector(tmp_path, item_key="ABC-1", runner=runner).collect_detected(fp)

    assert calls == [
        ("pytest -q", str(tmp_path / "backend")),
        ("ruff check", str(tmp_path / "backend")),
        ("npx vitest run", str(tmp_path / "frontend")),
        ("npx eslint .", str(tmp_path / "frontend")),
    ]
    assert [ev.kind for ev in evidence] == ["unit", "lint", "unit", "lint"]


def test_collect_detected_failure_marks_evidence_failed(tmp_path):
    def runner(cmd, **kwargs):  # noqa: ANN001
        return subprocess.CompletedProcess(cmd, 1, "", "failed")

    fp = TechFingerprint(repo_path=str(tmp_path), techs=["node", "jest"])
    evidence = EvidenceCollector(tmp_path, item_key="ABC-1", runner=runner).collect_detected(fp)

    assert [ev.title for ev in evidence] == ["jest", "eslint"]
    assert all(ev.passed is False for ev in evidence)
    assert all(ev.message == "exit 1" for ev in evidence)


def test_select_evidence_commands_nextjs_skips_unit_and_lints(tmp_path):
    fp = TechFingerprint(repo_path=str(tmp_path), techs=["nextjs"])

    commands = select_evidence_commands(fp)

    assert [(cmd.title, cmd.command) for cmd in commands] == [
        ("next test", None),
        ("next lint", "npx next lint"),
    ]


def test_detect_tech_finds_js_test_and_lint_tools(tmp_path):
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {"test": "vitest run", "lint": "eslint ."},
                "devDependencies": {"vitest": "^1.0.0", "eslint": "^9.0.0"},
            }
        ),
        encoding="utf-8",
    )

    fp = detect_tech(tmp_path)

    assert "node" in fp.techs
    assert "vitest" in fp.techs
    assert "eslint" in fp.techs


def test_detect_tech_finds_frontend_backend_monorepo(tmp_path):
    backend = tmp_path / "backend"
    backend.mkdir()
    backend.joinpath("pyproject.toml").write_text(
        """
[project]
dependencies = ["pytest", "ruff"]
""",
        encoding="utf-8",
    )
    frontend = tmp_path / "frontend"
    frontend.mkdir()
    frontend.joinpath("package.json").write_text(
        json.dumps(
            {
                "scripts": {"test": "vitest run", "lint": "eslint ."},
                "devDependencies": {"vitest": "^1.0.0", "eslint": "^9.0.0"},
            }
        ),
        encoding="utf-8",
    )

    fp = detect_tech(tmp_path)

    assert "python" in fp.techs
    assert "node" in fp.techs
    assert "vitest" in fp.techs
    assert "eslint" in fp.techs
    assert fp.tech_roots["python"] == "backend"
    assert fp.tech_roots["node"] == "frontend"
    assert fp.tech_roots["vitest"] == "frontend"
    assert fp.tech_roots["eslint"] == "frontend"


def test_detect_tech_finds_angular_and_js_config_markers(tmp_path):
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "angular.json").write_text("{}", encoding="utf-8")
    (tmp_path / "jest.config.js").write_text("export default {}", encoding="utf-8")
    (tmp_path / "eslint.config.js").write_text("export default []", encoding="utf-8")

    fp = detect_tech(tmp_path)

    assert "angular" in fp.techs
    assert "jest" in fp.techs
    assert "eslint" in fp.techs


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


def test_write_manifest_deduplicates_evidence_and_review_feedback(tmp_path):
    collector = EvidenceCollector(tmp_path, item_key="ABC-1")
    evidence = [
        TestEvidence(kind="unit", title="pytest", passed=True, path="/tmp/tests.log"),
        TestEvidence(kind="unit", title="pytest", passed=True, path="/tmp/tests.log"),
        TestEvidence(kind="screenshot", title="home", passed=True, path="/tmp/screen.png"),
    ]
    feedback = [
        ReviewFeedback(reviewer="ana", body="add a regression test", path="app.py", line=12),
        ReviewFeedback(reviewer="ana", body="add a regression test", path="app.py", line=12),
    ]
    manifest = collector.write_manifest(
        evidence, steps_completed=["revise", "evidence"], review_feedback=feedback
    )
    data = json.loads(manifest.read_text(encoding="utf-8"))
    assert data["item_key"] == "ABC-1"
    assert data["status"] == "passed"
    assert len(data["artifacts"]) == 2
    assert len(data["review_feedback"]) == 1
    assert data["steps_completed"] == ["revise", "evidence"]


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
    assert (
        "raw.githubusercontent.com/owner/repo/feature/x/.sendsprint/evidence/ABC-1/screen.png"
        in body
    )


def test_render_evidence_deduplicates_and_links_manifest():
    pr = PullRequestManager("github", "owner/repo", token="t")
    evidence = [
        TestEvidence(kind="unit", title="pytest", passed=True, message="exit 0"),
        TestEvidence(kind="unit", title="pytest", passed=True, message="exit 0"),
        TestEvidence(
            kind="log",
            title="evidence manifest",
            passed=True,
            path="/wt/.sendsprint/evidence/ABC-1/manifest.json",
        ),
    ]
    body = pr._render_evidence(
        "feature/x",
        evidence,
        ["execute"],
        review_feedback=[
            ReviewFeedback(reviewer="ana", body="add a regression test", path="app.py", line=12)
        ],
    )
    assert body.count("**unit**: pytest") == 1
    assert "Review feedback addressed" in body
    assert "[evidence manifest]" in body


class _ReviewClient:
    def get(self, url, params=None):  # noqa: ANN001
        if url.endswith("/reviews"):
            return _FakeResponse(
                [
                    {
                        "state": "CHANGES_REQUESTED",
                        "body": "Add a regression test",
                        "user": {"login": "ana"},
                    },
                    {
                        "state": "CHANGES_REQUESTED",
                        "body": "Add a regression test",
                        "user": {"login": "ana"},
                    },
                    {"state": "APPROVED", "body": "looks good", "user": {"login": "bob"}},
                ]
            )
        if url.endswith("/comments"):
            return _FakeResponse(
                [
                    {
                        "body": "rename the helper",
                        "path": "app.py",
                        "line": 12,
                        "user": {"login": "ana"},
                    },
                    {
                        "body": "rename the helper",
                        "path": "app.py",
                        "line": 12,
                        "user": {"login": "ana"},
                    },
                    {"body": "", "path": "app.py", "line": 13, "user": {"login": "ana"}},
                ]
            )
        raise AssertionError(url)


def test_review_reader_deduplicates_actionable_feedback():
    feedback = ReviewReader("owner/repo", client=_ReviewClient()).extract_actionable_feedback(7)
    assert [(f.reviewer, f.body, f.path, f.line, f.state) for f in feedback] == [
        ("ana", "Add a regression test", None, None, "CHANGES_REQUESTED"),
        ("ana", "rename the helper", "app.py", 12, "COMMENTED"),
    ]
