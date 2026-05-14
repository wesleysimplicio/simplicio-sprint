"""Tests for sendsprint/workspace/loader.py."""

import json
from pathlib import Path

import pytest
import yaml

from sendsprint.models.workspace import RepoConfig, WorkspaceConfig
from sendsprint.workspace.loader import load_workspace, new_project_dir, resolve_repo_path

# ---------------------------------------------------------------------------
# load_workspace
# ---------------------------------------------------------------------------


def test_load_workspace_valid_yaml(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    root.mkdir()

    cfg = {
        "name": "my-ws",
        "root_path": str(root),
        "repos": [{"name": "api", "path": "api-repo", "role": "api"}],
        "pr_provider": "github",
    }
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text(yaml.dump(cfg), encoding="utf-8")

    ws = load_workspace(ws_file)

    assert ws.name == "my-ws"
    assert ws.root_path == str(root)
    assert len(ws.repos) == 1
    assert ws.repos[0].name == "api"
    assert ws.repos[0].role == "api"
    assert ws.pr_provider == "github"


def test_load_workspace_valid_json(tmp_path: Path) -> None:
    root = tmp_path / "src"
    root.mkdir()

    cfg = {
        "name": "json-ws",
        "root_path": str(root),
        "repos": [],
    }
    ws_file = tmp_path / "workspace.json"
    ws_file.write_text(json.dumps(cfg), encoding="utf-8")

    ws = load_workspace(ws_file)

    assert ws.name == "json-ws"
    assert ws.repos == []
    assert ws.default_base_branch == "develop"


def test_load_workspace_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        load_workspace(tmp_path / "does_not_exist.yaml")


def test_load_workspace_unsupported_extension_raises(tmp_path: Path) -> None:
    ws_file = tmp_path / "workspace.toml"
    ws_file.write_text("name = 'ws'", encoding="utf-8")

    with pytest.raises(ValueError, match="unsupported workspace file extension"):
        load_workspace(ws_file)


def test_load_workspace_nonexistent_root_path_raises(tmp_path: Path) -> None:
    cfg = {
        "name": "bad-root",
        "root_path": str(tmp_path / "ghost_dir"),
    }
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text(yaml.dump(cfg), encoding="utf-8")

    with pytest.raises(FileNotFoundError, match="root_path does not exist"):
        load_workspace(ws_file)


# ---------------------------------------------------------------------------
# resolve_repo_path
# ---------------------------------------------------------------------------


def test_resolve_repo_path_relative(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()

    ws = WorkspaceConfig(root_path=str(root))
    repo = RepoConfig(name="frontend", path="apps/frontend")

    result = resolve_repo_path(ws, repo)

    assert result == (root / "apps" / "frontend").resolve()


def test_resolve_repo_path_absolute(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()

    abs_path = tmp_path / "external" / "lib"
    ws = WorkspaceConfig(root_path=str(root))
    repo = RepoConfig(name="lib", path=str(abs_path))

    result = resolve_repo_path(ws, repo)

    assert result == abs_path


# ---------------------------------------------------------------------------
# new_project_dir
# ---------------------------------------------------------------------------


def test_new_project_dir_returns_correct_path(tmp_path: Path) -> None:
    root = tmp_path / "ws"
    root.mkdir()

    ws = WorkspaceConfig(root_path=str(root), new_projects_dir="Projetos/novos")

    result = new_project_dir(ws)

    assert result == (root / "Projetos" / "novos").resolve()
