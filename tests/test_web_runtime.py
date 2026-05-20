from __future__ import annotations

from pathlib import Path

from sendsprint import profile
from sendsprint.web_runtime import ensure_localhost_control_plane


def test_ensure_localhost_control_plane_starts_services_and_opens_browser_once(
    monkeypatch, tmp_path: Path
) -> None:
    profile.CONFIG_DIR = tmp_path / "config"
    web_root = tmp_path / "repo" / "web"
    web_root.mkdir(parents=True)
    (web_root / "package.json").write_text("{}", encoding="utf-8")
    (web_root / "node_modules").mkdir()
    monkeypatch.setattr("sendsprint.web_runtime._project_root", lambda: tmp_path / "repo")

    state = {"api": False, "ui": False}
    launches: list[list[str]] = []
    opened: list[str] = []

    def fake_is_listening(host: str, port: int) -> bool:
        if port == 8765:
            return state["api"]
        if port == 8081:
            return state["ui"]
        return False

    def fake_spawn(command: list[str], *, cwd: Path, env: dict[str, str] | None = None):
        del cwd, env
        launches.append(command)
        if "sendsprint.api" in command:
            state["api"] = True
        if "run" in command and "dev" in command:
            state["ui"] = True
        return object()

    monkeypatch.setattr("sendsprint.web_runtime._is_listening", fake_is_listening)
    monkeypatch.setattr("sendsprint.web_runtime._spawn_background_process", fake_spawn)
    monkeypatch.setattr(
        "sendsprint.web_runtime.webbrowser.open", lambda url: opened.append(url) or True
    )
    monkeypatch.setattr("sendsprint.web_runtime._npm_executable", lambda: "npm")

    first = ensure_localhost_control_plane()
    second = ensure_localhost_control_plane()

    assert first.api_started is True
    assert first.ui_started is True
    assert first.browser_opened is True
    assert second.browser_opened is False
    assert opened == ["http://localhost:8081"]
    assert len(launches) == 2


def test_ensure_localhost_control_plane_warns_when_web_dependencies_missing(
    monkeypatch, tmp_path: Path
) -> None:
    profile.CONFIG_DIR = tmp_path / "config"
    web_root = tmp_path / "repo" / "web"
    web_root.mkdir(parents=True)
    (web_root / "package.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr("sendsprint.web_runtime._project_root", lambda: tmp_path / "repo")
    monkeypatch.setattr("sendsprint.web_runtime._is_listening", lambda host, port: port == 8765)

    status = ensure_localhost_control_plane(open_browser=False)

    assert status.api_running is True
    assert status.ui_running is False
    assert any("npm install" in warning for warning in status.warnings)
