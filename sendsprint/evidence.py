"""Portable evidence bundle generation."""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.models.reports import RunReport
from sendsprint.planning import DeliveryPlan


class EvidenceFile(BaseModel):
    """File included in a bundle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: str
    source: str | None = None
    path: str


class EvidenceBundleManifest(BaseModel):
    """Stable bundle manifest for dashboard and review consumers."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = "1.0"
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    root: str
    summary: str | None = None
    files: list[EvidenceFile] = Field(default_factory=list)
    pr_urls: list[str] = Field(default_factory=list)
    issue_updates: list[str] = Field(default_factory=list)


def create_evidence_bundle(
    report: RunReport,
    output_dir: str | Path,
    *,
    plan: DeliveryPlan | None = None,
    command_logs: list[Path] | None = None,
    extra_files: list[Path] | None = None,
    issue_updates: list[str] | None = None,
) -> EvidenceBundleManifest:
    """Create a portable evidence bundle and return its manifest."""
    run_id = report.sprint_id or "run"
    root = Path(output_dir).expanduser().resolve() / f"evidence-{run_id}"
    root.mkdir(parents=True, exist_ok=True)

    files: list[EvidenceFile] = []
    run_report_path = root / "run-report.json"
    run_report_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    files.append(EvidenceFile(kind="run-report", path=run_report_path.name))

    if plan is not None:
        plan_path = root / "dry-run-plan.json"
        plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
        files.append(EvidenceFile(kind="dry-run-plan", path=plan_path.name))

    for source in command_logs or []:
        files.append(_copy_into(root, source, "command-log"))
    for source in extra_files or []:
        files.append(_copy_into(root, source, "artifact"))

    pr_urls = [pr.url for pr in report.prs if pr.url]
    manifest = EvidenceBundleManifest(
        run_id=run_id,
        root=str(root),
        summary=report.summary,
        files=files,
        pr_urls=pr_urls,
        issue_updates=issue_updates or [],
    )
    manifest_path = root / "manifest.json"
    manifest_path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    manifest.files.append(EvidenceFile(kind="manifest", path=manifest_path.name))
    return manifest


def _copy_into(root: Path, source: Path, kind: str) -> EvidenceFile:
    src = source.expanduser().resolve()
    dest = root / src.name
    shutil.copy2(src, dest)
    return EvidenceFile(kind=kind, source=str(src), path=dest.name)
