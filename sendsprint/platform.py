"""Cross-platform helpers for Windows / macOS / Linux compatibility.

Provides detection, path handling, and shell-command wrapping so the rest of
the codebase can stay platform-agnostic.

Issue: #110
"""

from __future__ import annotations

import os
import platform
import shutil
import sys
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class PlatformInfo(BaseModel):
    """Snapshot of the current runtime platform."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    os_name: str = Field(description="Normalised OS: 'windows', 'darwin', 'linux', or raw value.")
    shell: str = Field(description="Default shell binary name: 'pwsh', 'cmd', 'bash', 'zsh', etc.")
    path_separator: str = Field(description="OS path separator (';' on Windows, ':' elsewhere).")
    dir_separator: str = Field(
        description="Directory separator ('\\\\' on Windows, '/' elsewhere)."
    )
    venv_activate: str = Field(description="Relative path to venv activate script.")
    python_cmd: str = Field(description="'python' on Windows, 'python3' elsewhere (if found).")
    line_ending: str = Field(description="'\\r\\n' on Windows, '\\n' elsewhere.")


# ---------------------------------------------------------------------------
# Detect
# ---------------------------------------------------------------------------


def detect_platform() -> PlatformInfo:
    """Return a ``PlatformInfo`` describing the current runtime."""
    raw = platform.system().lower()

    if raw == "windows":
        os_name = "windows"
        shell = "pwsh" if shutil.which("pwsh") else "cmd"
        path_sep = ";"
        dir_sep = "\\"
        venv = r".venv\Scripts\activate"
        py = "python"
        eol = "\r\n"
    else:
        os_name = raw if raw in ("darwin", "linux") else raw
        shell_env = os.environ.get("SHELL", "")
        shell = Path(shell_env).name if shell_env else "bash"
        path_sep = ":"
        dir_sep = "/"
        venv = ".venv/bin/activate"
        py = "python3" if shutil.which("python3") else "python"
        eol = "\n"

    return PlatformInfo(
        os_name=os_name,
        shell=shell,
        path_separator=path_sep,
        dir_separator=dir_sep,
        venv_activate=venv,
        python_cmd=py,
        line_ending=eol,
    )


# ---------------------------------------------------------------------------
# Convenience helpers
# ---------------------------------------------------------------------------


def is_windows() -> bool:
    """``True`` when running on Windows (or when ``SENDSPRINT_FORCE_WIN`` is set for testing)."""
    if os.environ.get("SENDSPRINT_FORCE_WIN"):
        return True
    return sys.platform == "win32"


def is_unix() -> bool:
    """``True`` when running on macOS, Linux, or another POSIX-like platform."""
    return not is_windows()


def normalize_path(p: str | Path) -> Path:
    """Return a ``pathlib.Path`` that uses the correct separators for the
    current OS.  Forward slashes in *p* are preserved on Unix but converted
    on Windows.
    """
    return Path(os.path.normpath(str(p)))


def vendor_bin(tool: str) -> str:
    """Return the platform-correct path to a PHP ``vendor/bin`` tool.

    On Windows, Composer installs ``.bat`` wrappers under ``vendor\\bin``.
    """
    if is_windows():
        return f"vendor\\bin\\{tool}.bat"
    return f"vendor/bin/{tool}"


def shell_command(cmd: str | list[str]) -> list[str]:
    """Wrap *cmd* for execution via ``subprocess.run``.

    On Windows, commands are prefixed with ``cmd /c`` (or ``pwsh -Command``
    when PowerShell is the default shell) so that ``.bat``/``.cmd`` scripts
    are resolved correctly.

    On Unix, commands are returned as-is (list form).
    """
    parts = cmd.split() if isinstance(cmd, str) else list(cmd)

    if not parts:
        return parts

    if is_windows():
        if shutil.which("pwsh"):
            return ["pwsh", "-NoProfile", "-Command", " ".join(parts)]
        return ["cmd", "/c", *parts]
    return parts


def venv_activate_cmd() -> str:
    """Return the shell snippet to activate a ``.venv`` on the current platform."""
    if is_windows():
        return r".venv\Scripts\Activate.ps1"
    return "source .venv/bin/activate"
