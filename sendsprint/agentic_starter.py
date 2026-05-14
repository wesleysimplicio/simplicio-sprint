"""Sync the agentic-starter scaffold into a repository.

The sync is intentionally file-based and conservative: existing files are
preserved unless ``force=True``. Scheduled automation can run the same command
and open a PR for review instead of mutating ``main`` directly.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_AGENTIC_STARTER_SOURCE = "https://github.com/wesleysimplicio/agentic-starter"
DEFAULT_AGENTIC_STARTER_REF = "latest"
AGENTIC_STARTER_LOCK = ".agentic-starter.json"

AGENTIC_STARTER_PATHS: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    "INIT.md",
    "_BOOTSTRAP.md",
    "bootstrap.ps1",
    "bootstrap.sh",
    "playwright.config.ts",
    "bin",
    ".agents",
    ".claude",
    ".codex",
    ".skills",
    ".github/CODEOWNERS",
    ".github/ISSUE_TEMPLATE",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/workflows/ci.yml",
    ".github/workflows/dod.yml",
    ".github/workflows/scaffold-self-check.yml",
    "templates/ADR-template.md",
    "templates/task-template.md",
    ".specs/architecture/ADR-template.md",
    ".specs/product/PERSONAS.md",
    ".specs/sprints/BACKLOG.md",
    ".specs/sprints/task-template.md",
    ".specs/workflow/CONTRIBUTING.md",
    ".specs/workflow/RELEASE.md",
    ".specs/workflow/WORKFLOW.md",
)


@dataclass
class AgenticStarterSyncResult:
    """Result returned by :func:`sync_agentic_starter`."""

    repo_path: Path
    source: str
    requested_ref: str
    resolved_ref: str
    created: list[Path] = field(default_factory=list)
    updated: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    dry_run: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated)


def sync_agentic_starter(
    repo_path: str | Path,
    *,
    source: str = DEFAULT_AGENTIC_STARTER_SOURCE,
    ref: str = DEFAULT_AGENTIC_STARTER_REF,
    paths: tuple[str, ...] = AGENTIC_STARTER_PATHS,
    force: bool = False,
    dry_run: bool = False,
) -> AgenticStarterSyncResult:
    """Copy the latest agentic-starter structure into ``repo_path``.

    ``source`` may be a local directory, a GitHub repo URL, or ``owner/repo``.
    GitHub sources use the latest release when ``ref="latest"`` and fall back to
    the default branch name ``main`` if the repository has no release yet.
    """

    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"repo path not found: {repo}")

    source_path = Path(source).expanduser()
    if source_path.exists():
        result = AgenticStarterSyncResult(
            repo_path=repo,
            source=str(source_path.resolve()),
            requested_ref=ref,
            resolved_ref=ref,
            dry_run=dry_run,
        )
        _copy_paths(source_path.resolve(), repo, paths, result, force=force, dry_run=dry_run)
        _write_lock(result, paths, force=force, dry_run=dry_run)
        return result

    owner, repo_name = _parse_github_source(source)
    with tempfile.TemporaryDirectory(prefix="sendsprint-agentic-starter-") as tmp:
        tmp_path = Path(tmp)
        archive, resolved_ref = _download_github_archive(owner, repo_name, ref, tmp_path)
        with zipfile.ZipFile(archive) as zf:
            zf.extractall(tmp_path / "src")
        source_root = _archive_root(tmp_path / "src")

        result = AgenticStarterSyncResult(
            repo_path=repo,
            source=f"https://github.com/{owner}/{repo_name}",
            requested_ref=ref,
            resolved_ref=resolved_ref,
            dry_run=dry_run,
        )
        _copy_paths(source_root, repo, paths, result, force=force, dry_run=dry_run)
        _write_lock(result, paths, force=force, dry_run=dry_run)
        return result


def _copy_paths(
    source_root: Path,
    repo: Path,
    paths: tuple[str, ...],
    result: AgenticStarterSyncResult,
    *,
    force: bool,
    dry_run: bool,
) -> None:
    for rel in paths:
        source = source_root / rel
        if not source.exists():
            result.missing.append(rel)
            continue
        if source.is_file():
            _copy_file(source, _target(repo, rel), result, force=force, dry_run=dry_run)
            continue
        for child in source.rglob("*"):
            if child.is_file():
                child_rel = child.relative_to(source_root).as_posix()
                _copy_file(child, _target(repo, child_rel), result, force=force, dry_run=dry_run)


def _copy_file(
    source: Path,
    target: Path,
    result: AgenticStarterSyncResult,
    *,
    force: bool,
    dry_run: bool,
) -> None:
    if target.exists() and not force:
        result.skipped.append(target)
        return

    bucket = result.updated if target.exists() else result.created
    bucket.append(target)
    if dry_run:
        return

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


def _target(repo: Path, rel: str) -> Path:
    target = (repo / rel).resolve()
    if target != repo and repo not in target.parents:
        raise ValueError(f"refusing to write outside repo: {rel}")
    return target


def _write_lock(
    result: AgenticStarterSyncResult,
    paths: tuple[str, ...],
    *,
    force: bool,
    dry_run: bool,
) -> None:
    lock = result.repo_path / AGENTIC_STARTER_LOCK
    data = {
        "source": result.source,
        "requested_ref": result.requested_ref,
        "resolved_ref": result.resolved_ref,
        "synced_at": datetime.now(tz=UTC).isoformat(timespec="seconds"),
        "mode": "force" if force else "missing",
        "managed_paths": list(paths),
    }
    if lock.exists() and not force:
        result.skipped.append(lock)
        return
    if lock.exists():
        result.updated.append(lock)
    else:
        result.created.append(lock)
    if not dry_run:
        lock.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _parse_github_source(source: str) -> tuple[str, str]:
    normalized = source.removesuffix(".git").rstrip("/")
    marker = "github.com/"
    if marker in normalized:
        normalized = normalized.split(marker, 1)[1]
    parts = normalized.split("/")
    if len(parts) >= 2 and parts[0] and parts[1]:
        return parts[0], parts[1]
    raise ValueError("agentic-starter source must be a local path, a GitHub URL, or 'owner/repo'")


def _download_github_archive(
    owner: str,
    repo: str,
    ref: str,
    target_dir: Path,
) -> tuple[Path, str]:
    resolved_ref = _resolve_github_ref(owner, repo, ref)
    archive_url = f"https://api.github.com/repos/{owner}/{repo}/zipball/{resolved_ref}"
    archive = target_dir / "agentic-starter.zip"
    _download(archive_url, archive)
    return archive, resolved_ref


def _resolve_github_ref(owner: str, repo: str, ref: str) -> str:
    if ref != "latest":
        return ref
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    try:
        data = json.loads(_read_url(url).decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return "main"
        raise
    tag = data.get("tag_name")
    return str(tag) if tag else "main"


def _read_url(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "sendsprint"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def _download(url: str, target: Path) -> None:
    data = _read_url(url)
    target.write_bytes(data)


def _archive_root(path: Path) -> Path:
    children = [p for p in path.iterdir() if p.is_dir()]
    if len(children) == 1:
        return children[0]
    return path


def result_to_json(result: AgenticStarterSyncResult) -> dict[str, Any]:
    """Return a JSON-serializable sync result for CLI output/tests."""

    repo = result.repo_path

    def _rel(paths: list[Path]) -> list[str]:
        return [p.relative_to(repo).as_posix() for p in paths]

    return {
        "repo_path": str(repo),
        "source": result.source,
        "requested_ref": result.requested_ref,
        "resolved_ref": result.resolved_ref,
        "created": _rel(result.created),
        "updated": _rel(result.updated),
        "skipped": _rel(result.skipped),
        "missing": result.missing,
        "dry_run": result.dry_run,
        "changed": result.changed,
    }
