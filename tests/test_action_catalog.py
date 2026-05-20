import json

from typer.testing import CliRunner

from sendsprint.action_catalog import (
    find_action_playbook,
    list_action_playbooks,
    write_action_catalog,
)
from sendsprint.cli import app


def test_builtin_action_catalog_includes_software_and_marketing() -> None:
    playbooks = list_action_playbooks()
    keys = {item.key for item in playbooks}

    assert "software.pr-delivery" in keys
    assert "marketing.campaign-launch" in keys
    marketing = find_action_playbook("marketing.campaign-launch")
    assert marketing is not None
    assert marketing.validation.evidence_required
    assert marketing.approval_policy == "human-before-publish"


def test_action_catalog_loads_editable_json(tmp_path) -> None:
    path = write_action_catalog(tmp_path / "actions.json")

    loaded = list_action_playbooks(path)

    assert loaded[0].key == "software.pr-delivery"


def test_actions_cli_list_show_and_write_default(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    listed = runner.invoke(app, ["actions", "list", "--output", "actions.json"])
    assert listed.exit_code == 0, listed.output
    listed_data = json.loads((tmp_path / "actions.json").read_text(encoding="utf-8"))
    assert any(item["key"] == "marketing.campaign-launch" for item in listed_data)

    shown = runner.invoke(app, ["actions", "show", "software.pr-delivery"])
    assert shown.exit_code == 0, shown.output
    assert "duplicate-risk" in shown.output

    written = runner.invoke(app, ["actions", "write-default", "catalog.json"])
    assert written.exit_code == 0, written.output
    data = json.loads((tmp_path / "catalog.json").read_text(encoding="utf-8"))
    assert data[0]["key"] == "software.pr-delivery"
