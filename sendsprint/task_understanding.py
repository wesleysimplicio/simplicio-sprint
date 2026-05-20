"""Deterministic sprint item intent normalization before routing."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.issue_quality import parse_acceptance_criteria
from sendsprint.models.sprint import SprintItem
from sendsprint.models.workspace import RepoConfig, WorkspaceConfig


class TaskUnderstandingReport(BaseModel):
    """Structured routing hints derived from a single sprint item."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    item_key: str
    item_type: str
    title: str
    project: str | None = None
    surfaces: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    likely_repos: list[str] = Field(default_factory=list)
    validation_needs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)
    signals: dict[str, list[str]] = Field(default_factory=dict)
    requires_confirmation: bool = False


_SURFACE_ORDER = ("front", "back", "full-stack", "docs", "infra", "mobile", "cli")
_SURFACE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "front": (
        "front",
        "frontend",
        "front end",
        "ui",
        "ux",
        "screen",
        "page",
        "browser",
        "modal",
        "button",
        "form",
        "dashboard",
        "layout",
        "visual",
        "navigation",
        "component",
        "react",
        "vue",
        "angular",
        "next",
        "css",
        "html",
        "web",
    ),
    "back": (
        "api",
        "endpoint",
        "request",
        "response",
        "service",
        "backend",
        "back end",
        "database",
        "db",
        "query",
        "sql",
        "migration",
        "controller",
        "webhook",
        "integration",
        "contract",
        "queue",
        "event",
        "persist",
        "repository",
    ),
    "docs": (
        "docs",
        "documentation",
        "readme",
        "guide",
        "tutorial",
        "example",
        "adr",
        "changelog",
        "instructions",
        "runbook",
        "copy",
    ),
    "infra": (
        "infra",
        "infrastructure",
        "ci",
        "cd",
        "pipeline",
        "deploy",
        "deployment",
        "docker",
        "kubernetes",
        "k8s",
        "helm",
        "terraform",
        "cloud",
        "environment",
        "github actions",
        "workflow",
        "observability",
        "monitoring",
        "secret",
        "secrets",
    ),
    "mobile": (
        "mobile",
        "ios",
        "android",
        "react native",
        "expo",
        "app store",
        "play store",
    ),
    "cli": (
        "cli",
        "cli command",
        "terminal",
        "stdout",
        "stderr",
        "exit code",
        "shell",
        "console",
    ),
}
_CAPABILITY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "bugfix": ("fix", "bug", "broken", "error", "exception", "regression", "defect"),
    "auth": (
        "auth",
        "authentication",
        "authorization",
        "permission",
        "login",
        "token",
        "oauth",
        "sso",
    ),
    "data": ("database", "db", "query", "sql", "migration", "schema", "persist"),
    "integration": ("integration", "webhook", "sync", "external", "jira", "azure devops"),
    "testing": ("test", "tests", "pytest", "playwright", "coverage", "regression"),
    "security-review": ("security", "secret", "secrets", "vulnerability", "permission"),
    "refactor": ("refactor", "cleanup", "debt", "simplify", "rename"),
}
_SURFACE_CAPABILITIES = {
    "front": "frontend-ui",
    "back": "backend-api",
    "docs": "documentation",
    "infra": "deployment-infra",
    "mobile": "mobile-app",
    "cli": "cli-tooling",
}
_ROLE_BY_SURFACE = {
    "front": {"front"},
    "back": {"api", "back", "lib"},
    "docs": {"other"},
    "infra": {"infra"},
    "mobile": {"mobile"},
    "cli": {"lib", "api", "back"},
}
_LOGICAL_REPO_BY_SURFACE = {
    "front": "front",
    "back": "api",
    "docs": "docs",
    "infra": "infra",
    "mobile": "mobile",
    "cli": "cli",
}
_UNCERTAINTY_KEYWORDS = (
    "tbd",
    "unclear",
    "unknown",
    "investigate",
    "spike",
    "research",
    "clarify",
    "maybe",
    "?",
)


def understand_sprint_item(
    item: SprintItem,
    workspace: WorkspaceConfig | None = None,
) -> TaskUnderstandingReport:
    """Build a deterministic task understanding report for routing decisions."""
    labels = [label.strip() for label in item.labels if label.strip()]
    acceptance_criteria = parse_acceptance_criteria(item.acceptance_criteria)
    comments = [comment.body for comment in item.comments if comment.body.strip()]
    attachments = [
        " ".join(part for part in [attachment.filename, attachment.mime_type or ""] if part)
        for attachment in item.attachments
        if attachment.filename.strip()
    ]
    fields = _text_fields(item, labels, acceptance_criteria, comments, attachments)

    signals: dict[str, list[str]] = {}
    _collect_keyword_signals(fields, _SURFACE_KEYWORDS, signals)
    _collect_keyword_signals(fields, _CAPABILITY_KEYWORDS, signals)
    _collect_label_signals(labels, signals)
    _collect_validation_signals(fields, attachments, acceptance_criteria, signals)
    if item.parent_key:
        _add_signal(signals, "parent_key", item.parent_key)

    surfaces = _detected_surfaces(signals)
    project = _infer_project(item, labels, signals)
    capabilities = _capabilities_for(surfaces, signals)
    likely_repos = _likely_repos(surfaces, labels, workspace, signals)
    validation_needs = _validation_needs(
        surfaces=surfaces,
        capabilities=capabilities,
        acceptance_criteria=acceptance_criteria,
        signals=signals,
    )
    confidence = _confidence(
        fields=fields,
        labels=labels,
        acceptance_criteria=acceptance_criteria,
        comments=comments,
        attachments=attachments,
        surfaces=surfaces,
        capabilities=capabilities,
        likely_repos=likely_repos,
        project=project,
        signals=signals,
    )
    requires_confirmation = _requires_confirmation(confidence, surfaces, signals)
    if requires_confirmation:
        validation_needs = _dedupe([*validation_needs, "manual-confirmation"])

    return TaskUnderstandingReport(
        item_key=item.key,
        item_type=item.type,
        title=item.title,
        project=project,
        surfaces=surfaces,
        capabilities=capabilities,
        likely_repos=likely_repos,
        validation_needs=validation_needs,
        confidence=confidence,
        reasons=_reasons(
            surfaces=surfaces,
            project=project,
            likely_repos=likely_repos,
            acceptance_criteria=acceptance_criteria,
            signals=signals,
            requires_confirmation=requires_confirmation,
        ),
        signals=signals,
        requires_confirmation=requires_confirmation,
    )


def _text_fields(
    item: SprintItem,
    labels: list[str],
    acceptance_criteria: list[str],
    comments: list[str],
    attachments: list[str],
) -> dict[str, str]:
    return {
        "title": item.title,
        "description": item.description or "",
        "acceptance_criteria": "\n".join(acceptance_criteria),
        "labels": " ".join(labels),
        "comments": "\n".join(comments),
        "attachments": "\n".join(attachments),
        "parent_key": item.parent_key or "",
    }


def _collect_keyword_signals(
    fields: dict[str, str],
    keyword_groups: dict[str, tuple[str, ...]],
    signals: dict[str, list[str]],
) -> None:
    for group, keywords in keyword_groups.items():
        for field, raw in fields.items():
            for keyword in _keyword_hits(raw, keywords):
                _add_signal(signals, group, f"{field}:{keyword}")


def _collect_label_signals(labels: list[str], signals: dict[str, list[str]]) -> None:
    for label in labels:
        value = _prefixed_value(label, ("scope", "surface", "area", "type"))
        surface = _surface_from_label(value or label)
        if surface:
            _add_signal(signals, surface, f"labels:{label}")

        repo = _prefixed_value(label, ("repo", "repository", "service", "component"))
        if repo:
            _add_signal(signals, "repo", f"labels:{repo}")

        project = _prefixed_value(label, ("project", "project-key"))
        if project:
            _add_signal(signals, "project", f"labels:{project}")


def _collect_validation_signals(
    fields: dict[str, str],
    attachments: list[str],
    acceptance_criteria: list[str],
    signals: dict[str, list[str]],
) -> None:
    combined = "\n".join(fields.values())
    validation_keywords = (
        "pytest",
        "playwright",
        "unit test",
        "integration test",
        "e2e",
        "smoke",
        "coverage",
    )
    for keyword in _keyword_hits(combined, validation_keywords):
        _add_signal(signals, "validation", f"text:{keyword}")

    if acceptance_criteria:
        _add_signal(signals, "validation", "acceptance_criteria")

    for attachment in attachments:
        for keyword in _keyword_hits(attachment, ("screenshot", "image", "png", "jpg", "trace")):
            _add_signal(signals, "validation", f"attachments:{keyword}")


def _detected_surfaces(signals: dict[str, list[str]]) -> list[str]:
    surfaces = [
        surface for surface in _SURFACE_ORDER if surface != "full-stack" and surface in signals
    ]
    if "front" in surfaces and "back" in surfaces:
        insert_at = surfaces.index("back") + 1
        surfaces.insert(insert_at, "full-stack")
    return surfaces


def _infer_project(
    item: SprintItem,
    labels: list[str],
    signals: dict[str, list[str]],
) -> str | None:
    for label in labels:
        project = _prefixed_value(label, ("project", "project-key"))
        if project:
            return project

    for source_name, value in (("item_key", item.key), ("parent_key", item.parent_key or "")):
        project = _project_from_key(value)
        if project:
            _add_signal(signals, "project", f"{source_name}:{project}")
            return project
    return None


def _capabilities_for(surfaces: list[str], signals: dict[str, list[str]]) -> list[str]:
    capabilities: list[str] = []
    for surface in surfaces:
        capability = _SURFACE_CAPABILITIES.get(surface)
        if capability:
            capabilities.append(capability)

    for capability in _CAPABILITY_KEYWORDS:
        if capability in signals:
            capabilities.append(capability)

    if not capabilities:
        capabilities.append("implementation")
    return _dedupe(capabilities)


def _likely_repos(
    surfaces: list[str],
    labels: list[str],
    workspace: WorkspaceConfig | None,
    signals: dict[str, list[str]],
) -> list[str]:
    explicit = _explicit_repo_labels(labels)
    if workspace is not None:
        return _workspace_repos(surfaces, explicit, workspace, signals)

    if explicit:
        return explicit

    logical = [
        _LOGICAL_REPO_BY_SURFACE[surface]
        for surface in surfaces
        if surface in _LOGICAL_REPO_BY_SURFACE
    ]
    return _dedupe(logical)


def _workspace_repos(
    surfaces: list[str],
    explicit: list[str],
    workspace: WorkspaceConfig,
    signals: dict[str, list[str]],
) -> list[str]:
    if explicit:
        explicit_norm = {_normalize(repo): repo for repo in explicit}
        matched = [
            repo.name
            for repo in workspace.repos
            if _normalize(repo.name) in explicit_norm or _normalize(repo.path) in explicit_norm
        ]
        return matched or explicit

    repo_names: list[str] = []
    for repo in workspace.repos:
        if _repo_matches_surfaces(repo, surfaces):
            repo_names.append(repo.name)

    if "docs" in surfaces and not repo_names:
        repo_names.extend(
            repo.name
            for repo in workspace.repos
            if "doc" in _normalize(" ".join([repo.name, repo.path, repo.tech or ""]))
        )

    for repo_name in repo_names:
        _add_signal(signals, "repo", f"workspace:{repo_name}")
    return _dedupe(repo_names)


def _repo_matches_surfaces(repo: RepoConfig, surfaces: list[str]) -> bool:
    if "docs" in surfaces and "doc" in _normalize(" ".join([repo.name, repo.path])):
        return True
    for surface in surfaces:
        roles = _ROLE_BY_SURFACE.get(surface, set())
        if repo.role in roles:
            return True
    return False


def _validation_needs(
    *,
    surfaces: list[str],
    capabilities: list[str],
    acceptance_criteria: list[str],
    signals: dict[str, list[str]],
) -> list[str]:
    needs: list[str] = []
    if "front" in surfaces or "mobile" in surfaces:
        needs.extend(["playwright-e2e", "visual-smoke"])
    if "back" in surfaces:
        needs.extend(["unit-tests", "integration-tests", "api-contract-tests"])
    if "docs" in surfaces:
        needs.append("docs-smoke")
    if "infra" in surfaces:
        needs.extend(["configuration-validation", "pipeline-dry-run"])
    if "cli" in surfaces:
        needs.append("cli-smoke")
    if acceptance_criteria:
        needs.append("acceptance-criteria-check")
    if "bugfix" in capabilities:
        needs.append("regression-test")
    if any(signal.startswith("attachments:") for signal in signals.get("validation", [])):
        needs.append("screenshot-evidence")
    return _dedupe(needs)


def _confidence(
    *,
    fields: dict[str, str],
    labels: list[str],
    acceptance_criteria: list[str],
    comments: list[str],
    attachments: list[str],
    surfaces: list[str],
    capabilities: list[str],
    likely_repos: list[str],
    project: str | None,
    signals: dict[str, list[str]],
) -> float:
    score = 0.1 if fields["title"].strip() else 0.0
    score += 0.18 if surfaces else 0.0
    score += min(0.24, 0.035 * _routing_signal_count(signals))
    score += 0.08 if capabilities and capabilities != ["implementation"] else 0.0
    score += 0.1 if likely_repos else 0.0
    score += 0.1 if acceptance_criteria else 0.0
    score += 0.08 if len(fields["description"].strip()) >= 40 else 0.0
    score += 0.05 if labels else 0.0
    score += 0.04 if comments else 0.0
    score += 0.03 if attachments else 0.0
    score += 0.03 if project else 0.0
    if _has_uncertainty(fields.values()):
        score -= 0.18
    if not surfaces:
        score -= 0.12
    return round(min(0.95, max(0.05, score)), 2)


def _requires_confirmation(
    confidence: float,
    surfaces: list[str],
    signals: dict[str, list[str]],
) -> bool:
    return confidence < 0.55 or not surfaces or "uncertainty" in signals


def _reasons(
    *,
    surfaces: list[str],
    project: str | None,
    likely_repos: list[str],
    acceptance_criteria: list[str],
    signals: dict[str, list[str]],
    requires_confirmation: bool,
) -> list[str]:
    reasons: list[str] = []
    for surface in surfaces:
        if surface == "full-stack":
            reasons.append("matched both front and back routing signals")
            continue
        preview = ", ".join(signals.get(surface, [])[:3])
        reasons.append(f"matched {surface} surface signals" + (f": {preview}" if preview else ""))
    if project:
        reasons.append(f"inferred project {project}")
    if likely_repos:
        reasons.append(f"likely repo route: {', '.join(likely_repos)}")
    if acceptance_criteria:
        reasons.append("acceptance criteria provided")
    if signals.get("validation"):
        reasons.append("validation signals found")
    if requires_confirmation:
        reasons.append("requires confirmation because routing confidence is incomplete")
    return reasons


def _routing_signal_count(signals: dict[str, list[str]]) -> int:
    routing_keys = set(_SURFACE_KEYWORDS) | set(_CAPABILITY_KEYWORDS) | {"repo", "project"}
    return sum(len(values) for key, values in signals.items() if key in routing_keys)


def _surface_from_label(value: str) -> str | None:
    normalized = _normalize(value)
    if normalized in {"frontend", "front end", "front", "ui", "web"}:
        return "front"
    if normalized in {"backend", "back end", "back", "api"}:
        return "back"
    if normalized in {"fullstack", "full stack", "full-stack"}:
        return "full-stack"
    if normalized in {"docs", "documentation", "readme"}:
        return "docs"
    if normalized in {"infra", "infrastructure", "devops", "ci", "deploy"}:
        return "infra"
    if normalized in {"mobile", "ios", "android"}:
        return "mobile"
    if normalized in {"cli", "command"}:
        return "cli"
    return None


def _explicit_repo_labels(labels: list[str]) -> list[str]:
    repos: list[str] = []
    for label in labels:
        repo = _prefixed_value(label, ("repo", "repository", "service"))
        if repo:
            repos.append(repo)
    return _dedupe(repos)


def _prefixed_value(label: str, prefixes: Iterable[str]) -> str | None:
    parts = re.split(r"[:=]", label, maxsplit=1)
    if len(parts) != 2:
        return None
    prefix, value = parts[0].strip(), parts[1].strip()
    normalized_prefixes = {_normalize(item) for item in prefixes}
    if _normalize(prefix) in normalized_prefixes and value:
        return value
    return None


def _project_from_key(value: str) -> str | None:
    match = re.match(r"^([A-Z][A-Z0-9]+)-\d+$", value.strip())
    return match.group(1) if match else None


def _keyword_hits(raw: str, keywords: Iterable[str]) -> list[str]:
    normalized = _normalize(raw)
    if not normalized:
        return []
    hits: list[str] = []
    for keyword in keywords:
        normalized_keyword = _normalize(keyword)
        if not normalized_keyword:
            continue
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_keyword)}(?![a-z0-9])"
        if re.search(pattern, normalized):
            hits.append(keyword)
    return _dedupe(hits)


def _has_uncertainty(values: Iterable[str]) -> bool:
    return any(_keyword_hits(value, _UNCERTAINTY_KEYWORDS) for value in values)


def _add_signal(signals: dict[str, list[str]], key: str, value: str) -> None:
    bucket = signals.setdefault(key, [])
    if value not in bucket:
        bucket.append(value)


def _dedupe(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        key = _normalize(value)
        if key and key not in seen:
            seen.add(key)
            deduped.append(value)
    return deduped


def _normalize(value: str) -> str:
    ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", " ", ascii_value.lower()).strip()
