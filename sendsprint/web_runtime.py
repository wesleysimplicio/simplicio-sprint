"""Background localhost runtime helpers for the SendSprint dashboard."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import time
import webbrowser
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

from sendsprint import profile

DEFAULT_API_HOST = "127.0.0.1"
DEFAULT_API_PORT = 8765
DEFAULT_UI_PORT = 8081
DEFAULT_UI_URL = f"http://localhost:{DEFAULT_UI_PORT}"


@dataclass(slots=True)
class LocalhostRuntimeStatus:
    api_url: str
    ui_url: str
    api_running: bool = False
    ui_running: bool = False
    api_started: bool = False
    ui_started: bool = False
    browser_opened: bool = False
    warnings: list[str] = field(default_factory=list)


def ensure_localhost_control_plane(
    *,
    api_host: str = DEFAULT_API_HOST,
    api_port: int = DEFAULT_API_PORT,
    ui_port: int = DEFAULT_UI_PORT,
    open_browser: bool = True,
    api_reload: bool = False,
) -> LocalhostRuntimeStatus:
    """Ensure the local API/UI pair is available for browser monitoring."""
    status = LocalhostRuntimeStatus(
        api_url=f"http://{api_host}:{api_port}",
        ui_url=f"http://localhost:{ui_port}",
    )
    if _is_listening(api_host, api_port):
        status.api_running = True
    else:
        try:
            _spawn_background_process(
                _api_command(api_host=api_host, api_port=api_port, api_reload=api_reload),
                cwd=_project_root(),
                env={
                    "SENDSPRINT_API_HOST": api_host,
                    "SENDSPRINT_API_PORT": str(api_port),
                },
            )
        except OSError as exc:
            status.warnings.append(f"could not start API backend: {exc}")
        else:
            status.api_started = _wait_until_listening(api_host, api_port, timeout_s=8.0)
            status.api_running = status.api_started
            if not status.api_started:
                status.warnings.append(
                    f"API backend did not become ready on {status.api_url}; check Python/api deps"
                )

    if _is_listening("127.0.0.1", ui_port) or _is_listening("localhost", ui_port):
        status.ui_running = True
    else:
        web_root = _project_root() / "web"
        try:
            web_command = _web_command(web_root=web_root, ui_port=ui_port)
        except RuntimeError as exc:
            status.warnings.append(str(exc))
        else:
            try:
                _spawn_background_process(
                    web_command,
                    cwd=web_root,
                    env={
                        "BROWSER": "none",
                        "CI": "1",
                        "EXPO_NO_TELEMETRY": "1",
                    },
                )
            except OSError as exc:
                status.warnings.append(f"could not start web UI: {exc}")
            else:
                status.ui_started = _wait_until_listening(
                    "127.0.0.1", ui_port, timeout_s=20.0
                ) or _wait_until_listening("localhost", ui_port, timeout_s=2.0)
                status.ui_running = status.ui_started
                if not status.ui_started:
                    status.warnings.append(
                        f"web UI did not become ready on {status.ui_url}; "
                        "check Node/npm dependencies"
                    )

    if open_browser and status.ui_running and _should_open_browser_today(status.ui_url):
        try:
            status.browser_opened = webbrowser.open(status.ui_url)
        except OSError as exc:
            status.warnings.append(f"could not open browser: {exc}")
        else:
            if status.browser_opened:
                _write_browser_state(status.ui_url)
    return status


def _api_command(*, api_host: str, api_port: int, api_reload: bool) -> list[str]:
    if api_reload:
        return [
            sys.executable,
            "-m",
            "uvicorn",
            "sendsprint.api.server:app",
            "--host",
            api_host,
            "--port",
            str(api_port),
            "--reload",
        ]
    return [sys.executable, "-m", "sendsprint.api"]


def _web_command(*, web_root: Path, ui_port: int) -> list[str]:
    package_json = web_root / "package.json"
    if not package_json.exists():
        raise RuntimeError(f"web UI package is missing at {package_json}")
    if not (web_root / "node_modules").exists():
        raise RuntimeError("web UI dependencies are missing; run `cd web && npm install` first")
    npm = _npm_executable()
    if not npm:
        raise RuntimeError("npm is not available on PATH; cannot start the web UI")
    return [npm, "run", "dev", "--", "--port", str(ui_port)]


def _npm_executable() -> str | None:
    candidates = ["npm.cmd", "npm"] if os.name == "nt" else ["npm"]
    for candidate in candidates:
        if shutil.which(candidate):
            return candidate
    return None


def _spawn_background_process(
    command: list[str], *, cwd: Path, env: dict[str, str] | None = None
) -> subprocess.Popen[str]:
    child_env = os.environ.copy()
    if env:
        child_env.update(env)
    if os.name == "nt":
        creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0
        )
        return subprocess.Popen(
            command,
            cwd=str(cwd),
            env=child_env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            creationflags=creationflags,
        )
    return subprocess.Popen(
        command,
        cwd=str(cwd),
        env=child_env,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )


def _is_listening(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.25):
            return True
    except OSError:
        return False


def _wait_until_listening(host: str, port: int, *, timeout_s: float) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        if _is_listening(host, port):
            return True
        time.sleep(0.2)
    return _is_listening(host, port)


def _state_path() -> Path:
    return profile.CONFIG_DIR / "dashboard-state.json"


def _should_open_browser_today(ui_url: str) -> bool:
    state = _read_browser_state()
    return state.get("opened_on") != date.today().isoformat() or state.get("ui_url") != ui_url


def _read_browser_state() -> dict[str, str]:
    path = _state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_browser_state(ui_url: str) -> None:
    path = _state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"opened_on": date.today().isoformat(), "ui_url": ui_url}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent
