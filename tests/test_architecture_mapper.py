"""Unit tests for ArchitectureMapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from sendsprint.architecture import ArchitectureMapper


def test_empty_repo_has_zero_score(tmp_path: Path) -> None:
    report = ArchitectureMapper().inspect(tmp_path)
    assert report.score == 0.0
    assert report.is_mapped is False
    assert "ARCHITECTURE.md" in report.missing
    assert "README.md" in report.missing


def test_full_repo_passes_threshold(tmp_path: Path) -> None:
    (tmp_path / "ARCHITECTURE.md").write_text("# Architecture")
    (tmp_path / "README.md").write_text("# Readme")
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    (tmp_path / "docs" / "c4").mkdir(parents=True)
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-foo.md").write_text("# ADR 1")
    (adr_dir / "0002-bar.md").write_text("# ADR 2")
    (tmp_path / "docs" / "dependencies.md").write_text("deps")
    (tmp_path / "docs" / "deploy.md").write_text("deploy")

    report = ArchitectureMapper().inspect(tmp_path)
    assert report.score == 1.0
    assert report.is_mapped is True
    assert report.adr_count == 2
    assert report.missing == []


def test_partial_repo_below_threshold(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Readme")
    report = ArchitectureMapper().inspect(tmp_path)
    assert 0.0 < report.score < 0.6
    assert report.is_mapped is False
    assert "ARCHITECTURE.md" in report.missing


def test_partial_repo_meets_threshold(tmp_path: Path) -> None:
    (tmp_path / "ARCHITECTURE.md").write_text("# Architecture")
    (tmp_path / "README.md").write_text("# Readme")
    (tmp_path / "docs" / "architecture").mkdir(parents=True)
    adr_dir = tmp_path / "docs" / "adr"
    adr_dir.mkdir(parents=True)
    (adr_dir / "0001-foo.md").write_text("# ADR 1")

    report = ArchitectureMapper().inspect(tmp_path)
    assert report.score >= 0.6
    assert report.is_mapped is True
    assert report.adr_count == 1


def test_missing_repo_path_raises(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist"
    with pytest.raises(FileNotFoundError):
        ArchitectureMapper().inspect(missing)


def test_agentic_starter_marker_short_circuits_is_mapped(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("# Agents")
    report = ArchitectureMapper().inspect(tmp_path)
    assert report.has_agentic_starter is True
    assert report.is_mapped is True


def test_agentic_starter_specs_design_also_detected(tmp_path: Path) -> None:
    specs = tmp_path / ".specs" / "architecture"
    specs.mkdir(parents=True)
    (specs / "DESIGN.md").write_text("# Design")
    report = ArchitectureMapper().inspect(tmp_path)
    assert report.has_agentic_starter is True
    assert report.is_mapped is True


def test_agentic_starter_lock_also_detected(tmp_path: Path) -> None:
    (tmp_path / ".agentic-starter.json").write_text("{}")
    report = ArchitectureMapper().inspect(tmp_path)
    assert report.has_agentic_starter is True
    assert report.is_mapped is True


def test_no_starter_marker_does_not_set_flag(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Readme")
    report = ArchitectureMapper().inspect(tmp_path)
    assert report.has_agentic_starter is False
