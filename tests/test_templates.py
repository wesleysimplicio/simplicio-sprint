"""Tests for stack validation templates."""

from __future__ import annotations

import json
from pathlib import Path

from sendsprint.tech import TechFingerprint
from sendsprint.templates import catalog, select_validation_template


def test_catalog_includes_requested_frontend_and_node_templates() -> None:
    names = {item.name for item in catalog()}
    assert {"angular", "react", "vue", "nodejs-api"} <= names


def test_selects_react_template() -> None:
    fp = TechFingerprint(repo_path="/tmp/app", techs=["react"], roles=["front"])
    template = select_validation_template(fp)
    assert template.name == "react"
    assert "npx playwright test" in template.commands()


def test_monorepo_template_wins_from_workspace_marker(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"workspaces": ["apps/*"]}))
    fp = TechFingerprint(repo_path=str(tmp_path), techs=["node"], roles=["back"])
    template = select_validation_template(fp, tmp_path)
    assert template.name == "monorepo"
