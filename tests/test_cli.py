"""CLI wiring tests for opt-in codegen/deploy overrides."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from sendsprint.cli import app
from sendsprint.models.sprint import Sprint
from sendsprint.models.workspace import WorkspaceConfig

runner = CliRunner()


def test_run_passes_codegen_and_deploy_overrides(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeJiraOperator:
        def __init__(self, *args, **kwargs) -> None:
            del args, kwargs

        def current_user(self) -> dict[str, str]:
            return {"emailAddress": "dev@example.com", "accountId": "acct-1"}

    class FakeFlow:
        def __init__(
            self,
            operator,
            *,
            workspace,
            scope,
            code_generation,
            deploy,
            autonomy_policy,
        ) -> None:
            del operator, scope
            captured["workspace"] = workspace
            captured["code_generation"] = code_generation
            captured["deploy"] = deploy
            captured["autonomy_policy"] = autonomy_policy

        def run(self, **kwargs):
            del kwargs
            return SimpleNamespace(
                sprint=Sprint(id="42", name="Sprint 42", source="jira", transport="api", items=[]),
                delivery_plan=None,
                architecture=None,
                run_report=None,
                notes=[],
            )

    monkeypatch.setattr("sendsprint.cli.JiraOperator", FakeJiraOperator)
    monkeypatch.setattr("sendsprint.cli.SprintFlow", FakeFlow)
    monkeypatch.setattr("sendsprint.cli.build_scope", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        "sendsprint.cli.load_workspace",
        lambda path: WorkspaceConfig(root_path=str(tmp_path), name="ws"),
    )

    result = runner.invoke(
        app,
        [
            "run",
            "jira",
            "42",
            "--workspace",
            str(tmp_path / "workspace.yaml"),
            "--repo",
            str(tmp_path),
            "--llm-codegen",
            "--llm-provider",
            "openai",
            "--llm-model",
            "gpt-4.1",
            "--llm-max-usd",
            "2.5",
            "--llm-max-tokens",
            "9000",
            "--deploy",
            "--deploy-url",
            "https://deploy.example.com/hook",
            "--deploy-final-status",
            "Released",
        ],
    )

    assert result.exit_code == 0, result.output
    code_generation = captured["code_generation"]
    deploy = captured["deploy"]
    assert code_generation.enabled is True
    assert code_generation.provider == "openai"
    assert code_generation.model == "gpt-4.1"
    assert code_generation.max_usd == 2.5
    assert code_generation.max_tokens == 9000
    assert deploy.enabled is True
    assert deploy.url == "https://deploy.example.com/hook"
    assert deploy.final_status == "Released"
    assert captured["autonomy_policy"].level == "deploy-callback"
