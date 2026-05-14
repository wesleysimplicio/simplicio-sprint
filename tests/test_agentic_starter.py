"""Tests for agentic-starter scaffold syncing."""

from __future__ import annotations

from pathlib import Path

from sendsprint.agentic_starter import (
    AGENTIC_STARTER_LOCK,
    result_to_json,
    sync_agentic_starter,
)


def _seed_source(root: Path) -> None:
    (root / ".agents").mkdir(parents=True)
    (root / ".agents" / "reviewer.agent.md").write_text("reviewer v2\n", encoding="utf-8")
    (root / ".skills" / "ralph-loop").mkdir(parents=True)
    (root / ".skills" / "ralph-loop" / "SKILL.md").write_text("skill v2\n", encoding="utf-8")
    (root / "templates").mkdir()
    (root / "templates" / "task-template.md").write_text("task template\n", encoding="utf-8")
    (root / "AGENTS.md").write_text("upstream agents\n", encoding="utf-8")


def test_sync_agentic_starter_copies_missing_files_and_lock(tmp_path: Path) -> None:
    source = tmp_path / "upstream"
    repo = tmp_path / "repo"
    source.mkdir()
    repo.mkdir()
    _seed_source(source)

    result = sync_agentic_starter(
        repo,
        source=str(source),
        paths=(".agents", ".skills", "AGENTS.md"),
    )

    assert (repo / ".agents" / "reviewer.agent.md").read_text(encoding="utf-8") == "reviewer v2\n"
    assert (repo / ".skills" / "ralph-loop" / "SKILL.md").is_file()
    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == "upstream agents\n"
    assert (repo / AGENTIC_STARTER_LOCK).is_file()
    assert {p.relative_to(repo).as_posix() for p in result.created} >= {
        ".agents/reviewer.agent.md",
        ".skills/ralph-loop/SKILL.md",
        "AGENTS.md",
        AGENTIC_STARTER_LOCK,
    }


def test_sync_agentic_starter_preserves_existing_files_without_force(tmp_path: Path) -> None:
    source = tmp_path / "upstream"
    repo = tmp_path / "repo"
    source.mkdir()
    repo.mkdir()
    _seed_source(source)
    (repo / "AGENTS.md").write_text("local agents\n", encoding="utf-8")

    result = sync_agentic_starter(repo, source=str(source), paths=("AGENTS.md",))

    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == "local agents\n"
    assert "AGENTS.md" in result_to_json(result)["skipped"]


def test_sync_agentic_starter_force_overwrites_existing_files(tmp_path: Path) -> None:
    source = tmp_path / "upstream"
    repo = tmp_path / "repo"
    source.mkdir()
    repo.mkdir()
    _seed_source(source)
    (repo / "AGENTS.md").write_text("local agents\n", encoding="utf-8")

    result = sync_agentic_starter(repo, source=str(source), paths=("AGENTS.md",), force=True)

    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == "upstream agents\n"
    assert "AGENTS.md" in result_to_json(result)["updated"]


def test_sync_agentic_starter_dry_run_does_not_write(tmp_path: Path) -> None:
    source = tmp_path / "upstream"
    repo = tmp_path / "repo"
    source.mkdir()
    repo.mkdir()
    _seed_source(source)

    result = sync_agentic_starter(repo, source=str(source), paths=("AGENTS.md",), dry_run=True)

    assert not (repo / "AGENTS.md").exists()
    assert "AGENTS.md" in result_to_json(result)["created"]
    assert result.dry_run is True


def test_sync_agentic_starter_reports_missing_upstream_paths(tmp_path: Path) -> None:
    source = tmp_path / "upstream"
    repo = tmp_path / "repo"
    source.mkdir()
    repo.mkdir()

    result = sync_agentic_starter(repo, source=str(source), paths=(".agents",))

    assert result.missing == [".agents"]
