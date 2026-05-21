"""Tests for sendsprint/workspace/loader.py."""

import json
from pathlib import Path

import pytest
import yaml

from sendsprint.models.workspace import ProjectConfig, RepoConfig, WorkspaceConfig
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
        "pr_reviewers": ["reviewer@example.com"],
        "required_pr_reviewers": ["lead@example.com"],
        "user_email": "dev@example.com",
        "watch": {
            "enabled": True,
            "provider": "azuredevops",
            "interval_minutes": 15,
            "scope": "assigned_to_me",
            "allowed_states": ["New"],
            "ignored_states": ["Removed", "Closed"],
            "work_item_types": ["Task"],
            "iteration_path": "Team\\Sprint 29",
            "max_tasks_per_cycle": 1,
        },
        "code_generation": {"enabled": True, "provider": "openai", "max_usd": 2.5},
        "deploy": {"enabled": True, "url": "https://deploy.example/hook"},
        "playwright_auto_flows": {
            "enabled": True,
            "frontend_base_url": "http://127.0.0.1:5173",
            "dev_server_command": "npm run dev -- --host 127.0.0.1",
            "timeout_seconds": 45,
        },
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
    assert ws.pr_reviewers == ["reviewer@example.com"]
    assert ws.required_pr_reviewers == ["lead@example.com"]
    assert ws.user_email == "dev@example.com"
    assert ws.watch.enabled is True
    assert ws.watch.provider == "azuredevops"
    assert ws.watch.iteration_path == "Team\\Sprint 29"
    assert ws.watch.max_tasks_per_cycle == 1
    assert ws.code_generation.enabled is True
    assert ws.code_generation.provider == "openai"
    assert ws.code_generation.max_usd == 2.5
    assert ws.deploy.enabled is True
    assert ws.deploy.url == "https://deploy.example/hook"
    assert ws.playwright_auto_flows.enabled is True
    assert ws.playwright_auto_flows.frontend_base_url == "http://127.0.0.1:5173"
    assert ws.playwright_auto_flows.dev_server_command == "npm run dev -- --host 127.0.0.1"
    assert ws.playwright_auto_flows.timeout_seconds == 45
    assert ws.projects == []
    assert ws.repos[0].project is None
    assert ws.repos[0].capabilities == []
    assert ws.repos[0].validation_commands == []


def test_workspace_model_flattens_project_repos(tmp_path: Path) -> None:
    root = tmp_path / "projects"
    root.mkdir()

    ws = WorkspaceConfig(
        root_path=str(root),
        projects=[
            ProjectConfig(
                key="payments",
                name="Payments",
                repos=[RepoConfig(name="api", path="apps/payments-api", role="api")],
            )
        ],
    )

    assert len(ws.projects) == 1
    assert len(ws.repos) == 1
    assert ws.projects[0].repos[0].project == "payments"
    assert ws.repos[0].project == "payments"


def test_load_workspace_single_project_config(tmp_path: Path) -> None:
    root = tmp_path / "portfolio"
    root.mkdir()

    cfg = {
        "name": "payments-portfolio",
        "root_path": str(root),
        "portfolio": {
            "name": "Commerce",
            "owners": ["platform-office"],
            "capabilities": ["checkout"],
        },
        "projects": [
            {
                "key": "payments",
                "name": "Payments",
                "owners": ["team-payments"],
                "capabilities": ["payment-processing"],
                "components": ["checkout", "ledger"],
                "routing_hints": {"labels": ["payments"], "areas": ["Checkout"]},
                "branch_pattern": "feature/payments/{number}-{title}",
                "commit_pattern": "feat(payments): {title}",
                "validation_commands": ["pytest tests/payments -q"],
                "repos": [
                    {
                        "name": "payments-api",
                        "path": "apps/payments-api",
                        "role": "api",
                        "tech": "python",
                        "capabilities": ["capture", "refund"],
                        "components": ["api", "worker"],
                        "owners": ["api-owner@example.com"],
                        "routing_hints": {
                            "labels": ["scope:back"],
                            "paths": ["apps/payments-api/**"],
                        },
                        "frontend": {
                            "base_url": "http://127.0.0.1:5173",
                            "dev_server_command": "npm run dev -- --host 127.0.0.1",
                            "flow_inventory": "auto",
                            "generate_route_smokes": True,
                            "screenshot_evidence": True,
                            "timeout_seconds": 60,
                            "max_routes": 25,
                        },
                        "branch_pattern": "feature/pay-api/{number}-{title}",
                        "commit_pattern": "fix(payments-api): {title}",
                        "validation_commands": ["ruff check sendsprint", "pytest tests -q"],
                    }
                ],
            }
        ],
    }
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text(yaml.dump(cfg), encoding="utf-8")

    ws = load_workspace(ws_file)

    assert ws.portfolio is not None
    assert ws.portfolio.name == "Commerce"
    assert ws.portfolio.owners == ["platform-office"]
    assert ws.projects[0].key == "payments"
    assert ws.projects[0].capabilities == ["payment-processing"]
    assert ws.projects[0].validation_commands == ["pytest tests/payments -q"]
    assert len(ws.repos) == 1

    repo = ws.repos[0]
    assert repo.project == "payments"
    assert repo.capabilities == ["capture", "refund"]
    assert repo.components == ["api", "worker"]
    assert repo.owners == ["api-owner@example.com"]
    assert repo.routing_hints == {
        "labels": ["scope:back"],
        "paths": ["apps/payments-api/**"],
    }
    assert repo.frontend.base_url == "http://127.0.0.1:5173"
    assert repo.frontend.dev_server_command == "npm run dev -- --host 127.0.0.1"
    assert repo.frontend.flow_inventory == "auto"
    assert repo.frontend.generate_route_smokes is True
    assert repo.frontend.screenshot_evidence is True
    assert repo.frontend.timeout_seconds == 60
    assert repo.frontend.max_routes == 25
    assert repo.branch_pattern == "feature/pay-api/{number}-{title}"
    assert repo.commit_pattern == "fix(payments-api): {title}"
    assert repo.validation_commands == ["ruff check sendsprint", "pytest tests -q"]


def test_load_workspace_multi_project_config_preserves_flat_repos(tmp_path: Path) -> None:
    root = tmp_path / "portfolio"
    root.mkdir()

    cfg = {
        "name": "multi-project",
        "root_path": str(root),
        "repos": [
            {
                "name": "shared-lib",
                "path": "packages/shared-lib",
                "role": "lib",
                "project": "platform",
            }
        ],
        "projects": [
            {
                "key": "checkout",
                "name": "Checkout",
                "repos": [
                    {
                        "name": "checkout-api",
                        "path": "services/checkout-api",
                        "role": "api",
                    }
                ],
            },
            {
                "name": "Backoffice",
                "repos": [
                    {
                        "name": "admin-web",
                        "path": "apps/admin-web",
                        "role": "front",
                        "project": "admin",
                    }
                ],
            },
        ],
    }
    ws_file = tmp_path / "workspace.yaml"
    ws_file.write_text(yaml.dump(cfg), encoding="utf-8")

    ws = load_workspace(ws_file)

    assert [project.name for project in ws.projects] == ["Checkout", "Backoffice"]
    assert [(repo.name, repo.project) for repo in ws.repos] == [
        ("shared-lib", "platform"),
        ("checkout-api", "checkout"),
        ("admin-web", "admin"),
    ]


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
    assert ws.branch_name_template == "feature/{number}-{title}"
    assert ws.playwright_auto_flows.enabled is True
    assert ws.playwright_auto_flows.frontend_base_url is None
    assert ws.playwright_auto_flows.dev_server_command is None
    assert ws.playwright_auto_flows.timeout_seconds == 30
    assert ws.playwright_auto_flows.max_routes == 50


def test_load_workspace_resolves_relative_root_path_from_workspace_file(tmp_path: Path) -> None:
    repo_root = tmp_path / "repos"
    repo_root.mkdir()
    ws_dir = tmp_path / "config"
    ws_dir.mkdir()
    ws_file = ws_dir / "workspace.yaml"
    ws_file.write_text("root_path: ../repos\nrepos: []\n", encoding="utf-8")

    ws = load_workspace(ws_file)

    assert Path(ws.root_path) == repo_root.resolve()


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
