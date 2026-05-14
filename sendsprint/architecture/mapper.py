"""ArchitectureMapper - inspects a repo to detect architecture documentation."""

from __future__ import annotations

import logging
from pathlib import Path

from sendsprint.models import ArchitectureReport

logger = logging.getLogger(__name__)

AGENTIC_STARTER_MARKERS = (
    ".agentic-starter.json",
    "AGENTS.md",
    ".specs/architecture/DESIGN.md",
    ".specs/product/VISION.md",
)
ARCHITECTURE_FILE_NAMES = ("ARCHITECTURE.md", "ARCHITECTURE.MD", "Architecture.md")
README_FILE_NAMES = ("README.md", "README.MD", "Readme.md")
ADR_DIRS = ("docs/adr", "docs/adrs", "docs/architecture/decisions", "adr", "adrs")
C4_DIRS = ("docs/c4", "docs/architecture/c4", "c4")
ARCH_DIRS = ("docs/architecture", "docs/arch")
DEPENDENCY_FILES = (
    "docs/dependencies.md",
    "docs/dependency-graph.svg",
    "docs/dependency-graph.png",
    "docs/deps.md",
    "deps.md",
)
DEPLOY_FILES = (
    "docs/deploy.md",
    "docs/deployment.md",
    "docs/topology.md",
    "docs/infra/topology.md",
    "infra/topology.yaml",
    "infra/topology.yml",
    "infra/topology.json",
)

WEIGHTS = {
    "has_architecture_md": 0.25,
    "has_docs_architecture_dir": 0.15,
    "has_c4": 0.15,
    "has_adrs": 0.20,
    "has_dependency_graph": 0.10,
    "has_deploy_topology": 0.10,
    "has_readme": 0.05,
}


class ArchitectureMapper:
    """Inspects a repo path and produces an ArchitectureReport."""

    def inspect(self, repo_path: str | Path) -> ArchitectureReport:
        root = Path(repo_path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"repo path not found: {root}")
        report = ArchitectureReport(
            repo_path=str(root),
            has_architecture_md=_any_file_exists(root, ARCHITECTURE_FILE_NAMES),
            has_docs_architecture_dir=_any_dir_exists(root, ARCH_DIRS),
            has_c4=_any_dir_exists(root, C4_DIRS),
            has_readme=_any_file_exists(root, README_FILE_NAMES),
            has_dependency_graph=_any_path_exists(root, DEPENDENCY_FILES),
            has_deploy_topology=_any_path_exists(root, DEPLOY_FILES),
            has_agentic_starter=_any_path_exists(root, AGENTIC_STARTER_MARKERS),
        )
        adr_dir = _first_existing_dir(root, ADR_DIRS)
        if adr_dir:
            adrs = list(adr_dir.glob("*.md"))
            report.has_adrs = len(adrs) > 0
            report.adr_count = len(adrs)
        report.missing = _missing(report)
        report.score = _score(report)
        return report


def _any_file_exists(root: Path, names: tuple[str, ...]) -> bool:
    return any((root / n).is_file() for n in names)


def _any_dir_exists(root: Path, dirs: tuple[str, ...]) -> bool:
    return any((root / d).is_dir() for d in dirs)


def _first_existing_dir(root: Path, dirs: tuple[str, ...]) -> Path | None:
    for d in dirs:
        candidate = root / d
        if candidate.is_dir():
            return candidate
    return None


def _any_path_exists(root: Path, paths: tuple[str, ...]) -> bool:
    return any((root / p).exists() for p in paths)


def _missing(report: ArchitectureReport) -> list[str]:
    missing: list[str] = []
    if not report.has_architecture_md:
        missing.append("ARCHITECTURE.md")
    if not report.has_docs_architecture_dir:
        missing.append("docs/architecture/")
    if not report.has_c4:
        missing.append("C4 diagrams (docs/c4/)")
    if not report.has_adrs:
        missing.append("ADRs (docs/adr/*.md)")
    if not report.has_dependency_graph:
        missing.append("dependency graph (docs/dependencies.*)")
    if not report.has_deploy_topology:
        missing.append("deploy topology (docs/deploy.md or infra/topology.*)")
    if not report.has_readme:
        missing.append("README.md")
    return missing


def _score(report: ArchitectureReport) -> float:
    total = 0.0
    for attr, weight in WEIGHTS.items():
        if getattr(report, attr):
            total += weight
    return round(total, 4)
