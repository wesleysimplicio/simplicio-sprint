"""Tests for sendsprint.platform — cross-platform helpers (#110)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from sendsprint.platform import (
    PlatformInfo,
    detect_platform,
    is_unix,
    is_windows,
    normalize_path,
    shell_command,
    vendor_bin,
    venv_activate_cmd,
)

# ---------------------------------------------------------------------------
# detect_platform
# ---------------------------------------------------------------------------


class TestDetectPlatform:
    def test_returns_platform_info(self):
        info = detect_platform()
        assert isinstance(info, PlatformInfo)
        assert info.os_name in ("windows", "darwin", "linux") or isinstance(info.os_name, str)

    def test_fields_non_empty(self):
        info = detect_platform()
        assert info.shell
        assert info.path_separator in (";", ":")
        assert info.dir_separator in ("\\", "/")
        assert info.python_cmd in ("python", "python3")
        assert info.line_ending in ("\r\n", "\n")

    def test_frozen(self):
        info = detect_platform()
        with pytest.raises(ValueError):
            info.os_name = "fake"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# is_windows / is_unix
# ---------------------------------------------------------------------------


class TestIsWindows:
    def test_mutually_exclusive(self):
        assert is_windows() != is_unix()

    def test_force_win_env(self, monkeypatch):
        monkeypatch.setenv("SENDSPRINT_FORCE_WIN", "1")
        assert is_windows() is True
        assert is_unix() is False

    def test_unset_force_follows_sys(self, monkeypatch):
        monkeypatch.delenv("SENDSPRINT_FORCE_WIN", raising=False)
        expected = sys.platform == "win32"
        assert is_windows() is expected


# ---------------------------------------------------------------------------
# normalize_path
# ---------------------------------------------------------------------------


class TestNormalizePath:
    def test_returns_path(self):
        result = normalize_path("foo/bar")
        assert isinstance(result, Path)

    def test_collapses_double_sep(self):
        result = normalize_path("foo//bar")
        assert str(result) == os.path.normpath("foo//bar")

    def test_resolves_dot_segments(self):
        result = normalize_path("foo/./bar/../baz")
        assert str(result) == os.path.normpath("foo/./bar/../baz")


# ---------------------------------------------------------------------------
# vendor_bin
# ---------------------------------------------------------------------------


class TestVendorBin:
    def test_unix(self, monkeypatch):
        monkeypatch.delenv("SENDSPRINT_FORCE_WIN", raising=False)
        if sys.platform == "win32":
            pytest.skip("Unix-only test")
        assert vendor_bin("phpcs") == "vendor/bin/phpcs"
        assert vendor_bin("phpunit") == "vendor/bin/phpunit"

    def test_windows(self, monkeypatch):
        monkeypatch.setenv("SENDSPRINT_FORCE_WIN", "1")
        result = vendor_bin("phpcs")
        assert result == "vendor\\bin\\phpcs.bat"


# ---------------------------------------------------------------------------
# shell_command
# ---------------------------------------------------------------------------


class TestShellCommand:
    def test_string_split(self):
        result = shell_command("ruff check .")
        assert "ruff" in result
        assert "check" in result

    def test_list_passthrough_unix(self, monkeypatch):
        monkeypatch.delenv("SENDSPRINT_FORCE_WIN", raising=False)
        if sys.platform == "win32":
            pytest.skip("Unix-only test")
        cmd = ["pytest", "--tb=short"]
        assert shell_command(cmd) == cmd

    def test_empty(self):
        assert shell_command([]) == []
        assert shell_command("") == []

    def test_windows_wraps_cmd(self, monkeypatch):
        monkeypatch.setenv("SENDSPRINT_FORCE_WIN", "1")
        monkeypatch.setattr("shutil.which", lambda x: None)
        result = shell_command(["ruff", "check", "."])
        assert result[0] == "cmd"
        assert result[1] == "/c"
        assert "ruff" in result

    def test_windows_wraps_pwsh(self, monkeypatch):
        monkeypatch.setenv("SENDSPRINT_FORCE_WIN", "1")
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/pwsh" if x == "pwsh" else None)
        result = shell_command(["ruff", "check", "."])
        assert result[0] == "pwsh"
        assert "-Command" in result


# ---------------------------------------------------------------------------
# venv_activate_cmd
# ---------------------------------------------------------------------------


class TestVenvActivateCmd:
    def test_unix(self, monkeypatch):
        monkeypatch.delenv("SENDSPRINT_FORCE_WIN", raising=False)
        if sys.platform == "win32":
            pytest.skip("Unix-only test")
        assert "source" in venv_activate_cmd()
        assert "bin/activate" in venv_activate_cmd()

    def test_windows(self, monkeypatch):
        monkeypatch.setenv("SENDSPRINT_FORCE_WIN", "1")
        result = venv_activate_cmd()
        assert "Scripts" in result
        assert "Activate.ps1" in result
