"""Portable evidence bundle generation."""

from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.models.reports import RunReport
from sendsprint.planning import DeliveryPlan
from sendsprint.rollback import RollbackPlan
from sendsprint.rollback import evidence_filename as _rollback_filename


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
    rollback: RollbackPlan | None = None,
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

    if rollback is not None:
        rollback_path = root / _rollback_filename(rollback.run_id or run_id)
        rollback_path.write_text(rollback.model_dump_json(indent=2), encoding="utf-8")
        files.append(EvidenceFile(kind="rollback-plan", path=rollback_path.name))

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


# ---------------------------------------------------------------------------
# First-class evidence bundles (issue #96)
# ---------------------------------------------------------------------------


class EvidenceItemType(StrEnum):
    """Types of evidence items captured during a run."""

    command = "command"
    log = "log"
    screenshot = "screenshot"
    coverage = "coverage"
    risk = "risk"
    decision = "decision"


class EvidenceItem(BaseModel):
    """Single piece of evidence collected during a run."""

    model_config = ConfigDict(extra="forbid")

    type: EvidenceItemType
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EvidenceBundle(BaseModel):
    """Versioned evidence bundle linking items to tuple/receipt/yool IDs."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str = "2.0"
    run_id: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finalized_at: datetime | None = None
    items: list[EvidenceItem] = Field(default_factory=list)
    tuple_ids: list[str] = Field(default_factory=list)
    receipt_ids: list[str] = Field(default_factory=list)
    yool_ids: list[str] = Field(default_factory=list)


_BUNDLE_DIR = ".sendsprint/evidence"


class BundleManager:
    """Manage evidence bundles on disk under `<base>/.sendsprint/evidence/<run_id>/`."""

    def __init__(self, base_dir: str | Path = ".") -> None:
        self._base = Path(base_dir).expanduser().resolve()

    def _bundle_root(self, run_id: str) -> Path:
        return self._base / _BUNDLE_DIR / run_id

    # -- lifecycle -----------------------------------------------------------

    def create_bundle(self, run_id: str) -> EvidenceBundle:
        """Create a new empty bundle and persist it."""
        root = self._bundle_root(run_id)
        root.mkdir(parents=True, exist_ok=True)
        bundle = EvidenceBundle(run_id=run_id)
        self._write(bundle)
        return bundle

    def add_item(
        self,
        bundle: EvidenceBundle,
        item_type: EvidenceItemType | str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> EvidenceItem:
        """Append an evidence item to the bundle and persist."""
        if isinstance(item_type, str):
            item_type = EvidenceItemType(item_type)
        item = EvidenceItem(
            type=item_type,
            content=content,
            metadata=metadata or {},
        )
        bundle.items.append(item)
        self._write(bundle)
        return item

    def finalize(self, bundle: EvidenceBundle) -> EvidenceBundle:
        """Mark the bundle as finalized and persist."""
        bundle.finalized_at = datetime.now(UTC)
        self._write(bundle)
        return bundle

    def export_manifest(self, bundle: EvidenceBundle) -> dict[str, Any]:
        """Return the bundle manifest as a plain dict."""
        return json.loads(bundle.model_dump_json())

    def summarize_for_pr(self, bundle: EvidenceBundle) -> str:
        """Build a Markdown summary suitable for a PR body."""
        lines: list[str] = [
            f"## Evidence — run `{bundle.run_id}`",
            "",
        ]
        if bundle.tuple_ids:
            lines.append(f"**Tuples:** {', '.join(bundle.tuple_ids)}")
        if bundle.receipt_ids:
            lines.append(f"**Receipts:** {', '.join(bundle.receipt_ids)}")
        if bundle.yool_ids:
            lines.append(f"**Yools:** {', '.join(bundle.yool_ids)}")
        if bundle.tuple_ids or bundle.receipt_ids or bundle.yool_ids:
            lines.append("")

        by_type: dict[str, list[EvidenceItem]] = {}
        for item in bundle.items:
            by_type.setdefault(item.type.value, []).append(item)

        for kind, items in by_type.items():
            lines.append(f"### {kind.capitalize()} ({len(items)})")
            for it in items:
                preview = it.content[:120]
                if len(it.content) > 120:
                    preview += "..."
                lines.append(f"- {preview}")
            lines.append("")

        return "\n".join(lines).rstrip()

    # -- query ---------------------------------------------------------------

    def load_bundle(self, run_id: str) -> EvidenceBundle | None:
        """Load a persisted bundle by run_id, or None if absent."""
        path = self._bundle_root(run_id) / "bundle.json"
        if not path.exists():
            return None
        return EvidenceBundle.model_validate_json(path.read_text(encoding="utf-8"))

    def list_bundles(self) -> list[str]:
        """Return run_ids for all bundles under the base directory."""
        evidence_dir = self._base / _BUNDLE_DIR
        if not evidence_dir.exists():
            return []
        return sorted(
            d.name for d in evidence_dir.iterdir() if d.is_dir() and (d / "bundle.json").exists()
        )

    # -- internal ------------------------------------------------------------

    def _write(self, bundle: EvidenceBundle) -> Path:
        root = self._bundle_root(bundle.run_id)
        root.mkdir(parents=True, exist_ok=True)
        path = root / "bundle.json"
        path.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
        return path
