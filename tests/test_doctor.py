"""Tests for sendsprint doctor readiness checks."""

from __future__ import annotations

import subprocess
from pathlib import Path

from sendsprint.doctor import run_doctor


def test_doctor_reports_missing_repo(tmp_path: Path) -> None:
    report = run_doctor(tmp_path / "missing")
    assert report.ok is False
    assert report.checks[0].name == "repo-exists"


def test_doctor_matches_template_and_git_state(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "pyproject.toml").write_text("[project]\ndependencies=['fastapi']\n")

    def fake_which(command: str) -> str | None:
        return f"/usr/bin/{command}"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return subprocess.CompletedProcess(cmd, 0, "origin/main\n", "")
        if cmd[:3] == ["git", "rev-list", "--left-right"]:
            return subprocess.CompletedProcess(cmd, 0, "0 0\n", "")
        if cmd[:3] == ["gh", "auth", "status"]:
            return subprocess.CompletedProcess(cmd, 0, "ok", "")
        if cmd[:2] == ["npx", "playwright"]:
            return subprocess.CompletedProcess(cmd, 0, "Version 1.0", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("sendsprint.doctor.shutil.which", fake_which)
    report = run_doctor(tmp_path, runner=fake_run)
    assert report.ok is True
    assert report.template is not None
    assert report.template.name == "python"


def test_doctor_checks_web_node_toolchain(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    web = tmp_path / "web"
    web.mkdir()
    (web / "package.json").write_text('{"name":"web"}', encoding="utf-8")

    def fake_which(command: str) -> str | None:
        return f"/usr/bin/{command}"

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["git", "status"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:3] == ["git", "rev-parse", "--abbrev-ref"]:
            return subprocess.CompletedProcess(cmd, 0, "origin/main\n", "")
        if cmd[:3] == ["git", "rev-list", "--left-right"]:
            return subprocess.CompletedProcess(cmd, 0, "0 0\n", "")
        if cmd[:3] == ["gh", "auth", "status"]:
            return subprocess.CompletedProcess(cmd, 0, "ok", "")
        if cmd[:2] == ["npx", "playwright"]:
            return subprocess.CompletedProcess(cmd, 0, "Version 1.0", "")
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("sendsprint.doctor.shutil.which", fake_which)

    report = run_doctor(tmp_path, runner=fake_run)

    names = {check.name: check for check in report.checks}
    assert names["node"].status == "ok"
    assert names["npm"].status == "ok"
    assert names["npx"].status == "ok"
    assert names["web-node-modules"].status == "warn"
