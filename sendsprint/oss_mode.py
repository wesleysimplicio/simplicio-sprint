"""Open-source contributor mode helpers."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

OssGateName = Literal[
    "snapshot",
    "candidate",
    "dedupe",
    "validate",
    "publish",
    "monitor",
    "rework",
    "learn",
]
OssGateStatus = Literal["passed", "blocked", "needs-review", "skipped"]
OssCandidateStrategy = Literal["new-pr", "review", "salvage", "abandon"]
OssPrivacyLevel = Literal["internal", "public", "sensitive"]

OSS_PUBLIC_PR_SECTION_GROUPS: tuple[tuple[str, ...], ...] = (
    ("What does this PR do?",),
    ("Problem", "Root cause"),
    ("What this changes", "Fix"),
    ("Why this shape",),
    ("Tests",),
)
OSS_PUBLIC_PR_SECTIONS = [
    "What does this PR do?",
    "Problem / Root cause",
    "What this changes / Fix",
    "Why this shape",
    "Tests",
]
OSS_PRIVATE_PR_MARKERS = (
    "agent volume",
    "agent-volume",
    "codex_home",
    "dedupe gate",
    "duplicate gate",
    "enospc",
    "internal scoring",
    "missing venv",
    "private procedure",
    "scouting",
    "subagent",
    "worktree failure",
    "$codex_home",
    "c:\\users",
)
OSS_MINIMAL_ACTIVE_FIX_MARKERS = (
    "competing with",
    "minimal",
    "minimal one-line",
    "one-line",
    "same fix",
    "smaller",
)


class OssContributorMode(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    has_contributing: bool = False
    has_code_of_conduct: bool = False
    has_security: bool = False
    has_pr_template: bool = False
    prefer_fork_workflow: bool = True


def detect_oss_mode(repo_path: str | Path) -> OssContributorMode:
    root = Path(repo_path)
    pr_template_dir = root / ".github" / "PULL_REQUEST_TEMPLATE"
    return OssContributorMode(
        has_contributing=(root / "CONTRIBUTING.md").is_file(),
        has_code_of_conduct=(root / "CODE_OF_CONDUCT.md").is_file(),
        has_security=(root / "SECURITY.md").is_file(),
        has_pr_template=(root / ".github" / "PULL_REQUEST_TEMPLATE.md").is_file()
        or (pr_template_dir.is_dir() and any(pr_template_dir.glob("*.md"))),
        prefer_fork_workflow=True,
    )


class OssRepositorySnapshot(BaseModel):
    """Small public-safe snapshot of an OSS target before selecting work."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repo_path: str
    conventions: OssContributorMode
    default_branch: str = "main"
    active_refs: list[str] = Field(default_factory=list)
    closed_refs: list[str] = Field(default_factory=list)
    active_paths: list[str] = Field(default_factory=list)
    test_commands: list[str] = Field(default_factory=list)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OssContributionCandidate(BaseModel):
    """One potential OSS contribution after scope selection."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    repo: str
    title: str
    issue_url: str | None = None
    strategy: OssCandidateStrategy = "new-pr"
    changed_paths: list[str] = Field(default_factory=list)
    public_summary: str = ""
    dedupe_markers: list[str] = Field(default_factory=list)
    root_cause_markers: list[str] = Field(default_factory=list)
    risk_level: Literal["low", "medium", "high"] = "low"


class OssDedupeMatch(BaseModel):
    """Duplicate-risk evidence that can block or redirect a candidate."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ref: str
    reason: str
    match_type: Literal[
        "open-pr",
        "closed-pr",
        "issue",
        "branch",
        "memory",
        "minimal-fix",
        "path",
        "title",
    ]
    blocking: bool = True


class OssValidationPlan(BaseModel):
    """Validation required before publishing a public OSS PR."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    commands: list[str] = Field(default_factory=list)
    manual_checks: list[str] = Field(default_factory=list)
    requires_before_publish: bool = True
    passed: bool = False


class OssPublishPlan(BaseModel):
    """Public PR publishing plan that hides internal selection procedure."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    dry_run: bool = True
    blocked: bool = True
    reason: str = ""
    public_sections: list[str] = Field(default_factory=lambda: list(OSS_PUBLIC_PR_SECTIONS))


class OssMonitorPlan(BaseModel):
    """Review and CI follow-up plan for a published contribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    refs: list[str] = Field(default_factory=list)
    ci_triage_minutes: int = 30
    review_response_hours: int = 24


class OssReworkPlan(BaseModel):
    """Minimal rework plan generated from CI/review failures."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    failures: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    needs_revalidation: bool = True


class OssGateDecision(BaseModel):
    """Internal gate result. Do not copy this model verbatim into public PRs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    gate: OssGateName
    status: OssGateStatus
    reason: str
    evidence: list[str] = Field(default_factory=list)


class OssLearningRecord(BaseModel):
    """Compact reusable learning from one OSS contribution cycle."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_id: str
    repo: str
    title: str
    decision: str
    signal: str
    result: str
    reusable_rule: str
    privacy: OssPrivacyLevel = "internal"
    related_refs: list[str] = Field(default_factory=list)
    learned_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class OssContributionPlan(BaseModel):
    """End-to-end OSS contribution state for SendSprint automation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    snapshot: OssRepositorySnapshot
    candidate: OssContributionCandidate
    decisions: list[OssGateDecision] = Field(default_factory=list)
    validation: OssValidationPlan | None = None
    publish: OssPublishPlan | None = None


def build_oss_snapshot(repo_path: str | Path) -> OssRepositorySnapshot:
    root = Path(repo_path).expanduser().resolve()
    return OssRepositorySnapshot(
        repo_path=str(root),
        conventions=detect_oss_mode(root),
        default_branch=_default_branch(root),
        test_commands=_default_test_commands(root),
    )


def build_oss_candidate(
    snapshot: OssRepositorySnapshot,
    *,
    title: str | None = None,
    issue_url: str | None = None,
    changed_paths: list[str] | None = None,
    dedupe_markers: list[str] | None = None,
    root_cause_markers: list[str] | None = None,
    strategy: OssCandidateStrategy = "new-pr",
) -> OssContributionCandidate:
    resolved_title = title or issue_url or "open-source contribution"
    markers = [resolved_title.lower()]
    if issue_url:
        markers.append(issue_url.lower())
        markers.extend(_issue_ref_markers(issue_url))
    markers.extend(marker.lower() for marker in dedupe_markers or [])
    markers.extend(marker.lower() for marker in root_cause_markers or [])
    return OssContributionCandidate(
        candidate_id=_slug(resolved_title),
        repo=snapshot.repo_path,
        title=resolved_title,
        issue_url=issue_url,
        strategy=strategy,
        changed_paths=changed_paths or [],
        dedupe_markers=_unique_markers(markers),
        root_cause_markers=_unique_markers(root_cause_markers or []),
    )


def find_oss_dedupe_matches(
    candidate: OssContributionCandidate,
    existing_refs: list[str],
    memory_markers: dict[str, str] | None = None,
) -> list[OssDedupeMatch]:
    matches: list[OssDedupeMatch] = []
    markers = _candidate_markers(candidate)
    for ref in existing_refs:
        haystack = ref.lower()
        if any(marker and (marker in haystack or haystack in marker) for marker in markers):
            match_type: Literal["minimal-fix", "title"] = (
                "minimal-fix" if _describes_minimal_active_fix(haystack) else "title"
            )
            reason = (
                "active minimal fix already covers this issue or root cause; "
                "route to review or consolidation"
                if match_type == "minimal-fix"
                else "candidate overlaps an existing public ref"
            )
            matches.append(
                OssDedupeMatch(
                    ref=ref,
                    reason=reason,
                    match_type=match_type,
                )
            )
    for marker, ref in (memory_markers or {}).items():
        haystack = marker.lower()
        if any(item and (item in haystack or haystack in item) for item in markers):
            matches.append(
                OssDedupeMatch(
                    ref=ref,
                    reason="candidate overlaps local operational memory",
                    match_type="memory",
                )
            )
    return matches


def audit_oss_public_pr_body(body: str) -> OssGateDecision:
    """Validate public PR text without exposing internal contribution procedure."""

    headings = _markdown_headings(body)
    missing_groups = [
        " | ".join(group)
        for group in OSS_PUBLIC_PR_SECTION_GROUPS
        if not any(section.lower() in headings for section in group)
    ]
    lowered_body = body.lower()
    leaked_markers = [marker for marker in OSS_PRIVATE_PR_MARKERS if marker.lower() in lowered_body]
    evidence = [
        *(f"missing section: {group}" for group in missing_groups),
        *(f"private marker: {marker}" for marker in leaked_markers),
    ]
    if evidence:
        return OssGateDecision(
            gate="publish",
            status="blocked",
            reason="public PR body is missing required sections or contains private procedure",
            evidence=evidence,
        )
    return OssGateDecision(
        gate="publish",
        status="passed",
        reason="public PR body follows the OSS contribution standard",
    )


def check_oss_dedupe(
    candidate: OssContributionCandidate,
    existing_refs: list[str],
    memory_markers: dict[str, str] | None = None,
) -> OssGateDecision:
    matches = find_oss_dedupe_matches(candidate, existing_refs, memory_markers)
    if matches:
        return OssGateDecision(
            gate="dedupe",
            status="blocked",
            reason="duplicate-risk match found; prefer review, salvage, or a different slice",
            evidence=[match.ref for match in matches],
        )
    return OssGateDecision(
        gate="dedupe",
        status="passed",
        reason="no matching active, closed, or remembered refs were found",
    )


def build_oss_validation_plan(
    snapshot: OssRepositorySnapshot,
    changed_paths: list[str],
) -> OssValidationPlan:
    commands = list(snapshot.test_commands)
    suffixes = {Path(path).suffix.lower() for path in changed_paths}
    manual_checks: list[str] = []
    if suffixes and suffixes <= {".md", ".mdx", ".txt"}:
        manual_checks.append("Review rendered documentation diff.")
    if any(suffix in {".ts", ".tsx", ".js", ".jsx"} for suffix in suffixes):
        manual_checks.append("Confirm frontend behavior in the affected route or component.")
    return OssValidationPlan(commands=commands, manual_checks=manual_checks)


def build_oss_publish_plan(
    candidate: OssContributionCandidate,
    validation_plan: OssValidationPlan,
    *,
    dry_run: bool = True,
    public_body: str | None = None,
) -> OssPublishPlan:
    if validation_plan.requires_before_publish and (
        not validation_plan.commands or not validation_plan.passed
    ):
        return OssPublishPlan(
            candidate_id=candidate.candidate_id,
            dry_run=dry_run,
            blocked=True,
            reason="validation evidence is required before publishing",
        )
    if public_body is not None:
        audit = audit_oss_public_pr_body(public_body)
        if audit.status == "blocked":
            return OssPublishPlan(
                candidate_id=candidate.candidate_id,
                dry_run=dry_run,
                blocked=True,
                reason=f"public PR body does not meet OSS standard: {audit.reason}",
            )
    return OssPublishPlan(
        candidate_id=candidate.candidate_id,
        dry_run=dry_run,
        blocked=False,
        reason="ready to prepare public PR body",
    )


def build_oss_monitor_plan(
    publish_plan: OssPublishPlan,
    refs: list[str] | None = None,
) -> OssMonitorPlan:
    return OssMonitorPlan(candidate_id=publish_plan.candidate_id, refs=refs or [])


def build_oss_rework_plan(monitor_plan: OssMonitorPlan, failures: list[str]) -> OssReworkPlan:
    actions = []
    for failure in failures:
        lowered = failure.lower()
        if "ci" in lowered or "test" in lowered:
            actions.append(
                "Inspect failing check logs, patch minimally, and rerun focused validation."
            )
        elif "review" in lowered or "change" in lowered:
            actions.append("Address maintainer feedback with the smallest acceptable diff.")
        else:
            actions.append("Classify blocker and decide whether to patch, document, or close.")
    return OssReworkPlan(candidate_id=monitor_plan.candidate_id, failures=failures, actions=actions)


def build_oss_learning_record(
    candidate: OssContributionCandidate,
    decisions: list[OssGateDecision],
    *,
    result: str,
    reusable_rule: str,
    privacy: OssPrivacyLevel = "internal",
) -> OssLearningRecord:
    signal = "; ".join(decision.reason for decision in decisions if decision.status != "skipped")
    return OssLearningRecord(
        candidate_id=candidate.candidate_id,
        repo=candidate.repo,
        title=candidate.title,
        decision=candidate.strategy,
        signal=signal,
        result=result,
        reusable_rule=reusable_rule,
        privacy=privacy,
        related_refs=[ref for decision in decisions for ref in decision.evidence],
    )


def _default_branch(root: Path) -> str:
    head = root / ".git" / "HEAD"
    if not head.is_file():
        return "main"
    content = head.read_text(encoding="utf-8", errors="ignore").strip()
    prefix = "ref: refs/heads/"
    if content.startswith(prefix):
        return content.removeprefix(prefix)
    return "main"


def _default_test_commands(root: Path) -> list[str]:
    commands: list[str] = []
    if (root / "pyproject.toml").is_file() and (root / "tests").is_dir():
        commands.append("python -m pytest tests/ -q")
    if (root / "package.json").is_file():
        commands.append("npm test")
    if (root / "web" / "package.json").is_file():
        commands.append("npm --prefix web test")
    return commands


def _candidate_markers(candidate: OssContributionCandidate) -> set[str]:
    markers = [
        candidate.title,
        *(candidate.dedupe_markers or []),
        *(candidate.root_cause_markers or []),
        *(candidate.changed_paths or []),
    ]
    if candidate.issue_url:
        markers.append(candidate.issue_url)
        markers.extend(_issue_ref_markers(candidate.issue_url))
    return {marker.lower() for marker in _unique_markers(markers) if marker}


def _describes_minimal_active_fix(ref: str) -> bool:
    return any(marker in ref for marker in OSS_MINIMAL_ACTIVE_FIX_MARKERS)


def _issue_ref_markers(issue_url: str) -> list[str]:
    parts = [part for part in issue_url.rstrip("/").split("/") if part]
    if len(parts) < 2 or not parts[-1].isdigit():
        return []
    issue_number = parts[-1]
    return [f"#{issue_number}", f"{parts[-2]}/{issue_number}"]


def _markdown_headings(body: str) -> set[str]:
    headings: set[str] = set()
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped.startswith("#"):
            continue
        title = stripped.lstrip("#").strip().lower()
        if title:
            headings.add(title)
    return headings


def _unique_markers(markers: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for marker in markers:
        normalized = marker.lower().strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


def _slug(value: str) -> str:
    slug = "".join(char.lower() if char.isalnum() else "-" for char in value).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug[:80] or "open-source-contribution"
