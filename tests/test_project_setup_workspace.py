from __future__ import annotations

import json
from pathlib import Path

import pytest

from sendsprint.api.project_setup_workspace import materialize_workspace_from_project_setup


def test_materialize_workspace_from_project_setup_writes_local_workspace(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    repo_path = tmp_path / "repo"
    repo_path.mkdir()

    workspace_path = materialize_workspace_from_project_setup(
        {
            "branchPattern": "feature/{item_key}",
            "commitPattern": "{type}: {summary}",
            "deployTargetBranch": "dev",
            "repositories": [
                {
                    "name": "web",
                    "repoPath": str(repo_path),
                    "role": "frontend",
                    "project": "Customer Portal",
                    "validationCommands": ["npm test"],
                }
            ]
        }
    )

    payload = json.loads(Path(workspace_path).read_text(encoding="utf-8"))
    assert payload["default_base_branch"] == "dev"
    assert payload["repos"][0]["role"] == "front"
    assert payload["repos"][0]["pr_target_branch"] == "dev"


def test_materialize_workspace_rejects_remote_urls(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ValueError, match="must point to a local path"):
        materialize_workspace_from_project_setup(
            {
                "repositories": [
                    {
                        "name": "api",
                        "repoPath": "https://github.com/org/repo",
                        "role": "backend",
                        "project": "Billing",
                    }
                ]
            }
        )
