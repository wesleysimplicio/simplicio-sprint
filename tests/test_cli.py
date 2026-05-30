"""CLI smoke tests for command wiring."""

from __future__ import annotations

from typer.testing import CliRunner

from sendsprint import cli as cli_mod
from sendsprint.models import RunReport


def test_run_passes_validate_only_to_flow(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    flow = _FakeFlow(captured)
    _patch_cli(monkeypatch, flow)

    result = CliRunner().invoke(
        cli_mod.app,
        ["run", "jira", "42", "--repo", str(tmp_path), "--no-update", "--validate-only"],
    )

    assert result.exit_code == 0
    assert captured["validate_plan"] is True
    assert captured["validate_only"] is True
    assert captured["read_kwargs"] == {"sprint_id": "42"}


def test_run_passes_no_validate_to_flow(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    flow = _FakeFlow(captured)
    _patch_cli(monkeypatch, flow)

    result = CliRunner().invoke(
        cli_mod.app,
        ["run", "jira", "42", "--repo", str(tmp_path), "--no-update", "--no-validate"],
    )

    assert result.exit_code == 0
    assert captured["validate_plan"] is False
    assert captured["validate_only"] is False


def test_run_passes_no_bootstrap_mapper_to_flow(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    flow = _FakeFlow(captured)
    _patch_cli(monkeypatch, flow)

    result = CliRunner().invoke(
        cli_mod.app,
        ["run", "jira", "42", "--repo", str(tmp_path), "--no-update", "--no-bootstrap-mapper"],
    )

    assert result.exit_code == 0
    assert captured["bootstrap_mapper"] is False


def test_run_passes_no_retro_to_flow(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    flow = _FakeFlow(captured)
    _patch_cli(monkeypatch, flow)

    result = CliRunner().invoke(
        cli_mod.app,
        ["run", "jira", "42", "--repo", str(tmp_path), "--no-update", "--no-retro"],
    )

    assert result.exit_code == 0
    assert captured["retro"] is False


def test_run_passes_resume_to_flow(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    flow = _FakeFlow(captured)
    _patch_cli(monkeypatch, flow)

    result = CliRunner().invoke(
        cli_mod.app,
        ["run", "jira", "42", "--repo", str(tmp_path), "--no-update", "--resume"],
    )

    assert result.exit_code == 0
    assert captured["resume"] is True


def test_run_cancelled_report_exits_130(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    flow = _FakeFlow(captured, report=RunReport(workspace="repo", cancelled=True, summary="stop"))
    _patch_cli(monkeypatch, flow)

    result = CliRunner().invoke(
        cli_mod.app,
        ["run", "jira", "42", "--repo", str(tmp_path), "--no-update"],
    )

    assert result.exit_code == 130


class _FakeFlow:
    scope = None

    def __init__(self, captured: dict[str, object], report: RunReport | None = None) -> None:
        self.captured = captured
        self.report = report or RunReport(
            workspace="repo", sprint_name="Sprint", sprint_id="42", summary="ok"
        )

    def run(
        self,
        *,
        validate_plan: bool = True,
        validate_only: bool = False,
        bootstrap_mapper: bool = True,
        retro: bool = True,
        resume: bool = False,
        **read_kwargs: object,
    ) -> RunReport:
        self.captured["validate_plan"] = validate_plan
        self.captured["validate_only"] = validate_only
        self.captured["bootstrap_mapper"] = bootstrap_mapper
        self.captured["retro"] = retro
        self.captured["resume"] = resume
        self.captured["read_kwargs"] = read_kwargs
        return self.report


def _patch_cli(monkeypatch, flow: _FakeFlow) -> None:
    monkeypatch.setattr(cli_mod, "_startup", lambda skip: None)
    monkeypatch.setattr(cli_mod, "_build_operator", lambda source: object())
    monkeypatch.setattr(cli_mod, "_build_flow", lambda *args, **kwargs: flow)
    monkeypatch.setattr(cli_mod, "_archive_report", lambda report: None)
