"""Materialize web project-setup state into a transient workspace file."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def materialize_workspace_from_project_setup(project_setup: dict[str, object]) -> str:
    """Write a deterministic workspace JSON derived from the web project setup."""
    repositories = project_setup.get("repositories")
    if not isinstance(repositories, list) or not repositories:
        raise ValueError("Configure at least one local repository before starting a run.")

    workspace = {
        "name": "web-session-workspace",
        "root_path": str(Path.cwd()),
        "default_base_branch": _default_target_branch(repositories),
        "repos": [_repo_to_workspace_repo(repo) for repo in repositories],
    }
    encoded = json.dumps(workspace, ensure_ascii=True, sort_keys=True)
    digest = hashlib.sha1(encoded.encode("utf-8")).hexdigest()[:12]
    target_dir = Path.cwd() / ".sendsprint" / "generated-workspaces"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"web-session-{digest}.json"
    target.write_text(encoded, encoding="utf-8")
    return str(target)


def _default_target_branch(repositories: list[object]) -> str:
    for repo in repositories:
        if isinstance(repo, dict):
            value = str(repo.get("deployTargetBranch") or "").strip()
            if value:
                return value
    return "dev"


def _repo_to_workspace_repo(raw: object) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("Invalid repository payload.")
    repo_path = str(raw.get("repoPath") or "").strip()
    if not repo_path:
        raise ValueError("Each repository needs a local repo path.")
    if _looks_remote(repo_path):
        repo_name = str(raw.get("name") or repo_path)
        raise ValueError(
            f"Repository '{repo_name}' must point to a local path, not a remote URL."
        )
    return {
        "name": str(raw.get("name") or "").strip() or Path(repo_path).name,
        "path": repo_path,
        "project": str(raw.get("project") or "").strip() or None,
        "role": _map_repo_role(str(raw.get("role") or "other")),
        "pr_target_branch": str(raw.get("deployTargetBranch") or "").strip() or "dev",
        "branch_pattern": str(raw.get("branchPattern") or "").strip() or None,
        "commit_pattern": str(raw.get("commitPattern") or "").strip() or None,
        "validation_commands": _string_list(raw.get("validationCommands")),
    }


def _map_repo_role(role: str) -> str:
    normalized = role.strip().lower()
    mapping = {
        "frontend": "front",
        "backend": "api",
        "fullstack": "other",
        "mobile": "mobile",
        "infra": "infra",
        "docs": "other",
        "shared": "lib",
        "other": "other",
    }
    return mapping.get(normalized, "other")


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _looks_remote(repo_path: str) -> bool:
    lowered = repo_path.lower()
    return lowered.startswith(("http://", "https://", "git@", "ssh://"))
