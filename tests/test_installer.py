"""Tests for the multi-agent skill installer."""

from __future__ import annotations

import pytest

from sendsprint.installer import BLOCK_BEGIN, BLOCK_END, TARGETS, install


def test_install_dedicated_file_targets(tmp_path):
    install(tmp_path, ["claude", "cursor", "kiro"])
    claude = tmp_path / ".claude/skills/sendsprint/SKILL.md"
    cursor = tmp_path / ".cursor/rules/sendsprint.mdc"
    kiro = tmp_path / ".kiro/steering/sendsprint.md"
    assert claude.exists() and "sendsprint run" in claude.read_text()
    assert claude.read_text().startswith("---\nname: sendsprint")
    assert "description:" in cursor.read_text()
    assert kiro.read_text().startswith("---\ninclusion: manual")


def test_block_targets_share_agents_md(tmp_path):
    results = install(tmp_path, ["codex", "opencode", "antigravity", "hermes", "openclaw"])
    agents = tmp_path / "AGENTS.md"
    text = agents.read_text()
    assert text.count(BLOCK_BEGIN) == 1 and text.count(BLOCK_END) == 1
    assert "sendsprint run" in text
    # First target creates it; the rest find the same block unchanged.
    assert results[0].action == "created"
    assert all(r.action == "unchanged" for r in results[1:])


def test_block_preserves_existing_content(tmp_path):
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# My project rules\n\nDo not break the build.\n")
    install(tmp_path, ["codex"])
    text = agents.read_text()
    assert "# My project rules" in text
    assert "Do not break the build." in text
    assert BLOCK_BEGIN in text and "sendsprint run" in text


def test_block_idempotent(tmp_path):
    install(tmp_path, ["gemini"])
    before = (tmp_path / "GEMINI.md").read_text()
    second = install(tmp_path, ["gemini"])
    after = (tmp_path / "GEMINI.md").read_text()
    assert before == after
    assert second[0].action == "unchanged"


def test_install_all_covers_every_target(tmp_path):
    results = install(tmp_path, sorted(TARGETS))
    assert {r.target for r in results} == set(TARGETS)


def test_unknown_target_raises(tmp_path):
    with pytest.raises(ValueError, match="unknown target"):
        install(tmp_path, ["notanagent"])
