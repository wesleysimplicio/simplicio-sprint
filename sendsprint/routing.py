"""Deterministic task-to-repository routing helpers."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from sendsprint.agents.story_task_planner import (
    BACK_REPO_ROLES,
    FRONT_REPO_ROLES,
    infer_item_scopes,
)
from sendsprint.models.sprint import SprintItem
from sendsprint.models.workspace import RepoConfig
from sendsprint.operational_memory import OperationalMemoryStore
from sendsprint.policy import AutonomyPolicy
from sendsprint.tech import TechFingerprint

Confidence = Literal["high", "medium", "low"]

ROLE_ALIASES: dict[str, set[str]] = {
    "front": {"front", "frontend", "web", "ui", "ux", "screen", "page", "component"},
    "api": {"api", "backend", "back", "service", "endpoint", "controller"},
    "back": {"api", "backend", "back", "service", "endpoint", "controller"},
    "mobile": {"mobile", "app", "android", "ios", "flutter"},
    "infra": {"infra", "platform", "devops", "terraform", "k8s", "docker", "deploy"},
    "lib": {"lib", "library", "sdk", "package", "shared"},
    "other": {"other"},
}
SURFACE_TO_ROLES: dict[str, set[str]] = {
    "front": {"front"},
    "frontend": {"front"},
    "web": {"front"},
    "ui": {"front"},
    "screen": {"front"},
    "page": {"front"},
    "api": {"api", "back"},
    "backend": {"api", "back"},
    "back": {"api", "back"},
    "service": {"api", "back"},
    "mobile": {"mobile"},
    "app": {"mobile"},
    "android": {"mobile"},
    "ios": {"mobile"},
    "infra": {"infra"},
    "platform": {"infra"},
    "devops": {"infra"},
    "library": {"lib"},
    "lib": {"lib"},
    "sdk": {"lib"},
}
GENERIC_CAPABILITY_TOKENS = {
    "api",
    "app",
    "back",
    "backend",
    "front",
    "frontend",
    "lib",
    "mobile",
    "repo",
    "service",
    "web",
}
RULE_RE = re.compile(
    r"^\s*[-*]?\s*"
    r"(repo|repository|project|scope|role|surface|capability|component|area)"
    r"\s*[:=]\s*(.+?)\s*$",
    re.IGNORECASE,
)


class RoutingConfidenceError(RuntimeError):
    """Raised when a low-confidence route would execute with side effects."""


class RepoRoutingProfile(BaseModel):
    """Normalized metadata used to compare a task with one workspace repo."""

    repo_label: str
    role: str | None = None
    exact_names: set[str] = Field(default_factory=set)
    project_terms: set[str] = Field(default_factory=set)
    capability_terms: set[str] = Field(default_factory=set)
    surface_terms: set[str] = Field(default_factory=set)
    role_terms: set[str] = Field(default_factory=set)


class TaskRoutingSignals(BaseModel):
    """Normalized explicit and inferred routing signals for one task."""

    repo_targets: set[str] = Field(default_factory=set)
    project_targets: set[str] = Field(default_factory=set)
    role_targets: set[str] = Field(default_factory=set)
    surface_targets: set[str] = Field(default_factory=set)
    capability_targets: set[str] = Field(default_factory=set)
    text_terms: set[str] = Field(default_factory=set)
    inferred_scopes: set[str] = Field(default_factory=set)
    has_task_understanding: bool = False


class RouteDecision(BaseModel):
    """Decision for one task/repo pair."""

    item_key: str
    repo_label: str
    match: bool
    confidence: Confidence
    reason: str
    signals: list[str] = Field(default_factory=list)

    def gate_message(self) -> str:
        return (
            f"{self.item_key}: low-confidence route to {self.repo_label} blocked "
            f"({self.reason})"
        )


def route_item_to_repo(
    item: SprintItem,
    repo_cfg: RepoConfig | None,
    fp: TechFingerprint,
    *,
    repo_path: Path | None = None,
    repo_role: str | None = None,
    task_understanding: Mapping[str, Any] | None = None,
    memory_facts: Mapping[str, str] | None = None,
    single_repo: bool = False,
) -> RouteDecision:
    """Route one sprint item to one repo with deterministic, auditable rules."""
    path = repo_path or Path(fp.repo_path)
    profile = build_repo_profile(
        repo_cfg,
        fp,
        repo_path=path,
        repo_role=repo_role,
        memory_facts=memory_facts
        if memory_facts is not None
        else load_routing_memory_facts(repo_cfg, path),
    )
    signals = build_task_signals(item, task_understanding=task_understanding)
    item_key = item.key or item.id

    repo_match = _targets_match(signals.repo_targets, profile.exact_names)
    project_match = _targets_match(signals.project_targets, profile.project_terms)
    if signals.repo_targets or signals.project_targets:
        if repo_match or project_match:
            return RouteDecision(
                item_key=item_key,
                repo_label=profile.repo_label,
                match=True,
                confidence="high",
                reason="explicit repo/project routing rule matched",
                signals=_signal_names(signals, "repo/project"),
            )
        return RouteDecision(
            item_key=item_key,
            repo_label=profile.repo_label,
            match=False,
            confidence="high",
            reason="explicit repo/project routing rule targets another repository",
            signals=_signal_names(signals, "repo/project"),
        )

    role_targets = _roles_from_targets(signals.role_targets | signals.surface_targets)
    if role_targets:
        if role_targets & _profile_roles(profile):
            return RouteDecision(
                item_key=item_key,
                repo_label=profile.repo_label,
                match=True,
                confidence="high",
                reason="explicit role/surface routing rule matched",
                signals=_signal_names(signals, "role/surface"),
            )
        if single_repo and not _specific_profile_roles(profile):
            return RouteDecision(
                item_key=item_key,
                repo_label=profile.repo_label,
                match=True,
                confidence="medium",
                reason="single repository target accepted explicit surface signal",
                signals=_signal_names(signals, "role/surface"),
            )
        return RouteDecision(
            item_key=item_key,
            repo_label=profile.repo_label,
            match=False,
            confidence="high",
            reason="explicit role/surface routing rule targets another repository",
            signals=_signal_names(signals, "role/surface"),
        )

    capability_match = _targets_match(signals.capability_targets, profile.capability_terms)
    if signals.capability_targets:
        if capability_match:
            return RouteDecision(
                item_key=item_key,
                repo_label=profile.repo_label,
                match=True,
                confidence="high",
                reason="explicit capability routing rule matched",
                signals=_signal_names(signals, "capability"),
            )
        return RouteDecision(
            item_key=item_key,
            repo_label=profile.repo_label,
            match=False,
            confidence="high",
            reason="explicit capability routing rule targets another repository",
            signals=_signal_names(signals, "capability"),
        )

    text_capability_match = _targets_match(signals.text_terms, _capability_text_terms(profile))
    if text_capability_match:
        confidence: Confidence = "high" if signals.has_task_understanding else "medium"
        reason = (
            "task understanding matched repo capability"
            if signals.has_task_understanding
            else "task text matched repo capability"
        )
        return RouteDecision(
            item_key=item_key,
            repo_label=profile.repo_label,
            match=True,
            confidence=confidence,
            reason=reason,
            signals=_signal_names(signals, "capability-text"),
        )

    inferred_roles = _roles_from_targets(signals.inferred_scopes)
    if inferred_roles:
        if inferred_roles & _profile_roles(profile):
            return RouteDecision(
                item_key=item_key,
                repo_label=profile.repo_label,
                match=True,
                confidence="medium",
                reason="backwards-compatible role fallback matched inferred scope",
                signals=_signal_names(signals, "inferred-scope"),
            )
        if single_repo and not _specific_profile_roles(profile):
            return RouteDecision(
                item_key=item_key,
                repo_label=profile.repo_label,
                match=True,
                confidence="medium",
                reason="single repository target accepted inferred scope",
                signals=_signal_names(signals, "inferred-scope"),
            )
        return RouteDecision(
            item_key=item_key,
            repo_label=profile.repo_label,
            match=False,
            confidence="medium",
            reason="inferred scope targets another repository role",
            signals=_signal_names(signals, "inferred-scope"),
        )

    if single_repo:
        return RouteDecision(
            item_key=item_key,
            repo_label=profile.repo_label,
            match=True,
            confidence="medium",
            reason="single repository target requires no cross-repo routing",
            signals=["single-repo"],
        )

    return RouteDecision(
        item_key=item_key,
        repo_label=profile.repo_label,
        match=True,
        confidence="low",
        reason="no explicit repo, capability, surface, or role signal",
        signals=["fallback"],
    )


def build_repo_profile(
    repo_cfg: RepoConfig | None,
    fp: TechFingerprint,
    *,
    repo_path: Path | None = None,
    repo_role: str | None = None,
    memory_facts: Mapping[str, str] | None = None,
) -> RepoRoutingProfile:
    """Build normalized repo routing metadata from workspace, tech, and memory."""
    path = repo_path or Path(fp.repo_path)
    repo_label = repo_cfg.name if repo_cfg else path.name
    role = repo_role or (repo_cfg.role if repo_cfg else None) or fp.primary_role
    exact_names = _term_set(repo_label, path.name, path.stem)
    project_terms = _term_set(repo_label, path.name, path.stem, *path.parts[-3:])
    capability_terms = _term_set(repo_label, path.name, path.stem, *path.parts[-3:])
    surface_terms: set[str] = set()
    role_terms: set[str] = set()

    if role:
        role_terms.update(_term_set(role, *ROLE_ALIASES.get(role, set())))
        surface_terms.update(ROLE_ALIASES.get(role, set()))
    if repo_cfg and repo_cfg.tech:
        capability_terms.update(_term_set(repo_cfg.tech))
    capability_terms.update(_term_set(*fp.techs, *fp.package_managers))
    for fp_role in fp.roles:
        role_terms.update(_term_set(fp_role, *ROLE_ALIASES.get(fp_role, set())))
        surface_terms.update(ROLE_ALIASES.get(fp_role, set()))

    _apply_memory_facts(
        memory_facts or {},
        exact_names=exact_names,
        project_terms=project_terms,
        capability_terms=capability_terms,
        surface_terms=surface_terms,
        role_terms=role_terms,
    )

    return RepoRoutingProfile(
        repo_label=repo_label,
        role=role,
        exact_names=exact_names,
        project_terms=project_terms,
        capability_terms=capability_terms,
        surface_terms=surface_terms,
        role_terms=role_terms,
    )


def build_task_signals(
    item: SprintItem,
    *,
    task_understanding: Mapping[str, Any] | None = None,
) -> TaskRoutingSignals:
    """Extract explicit labels, structured understanding, and text terms."""
    signals = TaskRoutingSignals()
    for label in item.labels:
        _add_rule(signals, label)

    for text in (item.title, item.description or "", item.acceptance_criteria or ""):
        signals.text_terms.update(_term_set(text))
        for line in text.splitlines():
            _add_rule(signals, line)

    understanding = task_understanding or _model_extra_mapping(item, "task_understanding")
    if understanding is None:
        understanding = _model_extra_mapping(item, "understanding")
    if understanding:
        signals.has_task_understanding = True
        _add_understanding(signals, understanding)

    signals.inferred_scopes.update(infer_item_scopes(item))
    return signals


def load_routing_memory_facts(
    repo_cfg: RepoConfig | None,
    repo_path: Path,
) -> dict[str, str]:
    """Read repo routing overrides from local operational memory when present."""
    names = [repo_cfg.name if repo_cfg else None, repo_path.name, str(repo_path)]
    roots = [repo_path, repo_path.parent]
    for root in roots:
        store = OperationalMemoryStore(root)
        for name in names:
            if not name:
                continue
            if store.path_for(name).exists():
                return dict(store.load_or_create(name).facts)
    return {}


def confidence_gate_warnings(
    decisions: list[RouteDecision],
    policy: AutonomyPolicy,
) -> list[str]:
    """Warn in plan-only mode and block side effects for low-confidence routes."""
    warnings: list[str] = []
    for decision in decisions:
        if not decision.match or decision.confidence != "low":
            continue
        message = decision.gate_message()
        if policy.allows("write-files"):
            raise RoutingConfidenceError(message)
        warnings.append(message)
    return warnings


def confidence_for_item(
    item: SprintItem,
    repo_role: str | None,
    fp: TechFingerprint,
) -> tuple[Confidence, str]:
    """Compatibility wrapper for callers that only need confidence text."""
    decision = route_item_to_repo(item, None, fp, repo_role=repo_role, single_repo=False)
    return decision.confidence, decision.reason


def _add_rule(signals: TaskRoutingSignals, raw: str) -> None:
    match = RULE_RE.match(raw.strip())
    if not match:
        return
    key = match.group(1).lower()
    values = _split_values(match.group(2))
    if key in {"repo", "repository"}:
        signals.repo_targets.update(values)
    elif key == "project":
        signals.project_targets.update(values)
    elif key in {"scope", "role"}:
        signals.role_targets.update(values)
    elif key == "surface":
        signals.surface_targets.update(values)
    else:
        signals.capability_targets.update(values)


def _add_understanding(signals: TaskRoutingSignals, understanding: Mapping[str, Any]) -> None:
    for key, value in understanding.items():
        normalized_key = _normalize_phrase(str(key))
        values = _values_from_unknown(value)
        if normalized_key in {"repo", "repository", "target repo", "target repository"}:
            signals.repo_targets.update(values)
        elif normalized_key in {"project", "product"}:
            signals.text_terms.update(values)
        elif normalized_key in {"scope", "role"}:
            signals.role_targets.update(values)
        elif normalized_key in {"surface", "surfaces", "ui surface"}:
            signals.surface_targets.update(values)
        elif normalized_key in {"capability", "capabilities", "component", "area", "domain"}:
            signals.text_terms.update(values)


def _apply_memory_facts(
    facts: Mapping[str, str],
    *,
    exact_names: set[str],
    project_terms: set[str],
    capability_terms: set[str],
    surface_terms: set[str],
    role_terms: set[str],
) -> None:
    for key, value in facts.items():
        key_terms = _term_set(key)
        values = _split_values(value)
        if not values:
            continue
        if {"routing", "route"} & key_terms or key_terms & {
            "aliases",
            "capabilities",
            "capability",
            "labels",
            "project",
            "projects",
            "repo",
            "role",
            "scope",
            "surface",
            "surfaces",
        }:
            if key_terms & {"repo", "aliases", "alias", "labels"}:
                exact_names.update(values)
                project_terms.update(_expand_terms(values))
            if key_terms & {"project", "projects"}:
                project_terms.update(_expand_terms(values))
            if key_terms & {"capability", "capabilities", "component", "area", "domain"}:
                capability_terms.update(_expand_terms(values))
            if key_terms & {"surface", "surfaces", "scope"}:
                surface_terms.update(_expand_terms(values))
                role_terms.update(_roles_from_targets(values))
            if key_terms & {"role"}:
                role_terms.update(_expand_terms(values))
                role_terms.update(_roles_from_targets(values))


def _profile_roles(profile: RepoRoutingProfile) -> set[str]:
    roles = _roles_from_targets(profile.role_terms)
    if profile.role:
        roles.update(_roles_from_targets({profile.role}))
    return roles


def _specific_profile_roles(profile: RepoRoutingProfile) -> set[str]:
    return _profile_roles(profile) - {"other"}


def _roles_from_targets(targets: set[str]) -> set[str]:
    roles: set[str] = set()
    for target in targets:
        normalized = _normalize_phrase(target)
        if normalized in FRONT_REPO_ROLES:
            roles.add("front")
        if normalized in BACK_REPO_ROLES:
            roles.add("api")
            roles.add("back")
        if normalized in {"mobile", "infra", "lib"}:
            roles.add(normalized)
        roles.update(SURFACE_TO_ROLES.get(normalized, set()))
        for role, aliases in ROLE_ALIASES.items():
            if normalized in aliases:
                roles.add(role)
    return roles


def _capability_text_terms(profile: RepoRoutingProfile) -> set[str]:
    terms = set(profile.project_terms | profile.capability_terms | profile.surface_terms)
    return {term for term in terms if term not in GENERIC_CAPABILITY_TOKENS and len(term) > 2}


def _targets_match(targets: set[str], terms: set[str]) -> bool:
    if not targets or not terms:
        return False
    expanded_terms = _expand_terms(terms)
    compact_terms = {_compact(term) for term in expanded_terms}
    for target in _expand_terms(targets):
        if target in expanded_terms or _compact(target) in compact_terms:
            return True
        target_tokens = _term_set(target)
        if target_tokens and target_tokens <= expanded_terms:
            return True
    return False


def _signal_names(signals: TaskRoutingSignals, fallback: str) -> list[str]:
    names: list[str] = []
    if signals.repo_targets:
        names.append("repo")
    if signals.project_targets:
        names.append("project")
    if signals.role_targets:
        names.append("role")
    if signals.surface_targets:
        names.append("surface")
    if signals.capability_targets:
        names.append("capability")
    if signals.inferred_scopes:
        names.append("inferred-scope")
    if signals.has_task_understanding:
        names.append("task-understanding")
    return names or [fallback]


def _model_extra_mapping(item: SprintItem, key: str) -> Mapping[str, Any] | None:
    extra = getattr(item, "model_extra", None)
    if isinstance(extra, Mapping):
        value = extra.get(key)
        if isinstance(value, Mapping):
            return value
    value = getattr(item, key, None)
    return value if isinstance(value, Mapping) else None


def _values_from_unknown(value: Any) -> set[str]:
    if value is None:
        return set()
    if isinstance(value, str):
        return _split_values(value)
    if isinstance(value, Mapping):
        terms: set[str] = set()
        for item in value.values():
            terms.update(_values_from_unknown(item))
        return terms
    if isinstance(value, list | tuple | set):
        terms = set()
        for item in value:
            terms.update(_values_from_unknown(item))
        return terms
    return _split_values(str(value))


def _split_values(value: str) -> set[str]:
    return {
        normalized
        for part in re.split(r"[,;|\n]", value)
        if (normalized := _normalize_phrase(part))
    }


def _expand_terms(values: set[str]) -> set[str]:
    expanded: set[str] = set()
    for value in values:
        normalized = _normalize_phrase(value)
        if not normalized:
            continue
        expanded.add(normalized)
        expanded.update(_term_set(normalized))
    return expanded


def _term_set(*values: str) -> set[str]:
    terms: set[str] = set()
    for value in values:
        normalized = _normalize_phrase(value)
        if not normalized:
            continue
        terms.add(normalized)
        terms.update(token for token in normalized.split() if token)
    return terms


def _normalize_phrase(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_value.lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", lowered)).strip()


def _compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


__all__ = [
    "Confidence",
    "RouteDecision",
    "RoutingConfidenceError",
    "TaskRoutingSignals",
    "build_repo_profile",
    "build_task_signals",
    "confidence_for_item",
    "confidence_gate_warnings",
    "load_routing_memory_facts",
    "route_item_to_repo",
]
