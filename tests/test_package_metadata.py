import tomllib
from pathlib import Path

from sendsprint import __version__


def test_package_version_matches_release_metadata() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert project["version"] == "1.2.3"
    assert __version__ == project["version"]


def test_simplicio_ecosystem_dependencies_are_current() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]

    assert "simplicio-cli>=0.4.3" in project["dependencies"]
    assert "simplicio-mapper>=0.6.1" in project["dependencies"]
    assert "simplicio-prompt>=1.12.0" in project["dependencies"]
