"""Install SendSprint assistant plugin manifests into target repositories."""

from __future__ import annotations

import contextlib
import json
import shutil
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Literal

PluginPlatform = Literal[
    "claude",
    "codex",
    "hermes",
    "openclaw",
    "cursor",
    "windsurf",
    "kiro",
    "antigravity",
    "github-copilot",
]


@dataclass(frozen=True, slots=True)
class PluginProfile:
    platform: PluginPlatform
    display_name: str
    template: str
    default_target: str
    runtime_command: str
    notes: tuple[str, ...] = ()
    package_dir: str | None = None
    packaged_target: str | None = None


PLUGIN_PROFILES: dict[PluginPlatform, PluginProfile] = {
    "claude": PluginProfile(
        platform="claude",
        display_name="Claude Code",
        template="claude.md",
        default_target=".claude/skills/sendsprint/SKILL.md",
        runtime_command="sendsprint sprint",
        notes=("Ralph-style repair loops should inspect SendSprint artifacts first.",),
        package_dir="claude-code",
        packaged_target=".claude/plugins/sendsprint",
    ),
    "codex": PluginProfile(
        platform="codex",
        display_name="Codex",
        template="codex.md",
        default_target="AGENTS.md",
        runtime_command="sendsprint sprint",
        notes=("Codex can wrap long-running delivery with /goal when requested.",),
        package_dir="codex",
        packaged_target=".codex/plugins/sendsprint",
    ),
    "hermes": PluginProfile(
        platform="hermes",
        display_name="Hermes Agent",
        template="hermes.md",
        default_target=".hermes/skills/sendsprint.md",
        runtime_command="sendsprint full --workspace workspace.yaml",
        notes=("Hermes should use SendSprint as a local control-plane module.",),
        package_dir="hermes",
        packaged_target=".hermes/plugins/sendsprint",
    ),
    "openclaw": PluginProfile(
        platform="openclaw",
        display_name="OpenClaw",
        template="openclaw.md",
        default_target=".openclaw/skills/sendsprint.md",
        runtime_command="sendsprint preflight <provider> <id> --workspace workspace.yaml",
        notes=("OpenClaw is positioned as review/security validation around SendSprint.",),
        package_dir="openclaw",
        packaged_target=".openclaw/plugins/sendsprint",
    ),
    "cursor": PluginProfile(
        platform="cursor",
        display_name="Cursor",
        template="cursor.mdc",
        default_target=".cursor/rules/sendsprint.mdc",
        runtime_command="sendsprint sprint",
        notes=("Cursor uses alwaysApply repo rules.",),
    ),
    "windsurf": PluginProfile(
        platform="windsurf",
        display_name="Windsurf",
        template="windsurf.md",
        default_target=".windsurf/rules/sendsprint.md",
        runtime_command="sendsprint sprint",
        notes=("Windsurf uses always-on repo rules that delegate to SendSprint.",),
    ),
    "kiro": PluginProfile(
        platform="kiro",
        display_name="Kiro",
        template="kiro.md",
        default_target=".kiro/steering/sendsprint.md",
        runtime_command="sendsprint sprint",
        notes=("Kiro steering keeps SendSprint as the canonical sprint executor.",),
    ),
    "antigravity": PluginProfile(
        platform="antigravity",
        display_name="Antigravity",
        template="antigravity.md",
        default_target=".antigravity/rules/sendsprint.md",
        runtime_command="sendsprint sprint",
        notes=("Antigravity should use SendSprint as the local delivery control plane.",),
    ),
    "github-copilot": PluginProfile(
        platform="github-copilot",
        display_name="GitHub Copilot",
        template="copilot.md",
        default_target=".github/copilot-instructions.md",
        runtime_command="sendsprint sprint",
        notes=("Copilot reads this as repository instructions.",),
    ),
}


@dataclass(slots=True)
class PluginInstallResult:
    repo_path: Path
    created: list[Path] = field(default_factory=list)
    updated: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    manifest_path: Path | None = None
    dry_run: bool = False

    @property
    def changed(self) -> bool:
        return bool(self.created or self.updated)


def list_plugin_profiles() -> list[PluginProfile]:
    """Return built-in plugin profiles in stable order."""
    return [PLUGIN_PROFILES[key] for key in sorted(PLUGIN_PROFILES)]


def install_plugins(
    repo_path: str | Path,
    *,
    platforms: list[PluginPlatform] | None = None,
    force: bool = False,
    dry_run: bool = False,
    write_manifest: bool = True,
    packaged: bool = False,
) -> PluginInstallResult:
    """Install SendSprint plugin manifests into a repo-local plugin structure.

    When ``packaged=True``, copy the full plugin package tree (commands, agents,
    skills, hooks, manifest) for hosts that support it (``claude``, ``codex``,
    ``hermes``, ``openclaw``). Hosts without a packaged form fall back to the
    flat rule file install.
    """
    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"repo path not found: {repo}")
    selected = platforms or list(PLUGIN_PROFILES)
    result = PluginInstallResult(repo_path=repo, dry_run=dry_run)

    installed: list[dict[str, str]] = []
    for platform in selected:
        profile = PLUGIN_PROFILES[platform]
        if packaged and profile.package_dir and profile.packaged_target:
            target_dir = _target(repo, profile.packaged_target)
            _install_package(
                target_dir,
                profile.package_dir,
                result,
                force=force,
                dry_run=dry_run,
            )
            installed.append(
                {
                    "platform": profile.platform,
                    "display_name": profile.display_name,
                    "target": profile.packaged_target,
                    "runtime_command": profile.runtime_command,
                    "mode": "packaged",
                }
            )
            continue
        target = _target(repo, profile.default_target)
        _write_plugin_file(
            target,
            _read_template(profile.template),
            result,
            force=force,
            dry_run=dry_run,
        )
        installed.append(
            {
                "platform": profile.platform,
                "display_name": profile.display_name,
                "target": profile.default_target,
                "runtime_command": profile.runtime_command,
                "mode": "flat",
            }
        )

    if write_manifest:
        manifest = _target(repo, ".sendsprint/plugins/manifest.json")
        payload = {
            "schema_version": "1.0",
            "runtime": "python-cli",
            "entrypoints": {
                "cli": "sendsprint sprint",
                "web": "sendsprint web",
                "watch": "sendsprint watch --workspace workspace.yaml",
                "full": "sendsprint full --workspace workspace.yaml",
            },
            "plugins": installed,
        }
        _write_plugin_file(
            manifest,
            json.dumps(payload, indent=2) + "\n",
            result,
            force=True,
            dry_run=dry_run,
        )
        result.manifest_path = manifest
    return result


def result_to_json(result: PluginInstallResult) -> dict[str, object]:
    """Convert a plugin install result into stable JSON for CLI/tests."""
    repo = result.repo_path

    def rel(paths: list[Path]) -> list[str]:
        return [path.relative_to(repo).as_posix() for path in paths]

    return {
        "repo_path": str(repo),
        "created": rel(result.created),
        "updated": rel(result.updated),
        "skipped": rel(result.skipped),
        "manifest_path": (
            result.manifest_path.relative_to(repo).as_posix() if result.manifest_path else None
        ),
        "dry_run": result.dry_run,
        "changed": result.changed,
    }


def _read_template(name: str) -> str:
    return resources.files("sendsprint.plugin_templates").joinpath(name).read_text(encoding="utf-8")


def _write_plugin_file(
    target: Path,
    content: str,
    result: PluginInstallResult,
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
    target.write_text(content, encoding="utf-8")


def _target(repo: Path, rel: str) -> Path:
    target = (repo / rel).resolve()
    if target != repo and repo not in target.parents:
        raise ValueError(f"refusing to write outside repo: {rel}")
    return target


def _locate_plugin_package_dir(name: str) -> Path:
    """Find the source directory for a packaged plugin.

    Search order:
      1. ``sendsprint/_plugin_packages/<name>`` (when bundled in the wheel).
      2. ``plugins/<name>`` relative to the repo root (source checkout).
    """
    bundled = Path(__file__).parent / "_plugin_packages" / name
    if bundled.is_dir():
        return bundled
    source = Path(__file__).parent.parent / "plugins" / name
    if source.is_dir():
        return source
    raise FileNotFoundError(f"plugin package '{name}' not found (looked in {bundled} and {source})")


def _install_package(
    target_dir: Path,
    package_name: str,
    result: PluginInstallResult,
    *,
    force: bool,
    dry_run: bool,
) -> None:
    """Copy the packaged plugin tree into ``target_dir``."""
    source = _locate_plugin_package_dir(package_name)
    for src_file in sorted(p for p in source.rglob("*") if p.is_file()):
        rel = src_file.relative_to(source)
        dest = target_dir / rel
        if dest.exists() and not force:
            result.skipped.append(dest)
            continue
        bucket = result.updated if dest.exists() else result.created
        bucket.append(dest)
        if dry_run:
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dest)
        if src_file.suffix == ".sh":
            with contextlib.suppress(OSError):
                dest.chmod(dest.stat().st_mode | 0o111)
