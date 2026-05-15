"""Auto-discover a repository and fill ``.specs/`` with LLM-generated baselines.

Run by ``sendsprint init`` the first time SendSprint is enabled in a repo.
The Scaffolder collects deterministic signals (manifests, README, git history,
tech fingerprint) and asks the configured LLM to draft VISION/DOMAIN/DESIGN/
PATTERNS markdown. Every output is marked ``> auto-generated, review me``
so humans can refine before merging.

No file is overwritten unless ``force=True``.
"""

from __future__ import annotations

import datetime
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from sendsprint.tech import detect_tech

logger = logging.getLogger(__name__)

SPEC_FILES: dict[str, Path] = {
    "vision": Path(".specs/product/VISION.md"),
    "domain": Path(".specs/product/DOMAIN.md"),
    "design": Path(".specs/architecture/DESIGN.md"),
    "patterns": Path(".specs/architecture/PATTERNS.md"),
}

MANIFEST_CANDIDATES: tuple[str, ...] = (
    "pyproject.toml",
    "package.json",
    "requirements.txt",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "Gemfile",
    "composer.json",
    "*.csproj",
    "pubspec.yaml",
    "Package.swift",
)

DOC_CANDIDATES: tuple[str, ...] = ("README.md", "README.rst", "ARCHITECTURE.md", "CHANGELOG.md")


@dataclass
class RepoSignals:
    """Deterministic facts harvested from the repo before any LLM call."""

    repo_path: Path
    fingerprint_json: str
    manifests: dict[str, str] = field(default_factory=dict)
    docs: dict[str, str] = field(default_factory=dict)
    git_log: str = ""
    git_authors: str = ""
    file_count: int = 0
    primary_languages: list[str] = field(default_factory=list)


@dataclass
class ScaffoldResult:
    created: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)
    signals: RepoSignals | None = None


class Scaffolder:
    """Discover + draft. Side-effect-free until :meth:`write` is called."""

    PROMPT_HEADER = (
        "You are documenting an existing codebase for an AI agent harness. "
        "Use only the supplied facts. Be terse, concrete, and structured. "
        "Output GitHub-flavoured Markdown with the exact section headings I "
        "ask for. Mark uncertain facts with `_TODO:_`. Never invent APIs."
    )

    def __init__(self, repo_path: Path, *, llm=None) -> None:
        self.repo_path = repo_path.expanduser().resolve()
        self.llm = llm  # injected; falls back to LlmClient lazily inside generate()

    def discover(self) -> RepoSignals:
        """Collect deterministic signals. No network, no LLM."""
        fp = detect_tech(self.repo_path)
        signals = RepoSignals(
            repo_path=self.repo_path,
            fingerprint_json=fp.model_dump_json(indent=2),
            primary_languages=list(getattr(fp, "techs", []) or []),
            file_count=_count_files(self.repo_path),
        )
        for name in MANIFEST_CANDIDATES:
            for match in self.repo_path.glob(name):
                if match.is_file():
                    signals.manifests[match.name] = _read_capped(match, 4000)
        for name in DOC_CANDIDATES:
            target = self.repo_path / name
            if target.is_file():
                signals.docs[name] = _read_capped(target, 6000)
        signals.git_log = _git(self.repo_path, ["log", "--oneline", "-20"])
        signals.git_authors = _git(self.repo_path, ["shortlog", "-sne", "--all"])
        return signals

    def generate(
        self,
        signals: RepoSignals,
        *,
        offline: bool = False,
        on_step: Callable[[str], None] | None = None,
    ) -> dict[str, str]:
        """Draft the four spec docs. With ``offline=True`` skips the LLM and emits
        deterministic templates filled with collected facts.

        ``on_step(key)`` is invoked before each spec is generated (CLI uses it to
        animate a spinner).
        """
        today = datetime.date.today().isoformat()
        sections_by_key = {
            "vision": _VISION_SECTIONS,
            "domain": _DOMAIN_SECTIONS,
            "design": _DESIGN_SECTIONS,
            "patterns": _PATTERNS_SECTIONS,
        }
        outputs: dict[str, str] = {}
        if offline:
            for key, sections in sections_by_key.items():
                if on_step:
                    on_step(key)
                outputs[key] = _add_header(key, today, _offline_body(sections, signals))
            return outputs
        client = self.llm or _default_client()
        prompts = {
            "vision": self._prompt_vision(signals),
            "domain": self._prompt_domain(signals),
            "design": self._prompt_design(signals),
            "patterns": self._prompt_patterns(signals),
        }
        for key, prompt in prompts.items():
            if on_step:
                on_step(key)
            body = client.complete(prompt, system=self.PROMPT_HEADER)
            outputs[key] = _add_header(key, today, body)
        return outputs

    def write(self, outputs: dict[str, str], *, force: bool = False) -> ScaffoldResult:
        """Write generated markdown to ``.specs/``. Skips existing files unless ``force``."""
        result = ScaffoldResult()
        for key, body in outputs.items():
            target = self.repo_path / SPEC_FILES[key]
            if target.exists() and not force:
                result.skipped.append(target)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(body)
            result.created.append(target)
        return result

    def run(
        self,
        *,
        force: bool = False,
        offline: bool = False,
        on_step: Callable[[str], None] | None = None,
    ) -> ScaffoldResult:
        """Discover + generate + write in one shot."""
        signals = self.discover()
        outputs = self.generate(signals, offline=offline, on_step=on_step)
        result = self.write(outputs, force=force)
        result.signals = signals
        return result

    def _prompt_vision(self, s: RepoSignals) -> str:
        return _build_prompt(title="VISION.md", sections=_VISION_SECTIONS, signals=s)

    def _prompt_domain(self, s: RepoSignals) -> str:
        return _build_prompt(title="DOMAIN.md", sections=_DOMAIN_SECTIONS, signals=s)

    def _prompt_design(self, s: RepoSignals) -> str:
        return _build_prompt(title="DESIGN.md", sections=_DESIGN_SECTIONS, signals=s)

    def _prompt_patterns(self, s: RepoSignals) -> str:
        return _build_prompt(title="PATTERNS.md", sections=_PATTERNS_SECTIONS, signals=s)


_VISION_SECTIONS: list[str] = [
    "## North star",
    "## Non-goals",
    "## Target users",
    "## Success metrics",
    "## Open questions",
]
_DOMAIN_SECTIONS: list[str] = [
    "## Vocabulary",
    "## Core entities",
    "## Lifecycles",
    "## Invariants",
    "## External systems",
]
_DESIGN_SECTIONS: list[str] = [
    "## Bird's-eye",
    "## Layers",
    "## Data flow",
    "## Concurrency model",
    "## Failure model",
    "## Extension points",
]
_PATTERNS_SECTIONS: list[str] = [
    "## File header convention",
    "## Error handling",
    "## I/O boundary",
    "## Tests",
    "## DON'Ts",
]


def _offline_body(sections: list[str], signals: RepoSignals) -> str:
    """Deterministic Markdown body using only collected facts. No LLM call."""
    facts_block = (
        f"### Detected\n"
        f"- techs: {', '.join(signals.primary_languages) or 'unknown'}\n"
        f"- files: {signals.file_count}\n"
        f"- manifests: {', '.join(signals.manifests.keys()) or 'none'}\n"
        f"- docs: {', '.join(signals.docs.keys()) or 'none'}\n"
    )
    body = facts_block + "\n"
    for s in sections:
        body += f"{s}\n\n_TODO:_\n\n"
    return body


def _build_prompt(*, title: str, sections: list[str], signals: RepoSignals) -> str:
    section_list = "\n".join(f"- {s.lstrip('# ').strip()}" for s in sections)
    section_template = "\n\n".join(f"{s}\n\n_TODO:_" for s in sections)
    facts = (
        f"### Tech fingerprint\n```json\n{signals.fingerprint_json}\n```\n\n"
        f"### Primary languages\n{', '.join(signals.primary_languages) or 'unknown'}\n\n"
        f"### File count\n{signals.file_count}\n\n"
        f"### Manifests\n"
        + "\n".join(f"#### {name}\n```\n{body}\n```" for name, body in signals.manifests.items())
        + "\n\n### Docs\n"
        + "\n".join(f"#### {name}\n```\n{body}\n```" for name, body in signals.docs.items())
        + f"\n\n### Recent commits\n```\n{signals.git_log}\n```\n\n"
        f"### Authors\n```\n{signals.git_authors}\n```\n"
    )
    return (
        f"Generate `{title}` for this repository.\n\n"
        f"Required sections (use these exact `## ` headings):\n{section_list}\n\n"
        f"Use this template if a section has no clear answer yet:\n\n"
        f"````markdown\n{section_template}\n````\n\n"
        f"Facts about the repo:\n\n{facts}"
    )


def _add_header(key: str, today: str, body: str) -> str:
    title_map = {
        "vision": "Vision",
        "domain": "Domain",
        "design": "Design",
        "patterns": "Patterns",
    }
    title = title_map[key]
    banner = (
        f"# {title}\n\n"
        f"> auto-generated by `sendsprint init` on {today}. review me before relying on it.\n\n"
    )
    if body.lstrip().startswith("# "):
        body = "\n".join(body.splitlines()[1:]).lstrip()
    return banner + body.rstrip() + "\n"


def _read_capped(path: Path, max_bytes: int) -> str:
    try:
        data = path.read_text(errors="replace")
    except OSError as exc:
        logger.debug("could not read %s: %s", path, exc)
        return ""
    if len(data) <= max_bytes:
        return data
    return data[:max_bytes] + f"\n... [truncated, {len(data) - max_bytes} more bytes]"


def _git(repo: Path, args: list[str]) -> str:
    try:
        out = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        logger.debug("git %s failed: %s", args, exc)
        return ""
    return (out.stdout or out.stderr or "").strip()


def _count_files(repo: Path) -> int:
    out = _git(repo, ["ls-files"])
    if not out:
        return sum(1 for _ in repo.rglob("*") if _.is_file())
    return out.count("\n") + 1


def _default_client():
    from sendsprint.llm.client import LlmClient

    return LlmClient()
