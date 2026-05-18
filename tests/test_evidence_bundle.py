"""Tests for portable evidence bundles."""

from __future__ import annotations

from pathlib import Path

from sendsprint.evidence import create_evidence_bundle
from sendsprint.models.reports import PrInfo, RunReport


def test_create_evidence_bundle_writes_manifest_and_report(tmp_path: Path) -> None:
    report = RunReport(workspace="ws", sprint_id="42", summary="ok")
    report.prs.append(
        PrInfo(
            provider="github",
            repo="repo",
            title="PR",
            source_branch="feature/x",
            target_branch="main",
            url="https://github.com/o/r/pull/1",
        )
    )
    manifest = create_evidence_bundle(report, tmp_path, issue_updates=["closed #1"])
    root = Path(manifest.root)
    assert (root / "run-report.json").exists()
    assert (root / "manifest.json").exists()
    assert manifest.pr_urls == ["https://github.com/o/r/pull/1"]
    assert manifest.issue_updates == ["closed #1"]
