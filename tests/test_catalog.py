"""Tests for the HAMT-backed agent capability catalog."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from sendsprint.agent_registry import (
    AgentCapability,
    AgentProvider,
    AgentRegistry,
    default_agent_registry,
)
from sendsprint.catalog import (
    BITS_PER_LEVEL,
    BRANCH,
    HASH_BITS,
    MAX_LEVELS,
    build_agent_catalog,
    find_entries,
    hash_yool,
    list_entries,
    load_catalog,
    lookup_yool,
    save_catalog,
)
from sendsprint.cli import app


def test_hamt_constants_match_spec() -> None:
    assert BITS_PER_LEVEL == 5
    assert BRANCH == 32
    assert MAX_LEVELS == 6
    assert HASH_BITS == 30


def test_hash_yool_is_stable_and_bounded() -> None:
    assert hash_yool("agent.codex.plan") == hash_yool("agent.codex.plan")
    assert 0 <= hash_yool("agent.x.y") < (1 << HASH_BITS)


def test_build_default_registry_includes_all_capabilities() -> None:
    registry = default_agent_registry()
    cat = build_agent_catalog(registry)
    entries = list_entries(cat)
    expected = sum(len(p.capabilities) for p in registry.providers)
    assert len(entries) == expected
    ids = {e.yool_id for e in entries}
    assert "agent.codex.plan" in ids
    assert "agent.hermes.implement" in ids
    assert "agent.openclaw.security-review" in ids


def test_lookup_hits_and_misses() -> None:
    cat = build_agent_catalog()
    hit = lookup_yool(cat, "agent.codex.plan")
    assert hit is not None
    assert hit.provider_key == "codex"
    assert hit.capability_key == "plan"
    assert lookup_yool(cat, "agent.does.not.exist") is None


def test_entries_carry_mandatory_guardrails() -> None:
    """Spec §11 — cpu_quota_pct + disk_quota_mb on every entry."""
    cat = build_agent_catalog()
    for entry in list_entries(cat):
        assert entry.cpu_quota_pct > 0
        assert entry.disk_quota_mb > 0
        assert entry.timeout_s > 0


def test_find_entries_is_case_insensitive_substring() -> None:
    cat = build_agent_catalog()
    hermes = find_entries(cat, "HERMES")
    assert hermes
    assert all("hermes" in e.yool_id for e in hermes)


def test_roundtrip_via_canonical_json(tmp_path: Path) -> None:
    cat = build_agent_catalog()
    target = tmp_path / ".catalog/agents.json"
    save_catalog(cat, target)
    assert target.exists()
    cat2 = load_catalog(target)
    assert {e.yool_id for e in list_entries(cat)} == {
        e.yool_id for e in list_entries(cat2)
    }
    e = lookup_yool(cat2, "agent.claude-code.browser-e2e")
    assert e is not None and e.provider_key == "claude-code"


def test_insert_overwrites_same_key() -> None:
    cap_a = AgentCapability(key="plan", description="v1", cost_profile="research")
    cap_b = AgentCapability(key="plan", description="v2", cost_profile="research")
    provider_a = AgentProvider(key="p", name="P", runtime="x", capabilities=[cap_a])
    provider_b = AgentProvider(key="p", name="P", runtime="x", capabilities=[cap_b])
    cat = build_agent_catalog(AgentRegistry(providers=[provider_a]))
    cat2 = build_agent_catalog(AgentRegistry(providers=[provider_b]))
    e1 = lookup_yool(cat, "agent.p.plan")
    e2 = lookup_yool(cat2, "agent.p.plan")
    assert e1 is not None and e1.description == "v1"
    assert e2 is not None and e2.description == "v2"


def test_cli_catalog_build_and_list(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(app, ["catalog", "build"])
    assert result.exit_code == 0, result.output
    assert "wrote" in result.output
    out_path = tmp_path / ".catalog/agents.json"
    assert out_path.exists()
    data = json.loads(out_path.read_text())
    assert "flat" in data and "agent.codex.plan" in data["flat"]

    list_result = runner.invoke(app, ["catalog", "list"])
    assert list_result.exit_code == 0
    assert "codex" in list_result.output


def test_cli_catalog_show_and_find(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(app, ["catalog", "build"])

    show = runner.invoke(app, ["catalog", "show", "agent.codex.plan"])
    assert show.exit_code == 0
    assert "agent.codex.plan" in show.output

    missing = runner.invoke(app, ["catalog", "show", "agent.nope.nope"])
    assert missing.exit_code == 1

    find = runner.invoke(app, ["catalog", "find", "openclaw"])
    assert find.exit_code == 0
    assert "openclaw" in find.output
