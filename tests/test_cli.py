from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

from sendsprint.cli import app
from sendsprint.profile import Profile, RuntimeProfile


def test_web_command_boots_localhost_control_plane(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_ensure(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            api_url="http://127.0.0.1:8765",
            ui_url="http://localhost:8081",
            api_started=True,
            ui_started=True,
            browser_opened=False,
            warnings=[],
        )

    monkeypatch.setattr("sendsprint.cli.ensure_localhost_control_plane", fake_ensure)

    result = CliRunner().invoke(app, ["web", "--no-open-browser"])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1
    assert calls[0]["open_browser"] is False


def test_watch_command_boots_dashboard_by_default(monkeypatch, tmp_path: Path) -> None:
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text("name: ws\nroot_path: .\n", encoding="utf-8")
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    def fake_bootstrap(*args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(
            doctor=None,
            dashboard=None,
            mapper_updated=False,
            python_fallback_active=False,
            notes=[],
        )

    class FakeWatcher:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def run_once(self, *, dry_run: bool, force: bool):
            del dry_run, force
            return SimpleNamespace(
                provider="azuredevops",
                sprint_id="sprint-29",
                eligible=[],
                processed=[],
                skipped=[],
                blocked=[],
                summary=lambda: "checked=0 eligible=0 processed=0 skipped=0 blocked=0",
            )

    monkeypatch.setattr("sendsprint.cli.run_operational_bootstrap", fake_bootstrap)
    monkeypatch.setattr("sendsprint.cli.Watcher", FakeWatcher)

    result = CliRunner().invoke(app, ["watch", "--workspace", str(ws_file), "--dry-run"])

    assert result.exit_code == 0, result.output
    assert len(calls) == 1


def test_watch_command_can_skip_dashboard(monkeypatch, tmp_path: Path) -> None:
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text("name: ws\nroot_path: .\n", encoding="utf-8")
    calls: list[dict[str, object]] = []

    class FakeWatcher:
        def __init__(self, **kwargs) -> None:
            del kwargs

        def run_once(self, *, dry_run: bool, force: bool):
            del dry_run, force
            return SimpleNamespace(
                provider="azuredevops",
                sprint_id="sprint-29",
                eligible=[],
                processed=[],
                skipped=[],
                blocked=[],
                summary=lambda: "checked=0 eligible=0 processed=0 skipped=0 blocked=0",
            )

    monkeypatch.setattr(
        "sendsprint.cli.ensure_localhost_control_plane", lambda **kwargs: calls.append(kwargs)
    )
    monkeypatch.setattr(
        "sendsprint.cli.run_operational_bootstrap",
        lambda *args, **kwargs: SimpleNamespace(
            doctor=None,
            dashboard=None,
            mapper_updated=False,
            python_fallback_active=False,
            notes=[],
        ),
    )
    monkeypatch.setattr("sendsprint.cli.Watcher", FakeWatcher)

    result = CliRunner().invoke(
        app,
        ["watch", "--workspace", str(ws_file), "--dry-run", "--no-dashboard"],
    )

    assert result.exit_code == 0, result.output
    assert calls == []


def test_watch_command_full_mode_forces_max_autonomy(monkeypatch, tmp_path: Path) -> None:
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text("name: ws\nroot_path: .\n", encoding="utf-8")
    init_calls: list[dict[str, object]] = []

    class FakeWatcher:
        def __init__(self, **kwargs) -> None:
            init_calls.append(kwargs)

        def run_once(self, *, dry_run: bool, force: bool):
            del dry_run, force
            return SimpleNamespace(
                provider="azuredevops",
                sprint_id="sprint-29",
                eligible=[],
                processed=[],
                skipped=[],
                blocked=[],
                summary=lambda: "checked=0 eligible=0 processed=0 skipped=0 blocked=0",
            )

    monkeypatch.setattr(
        "sendsprint.cli.ensure_localhost_control_plane",
        lambda **kwargs: SimpleNamespace(
            api_url="http://127.0.0.1:8765",
            ui_url="http://localhost:8081",
            api_started=False,
            ui_started=False,
            browser_opened=False,
            warnings=[],
        ),
    )
    monkeypatch.setattr(
        "sendsprint.cli.run_operational_bootstrap",
        lambda *args, **kwargs: SimpleNamespace(
            doctor=None,
            dashboard=None,
            mapper_updated=False,
            python_fallback_active=False,
            notes=[],
        ),
    )
    monkeypatch.setattr("sendsprint.cli.Watcher", FakeWatcher)

    result = CliRunner().invoke(
        app,
        ["watch", "--workspace", str(ws_file), "--dry-run", "--full-mode"],
    )

    assert result.exit_code == 0, result.output
    assert init_calls[0]["autonomy_policy"].level == "deploy-callback"


def test_full_command_wraps_watch_with_max_autonomy(monkeypatch, tmp_path: Path) -> None:
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text("name: ws\nroot_path: .\n", encoding="utf-8")
    calls: list[dict[str, object]] = []

    def fake_watch_cmd(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("sendsprint.cli.watch_cmd", fake_watch_cmd)

    result = CliRunner().invoke(app, ["full", "--workspace", str(ws_file), "--once"])

    assert result.exit_code == 0, result.output
    assert calls[0]["autonomy"] == "deploy-callback"
    assert calls[0]["full_mode"] is True
    assert calls[0]["once"] is True


def test_watch_uses_profile_default_workspace(monkeypatch, tmp_path: Path) -> None:
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text("name: ws\nroot_path: .\n", encoding="utf-8")
    monkeypatch.setattr(
        "sendsprint.cli.profile_mod.load",
        lambda: Profile(default_workspace=str(ws_file)),
    )
    monkeypatch.setattr(
        "sendsprint.cli.run_operational_bootstrap",
        lambda *args, **kwargs: SimpleNamespace(
            doctor=None,
            dashboard=None,
            mapper_updated=False,
            python_fallback_active=False,
            notes=[],
        ),
    )

    init_calls: list[dict[str, object]] = []

    class FakeWatcher:
        def __init__(self, **kwargs) -> None:
            init_calls.append(kwargs)

        def run_once(self, *, dry_run: bool, force: bool):
            del dry_run, force
            return SimpleNamespace(
                provider="azuredevops",
                sprint_id="sprint-29",
                eligible=[],
                processed=[],
                skipped=[],
                blocked=[],
                summary=lambda: "checked=0 eligible=0 processed=0 skipped=0 blocked=0",
            )

    monkeypatch.setattr("sendsprint.cli.Watcher", FakeWatcher)

    result = CliRunner().invoke(app, ["watch", "--dry-run"])

    assert result.exit_code == 0, result.output
    assert len(init_calls) == 1


def test_sprint_auto_full_mode_uses_default_workspace(monkeypatch, tmp_path: Path) -> None:
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text("name: ws\nroot_path: .\n", encoding="utf-8")
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "sendsprint.cli.profile_mod.load",
        lambda: Profile(
            default_workspace=str(ws_file),
            runtime=RuntimeProfile(auto_full_mode=True, watch_interval_minutes=7),
        ),
    )

    def fake_full_cmd(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr("sendsprint.cli.full_cmd", fake_full_cmd)

    result = CliRunner().invoke(app, ["sprint"])

    assert result.exit_code == 0, result.output
    assert calls[0]["workspace_file"] == ws_file.resolve()
    assert calls[0]["interval"] == "7"


def test_configure_defaults_sets_profile(monkeypatch, tmp_path: Path) -> None:
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text("name: ws\nroot_path: .\n", encoding="utf-8")
    updates: list[dict[str, object]] = []
    monkeypatch.setattr(
        "sendsprint.cli.profile_mod.update", lambda **kwargs: updates.append(kwargs)
    )

    result = CliRunner().invoke(
        app,
        [
            "configure-defaults",
            "--repo",
            str(tmp_path),
            "--workspace",
            str(ws_file),
            "--watch-interval",
            "20",
        ],
    )

    assert result.exit_code == 0, result.output
    assert updates[0]["default_repo_path"] == str(tmp_path.resolve())
    assert updates[0]["default_workspace"] == str(ws_file.resolve())
    assert updates[0]["runtime.auto_full_mode"] is True
