"""Tests for sendsprint/agents/ modules."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from sendsprint.agents.dev import DevAgent
from sendsprint.agents.lint_runner import LintRunner
from sendsprint.agents.pr_reviewer import PrReviewer
from sendsprint.agents.security_reviewer import SecurityReviewer
from sendsprint.agents.test_runner import TestRunner
from sendsprint.agents.worktree import WorktreeError, WorktreeManager
from sendsprint.tech import TechFingerprint

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_fp(
    tmp_path: Path,
    *,
    techs: list[str] | None = None,
    pms: list[str] | None = None,
) -> TechFingerprint:
    return TechFingerprint(
        repo_path=str(tmp_path),
        techs=techs or [],
        roles=["other"],
        package_managers=pms or [],
    )


def init_git(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=str(path), capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "--allow-empty", "-m", "init"],
        cwd=str(path),
        capture_output=True,
        check=True,
        env={
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@test.com",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@test.com",
            "HOME": str(path),
            "PATH": "/usr/bin:/bin:/usr/local/bin",
        },
    )


# ---------------------------------------------------------------------------
# WorktreeManager
# ---------------------------------------------------------------------------


class TestWorktreeManager:
    def test_init_raises_on_non_git_dir(self, tmp_path: Path) -> None:
        with pytest.raises(WorktreeError, match="not a git repo"):
            WorktreeManager(tmp_path)

    def test_init_succeeds_on_git_repo(self, tmp_path: Path) -> None:
        init_git(tmp_path)
        wm = WorktreeManager(tmp_path)
        assert wm.repo == tmp_path.resolve()

    def test_list_worktrees_includes_main(self, tmp_path: Path) -> None:
        init_git(tmp_path)
        wm = WorktreeManager(tmp_path)
        worktrees = wm.list_worktrees()
        assert len(worktrees) >= 1
        assert any(str(tmp_path.resolve()) in wt for wt in worktrees)

    def test_current_branch_returns_string(self, tmp_path: Path) -> None:
        init_git(tmp_path)
        wm = WorktreeManager(tmp_path)
        branch = wm.current_branch()
        assert isinstance(branch, str)
        assert len(branch) > 0

    def test_worktree_dir_sanitizes_branch_slashes(self, tmp_path: Path) -> None:
        init_git(tmp_path)
        wm = WorktreeManager(tmp_path)
        path = wm.worktree_dir("feature/42-add-login")
        assert path.name == f"{tmp_path.name}-wt-feature-42-add-login"


# ---------------------------------------------------------------------------
# DevAgent
# ---------------------------------------------------------------------------


class TestDevAgent:
    def test_init_stores_repo_and_fingerprint(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path)
        agent = DevAgent(tmp_path, fp)
        assert agent.repo == tmp_path.resolve()
        assert agent.fp is fp

    def test_install_skipped_when_no_package_managers(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path, pms=[])
        agent = DevAgent(tmp_path, fp)
        report = agent.install()
        assert report.status == "skipped"
        assert "no package manager" in (report.message or "")

    def test_build_skipped_for_unknown_tech(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path, techs=["cobol"])
        agent = DevAgent(tmp_path, fp)
        report = agent.build()
        assert report.status == "skipped"

    def test_build_skipped_when_no_techs(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path, techs=[])
        agent = DevAgent(tmp_path, fp)
        report = agent.build()
        assert report.status == "skipped"

    def test_build_failed_when_custom_command_binary_missing(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path)
        agent = DevAgent(tmp_path, fp)
        report = agent.build(custom_command="__nonexistent_binary_xyz__ --flag")
        assert report.status == "failed"
        assert "__nonexistent_binary_xyz__" in (report.message or "")

    # --- Bun (TASK-001) ---

    def test_dev_agent_bun_install_command(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AC-3: `bun install` is invoked for bun fingerprint."""
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        fp = make_fp(tmp_path, techs=["bun"], pms=["bun"])
        agent = DevAgent(tmp_path, fp)
        report = agent.install()
        assert report.status == "ok"
        assert captured["cmd"] == ["bun", "install"]

    def test_dev_agent_bun_build_command(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AC-3: `bun run build` is invoked when build script is present."""
        captured: dict[str, list[str]] = {}
        (tmp_path / "package.json").write_text(json.dumps({"scripts": {"build": "tsc"}}))

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="ok", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        fp = make_fp(tmp_path, techs=["bun"], pms=["bun"])
        agent = DevAgent(tmp_path, fp)
        report = agent.build()
        assert report.status == "ok"
        assert captured["cmd"] == ["bun", "run", "build"]

    def test_dev_agent_bun_build_skipped_no_script(self, tmp_path: Path) -> None:
        """AC-3: when package.json has no build script, build is skipped."""
        (tmp_path / "package.json").write_text(json.dumps({"scripts": {"dev": "bun run dev"}}))
        fp = make_fp(tmp_path, techs=["bun"], pms=["bun"])
        agent = DevAgent(tmp_path, fp)
        report = agent.build()
        assert report.status == "skipped"
        assert "no build script" in (report.message or "")

    def test_dev_agent_bun_install_skipped_no_binary(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AC-6: bun binary absent → status='skipped', message='bun not installed'."""

        def raise_fnf(cmd, **kwargs):
            raise FileNotFoundError(2, "No such file or directory: 'bun'")

        monkeypatch.setattr(subprocess, "run", raise_fnf)
        fp = make_fp(tmp_path, techs=["bun"], pms=["bun"])
        agent = DevAgent(tmp_path, fp)
        report = agent.install()
        assert report.status == "skipped"
        assert "bun not installed" in (report.message or "")

    def test_dev_agent_install_and_build_returns_two_reports(self, tmp_path: Path) -> None:
        """install_and_build returns both step reports."""
        fp = make_fp(tmp_path, techs=["bun"], pms=["bun"])
        agent = DevAgent(tmp_path, fp)
        reports = agent.install_and_build()
        assert len(reports) == 2
        assert reports[0].name == "install-deps"
        assert reports[1].name == "build"

    # --- Deno (Sprint 3) ---

    def test_dev_agent_deno_install_command(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        fp = make_fp(tmp_path, techs=["deno"], pms=["deno"])
        agent = DevAgent(tmp_path, fp)
        report = agent.install()
        assert report.status == "ok"
        assert captured["cmd"][0:2] == ["deno", "cache"]

    def test_dev_agent_deno_skipped_no_binary(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def raise_fnf(cmd, **kwargs):
            raise FileNotFoundError(2, "No such file or directory: 'deno'")

        monkeypatch.setattr(subprocess, "run", raise_fnf)
        fp = make_fp(tmp_path, techs=["deno"], pms=["deno"])
        agent = DevAgent(tmp_path, fp)
        report = agent.install()
        assert report.status == "skipped"
        assert "deno not installed" in (report.message or "")


# ---------------------------------------------------------------------------
# TestRunner
# ---------------------------------------------------------------------------


class TestTestRunner:
    def test_run_unit_skipped_for_unknown_tech(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path, techs=["cobol"])
        runner = TestRunner(tmp_path, fp)
        report = runner.run_unit()
        assert report.status == "skipped"

    def test_run_unit_skipped_when_no_techs(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path, techs=[])
        runner = TestRunner(tmp_path, fp)
        report = runner.run_unit()
        assert report.status == "skipped"

    def test_run_e2e_skipped_for_unknown_tech(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path, techs=["cobol"])
        runner = TestRunner(tmp_path, fp)
        report = runner.run_e2e()
        assert report.status == "skipped"

    def test_run_e2e_skipped_when_no_techs(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path, techs=[])
        runner = TestRunner(tmp_path, fp)
        report = runner.run_e2e()
        assert report.status == "skipped"

    def test_run_all_returns_two_reports(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path, techs=[])
        runner = TestRunner(tmp_path, fp)
        reports = runner.run_all()
        assert len(reports) == 2

    def test_evidence_dir_created_on_init(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path)
        runner = TestRunner(tmp_path, fp)
        assert runner.evidence_dir.exists()
        assert runner.evidence_dir.is_dir()

    def test_run_unit_does_not_reuse_stale_screenshot_evidence(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict[str, list[str]] = {}
        evidence_dir = tmp_path / "sendsprint-evidence"
        evidence_dir.mkdir()
        (evidence_dir / "old.png").write_bytes(b"png")

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        fp = make_fp(tmp_path, techs=["python"])
        runner = TestRunner(tmp_path, fp)
        report = runner.run_unit()

        assert report.status == "ok"
        assert captured["cmd"][:1] == ["pytest"]
        assert not any(
            evidence.kind == "screenshot" and evidence.path == "sendsprint-evidence/old.png"
            for evidence in report.evidence
        )

    # --- Bun / Deno (TASK-001 + Sprint 3 #12) ---

    def test_test_runner_bun_command(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """AC-5: `bun test` is invoked for bun fingerprint."""
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(
                args=cmd, returncode=0, stdout='{"tests":[]}', stderr=""
            )

        monkeypatch.setattr(subprocess, "run", fake_run)
        fp = make_fp(tmp_path, techs=["bun"])
        runner = TestRunner(tmp_path, fp)
        report = runner.run_unit()
        assert report.status == "ok"
        assert captured["cmd"] == ["bun", "test"]

    def test_test_runner_bun_skipped_no_binary(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AC-6: bun absent → status='skipped', message='bun not installed'."""

        def raise_fnf(cmd, **kwargs):
            raise FileNotFoundError(2, "No such file or directory: 'bun'")

        monkeypatch.setattr(subprocess, "run", raise_fnf)
        fp = make_fp(tmp_path, techs=["bun"])
        runner = TestRunner(tmp_path, fp)
        report = runner.run_unit()
        assert report.status == "skipped"
        assert "bun not installed" in (report.message or "")

    def test_test_runner_deno_command(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        fp = make_fp(tmp_path, techs=["deno"])
        runner = TestRunner(tmp_path, fp)
        report = runner.run_unit()
        assert report.status == "ok"
        assert captured["cmd"][0:2] == ["deno", "test"]


# ---------------------------------------------------------------------------
# SecurityReviewer
# ---------------------------------------------------------------------------


class TestSecurityReviewer:
    def test_scan_empty_repo_ok_zero_findings(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path)
        reviewer = SecurityReviewer(tmp_path, fp)
        report = reviewer.scan()
        assert report.status == "ok"
        assert len(report.findings) == 0

    def test_scan_detects_hardcoded_secret(self, tmp_path: Path) -> None:
        (tmp_path / "config.py").write_text('API_KEY = "sk-1234567890abcdefghij"')
        fp = make_fp(tmp_path)
        reviewer = SecurityReviewer(tmp_path, fp)
        report = reviewer.scan()
        rules = [f.rule for f in report.findings]
        assert any(r in ("hardcoded-api-key", "openai-key") for r in rules)

    def test_scan_flags_env_not_gitignored(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("SECRET=super_secret_value\n")
        fp = make_fp(tmp_path)
        reviewer = SecurityReviewer(tmp_path, fp)
        report = reviewer.scan()
        rules = [f.rule for f in report.findings]
        assert "env-not-gitignored" in rules

    def test_scan_no_finding_for_env_example(self, tmp_path: Path) -> None:
        (tmp_path / ".env.example").write_text("SECRET=changeme\n")
        fp = make_fp(tmp_path)
        reviewer = SecurityReviewer(tmp_path, fp)
        report = reviewer.scan()
        files = [f.file for f in report.findings]
        assert ".env.example" not in files

    def test_scan_env_gitignored_no_finding(self, tmp_path: Path) -> None:
        (tmp_path / ".env").write_text("SECRET=super_secret_value\n")
        (tmp_path / ".gitignore").write_text(".env\n")
        fp = make_fp(tmp_path)
        reviewer = SecurityReviewer(tmp_path, fp)
        report = reviewer.scan()
        rules = [f.rule for f in report.findings]
        assert "env-not-gitignored" not in rules

    def test_scan_detects_slack_webhook(self, tmp_path: Path) -> None:
        (tmp_path / "notify.py").write_text(
            'WEBHOOK = "https://hooks.slack.com/services/T0000/B0000/xxxx1234abcd"'
        )
        fp = make_fp(tmp_path)
        reviewer = SecurityReviewer(tmp_path, fp)
        report = reviewer.scan()
        rules = [f.rule for f in report.findings]
        assert "slack-webhook" in rules

    def test_scan_detects_jwt_token(self, tmp_path: Path) -> None:
        jwt = (
            "eyJhbGciOiJIUzI1NiJ9."
            "eyJzdWIiOiIxMjM0NTY3ODkwIn0."
            "dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        )
        (tmp_path / "auth.py").write_text(f'TOKEN = "{jwt}"')
        fp = make_fp(tmp_path)
        reviewer = SecurityReviewer(tmp_path, fp)
        report = reviewer.scan()
        rules = [f.rule for f in report.findings]
        assert "jwt-in-source" in rules


# ---------------------------------------------------------------------------
# LintRunner
# ---------------------------------------------------------------------------


class TestLintRunner:
    def test_skip_unknown_tech(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path)
        runner = LintRunner(tmp_path, fp)
        report = runner.run()
        assert report.status == "skipped"

    def test_skip_when_linter_not_installed(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path, techs=["python"])
        runner = LintRunner(tmp_path, fp)
        report = runner.run()
        # ruff may or may not be installed; either skipped or ok/failed
        assert report.status in ("skipped", "ok", "failed")

    def test_custom_command_not_found(self, tmp_path: Path) -> None:
        fp = make_fp(tmp_path)
        runner = LintRunner(tmp_path, fp, custom_command="nonexistent_linter_xyz --check")
        report = runner.run()
        assert report.status == "skipped"
        assert "not installed" in (report.message or "")

    # --- Bun / Deno (TASK-001 + Sprint 3 #12) ---

    def test_lint_runner_bun_eslint_command(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """AC-4: `bun x eslint .` is invoked for bun fingerprint."""
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        fp = make_fp(tmp_path, techs=["bun"])
        runner = LintRunner(tmp_path, fp)
        report = runner.run()
        assert report.status == "ok"
        assert captured["cmd"] == ["bun", "x", "eslint", "."]

    def test_lint_runner_bun_skipped_no_binary(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        def raise_fnf(cmd, **kwargs):
            raise FileNotFoundError(2, "No such file or directory: 'bun'")

        monkeypatch.setattr(subprocess, "run", raise_fnf)
        fp = make_fp(tmp_path, techs=["bun"])
        runner = LintRunner(tmp_path, fp)
        report = runner.run()
        assert report.status == "skipped"
        assert "bun not installed" in (report.message or "")

    def test_lint_runner_deno_command(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        captured: dict[str, list[str]] = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)
        fp = make_fp(tmp_path, techs=["deno"])
        runner = LintRunner(tmp_path, fp)
        report = runner.run()
        assert report.status == "ok"
        assert captured["cmd"] == ["deno", "lint"]


# ---------------------------------------------------------------------------
# PrReviewer
# ---------------------------------------------------------------------------


class TestPrReviewer:
    def _reviewer(self, tmp_path: Path) -> PrReviewer:
        return PrReviewer(tmp_path)

    def test_static_checks_todo_marker(self, tmp_path: Path) -> None:
        reviewer = self._reviewer(tmp_path)
        diff = "+const x = 1; // TODO: fix this later\n"
        issues = reviewer._static_checks(diff)
        rules = [i["rule"] for i in issues]
        assert "todo-marker" in rules

    def test_static_checks_debug_statement(self, tmp_path: Path) -> None:
        reviewer = self._reviewer(tmp_path)
        diff = "+console.log('debug value', value);\n"
        issues = reviewer._static_checks(diff)
        rules = [i["rule"] for i in issues]
        assert "debug-statement" in rules

    def test_static_checks_long_line(self, tmp_path: Path) -> None:
        reviewer = self._reviewer(tmp_path)
        long_code = "x" * 201
        diff = f"+{long_code}\n"
        issues = reviewer._static_checks(diff)
        rules = [i["rule"] for i in issues]
        assert "long-line" in rules

    def test_static_checks_clean_diff_no_issues(self, tmp_path: Path) -> None:
        reviewer = self._reviewer(tmp_path)
        diff = "+const value = compute(a, b);\n+return value;\n"
        issues = reviewer._static_checks(diff)
        assert issues == []

    def test_static_checks_ignores_removed_lines(self, tmp_path: Path) -> None:
        reviewer = self._reviewer(tmp_path)
        diff = "-const x = 1; // TODO: old code\n"
        issues = reviewer._static_checks(diff)
        assert issues == []

    def test_static_checks_merge_conflict_marker(self, tmp_path: Path) -> None:
        reviewer = self._reviewer(tmp_path)
        diff = "+<<<<<<< HEAD\n+const x = 1;\n+=======\n+const x = 2;\n+>>>>>>> feature\n"
        issues = reviewer._static_checks(diff)
        rules = [i["rule"] for i in issues]
        assert rules.count("merge-conflict") == 3

    def test_static_checks_debugger_statement(self, tmp_path: Path) -> None:
        reviewer = self._reviewer(tmp_path)
        diff = "+debugger\n"
        issues = reviewer._static_checks(diff)
        rules = [i["rule"] for i in issues]
        assert "debug-statement" in rules

    def test_static_checks_python_debug(self, tmp_path: Path) -> None:
        reviewer = self._reviewer(tmp_path)
        diff = "+import pdb\n+breakpoint()\n"
        issues = reviewer._static_checks(diff)
        rules = [i["rule"] for i in issues]
        assert rules.count("debug-statement") == 2

    def test_static_checks_logger_not_flagged(self, tmp_path: Path) -> None:
        reviewer = self._reviewer(tmp_path)
        diff = "+logger.debug('value', value);\n"
        issues = reviewer._static_checks(diff)
        rules = [i["rule"] for i in issues]
        assert "debug-statement" not in rules
