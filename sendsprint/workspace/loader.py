"""Load a workspace.yaml (or .json) into a WorkspaceConfig."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..models.workspace import RepoConfig, WorkspaceConfig


def _read_text(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"workspace file not found: {path}")
    return path.read_text(encoding="utf-8")


def _parse(text: str, suffix: str) -> dict[str, Any]:
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - defensive
            raise ImportError(
                "pyyaml is required to parse YAML workspace files. "
                "Install with `pip install pyyaml`."
            ) from exc
        return yaml.safe_load(text) or {}
    if suffix == ".json":
        return json.loads(text)
    raise ValueError(f"unsupported workspace file extension: {suffix!r}")


def load_workspace(path: str | Path) -> WorkspaceConfig:
    """Load and validate a workspace config file."""
    p = Path(path).expanduser()
    raw = _parse(_read_text(p), p.suffix.lower())

    if "root_path" not in raw:
        raw["root_path"] = str(p.parent.resolve())
    else:
        configured_root = Path(str(raw["root_path"])).expanduser()
        if not configured_root.is_absolute():
            raw["root_path"] = str((p.parent / configured_root).resolve())

    repos_raw = raw.get("repos", []) or []
    repos = [r if isinstance(r, RepoConfig) else RepoConfig(**r) for r in repos_raw]
    raw["repos"] = repos

    ws = WorkspaceConfig(**raw)

    root = Path(ws.root_path).expanduser()
    if not root.exists():
        raise FileNotFoundError(f"workspace root_path does not exist: {root}")

    return ws


def resolve_repo_path(ws: WorkspaceConfig, repo: RepoConfig) -> Path:
    """Resolve a repo's absolute filesystem path within the workspace."""
    base = Path(ws.root_path).expanduser()
    p = Path(repo.path).expanduser()
    return p if p.is_absolute() else (base / p).resolve()


def new_project_dir(ws: WorkspaceConfig) -> Path:
    """Return the absolute path where new projects must be created."""
    base = Path(ws.root_path).expanduser()
    target = Path(ws.new_projects_dir).expanduser()
    return target if target.is_absolute() else (base / target).resolve()
