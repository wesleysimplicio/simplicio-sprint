"""Pre-publish diff verifier — reads a local diff, relates it to the plan/task,
flags unexpected files, large changes, and missing tests, and returns a
structured verdict for consumption by :class:`DeliveryQualityGate`.

Issue: #99
"""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.plan_verifier import VerifiablePlan

# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class DiffVerdict(StrEnum):
    """Outcome of the diff verification."""

    passed = "pass"
    warn = "warn"
    block = "block"


class FindingType(StrEnum):
    """Category of a diff finding."""

    unexpected_file = "unexpected_file"
    large_change = "large_change"
    missing_test = "missing_test"
    generated_artifact = "generated_artifact"


class FindingSeverity(StrEnum):
    """How critical a finding is."""

    info = "info"
    warning = "warning"
    blocking = "blocking"


class DiffFinding(BaseModel):
    """Single finding produced by the diff verifier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    file_path: str
    finding_type: FindingType
    severity: FindingSeverity
    message: str


class DiffReport(BaseModel):
    """Full report produced by :class:`DiffVerifier`."""

    model_config = ConfigDict(extra="forbid")

    verdict: DiffVerdict
    findings: list[DiffFinding] = Field(default_factory=list)
    summary: str = ""


# ---------------------------------------------------------------------------
# Diff parsing helpers
# ---------------------------------------------------------------------------

_DIFF_FILE_RE = re.compile(r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE)

# Generated / artifact patterns that should not normally appear in a PR.
_GENERATED_PATTERNS: tuple[str, ...] = (
    ".min.js",
    ".min.css",
    ".map",
    ".pyc",
    "__pycache__",
    "node_modules/",
    "dist/",
    ".egg-info/",
    ".whl",
    ".tar.gz",
    "package-lock.json",
    "yarn.lock",
    "poetry.lock",
    "Pipfile.lock",
)

# Default threshold for "large change" (added lines in a single file).
_LARGE_CHANGE_THRESHOLD = 300


def _parse_changed_files(diff_text: str) -> list[str]:
    """Extract unique file paths touched by the diff."""
    files: list[str] = []
    seen: set[str] = set()
    for match in _DIFF_FILE_RE.finditer(diff_text):
        path = match.group(2)
        if path not in seen:
            seen.add(path)
            files.append(path)
    return files


def _count_added_lines_per_file(diff_text: str) -> dict[str, int]:
    """Return {filepath: added_line_count} from a unified diff."""
    counts: dict[str, int] = {}
    current_file: str | None = None
    for line in diff_text.splitlines():
        file_match = _DIFF_FILE_RE.match(line)
        if file_match:
            current_file = file_match.group(2)
            counts.setdefault(current_file, 0)
            continue
        if current_file is not None and line.startswith("+") and not line.startswith("+++"):
            counts[current_file] = counts.get(current_file, 0) + 1
    return counts


def _is_test_file(path: str) -> bool:
    """Heuristic: file lives under tests/ or has test_ / _test prefix/suffix."""
    p = PurePosixPath(path)
    parts = p.parts
    name = p.stem
    return (
        "tests" in parts
        or "test" in parts
        or "__tests__" in parts
        or name.startswith("test_")
        or name.endswith("_test")
        or name.endswith(".test")
        or name.endswith(".spec")
    )


def _is_source_file(path: str) -> bool:
    """Heuristic: file is a code source file (not config, docs, etc.)."""
    ext = PurePosixPath(path).suffix.lower()
    return ext in {
        ".py",
        ".js",
        ".ts",
        ".tsx",
        ".jsx",
        ".go",
        ".rs",
        ".java",
        ".kt",
        ".cs",
        ".rb",
        ".php",
        ".swift",
        ".dart",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
    }


# ---------------------------------------------------------------------------
# DiffVerifier
# ---------------------------------------------------------------------------


class DiffVerifier:
    """Verify a diff against an optional plan before publish.

    Parameters
    ----------
    large_change_threshold:
        Number of added lines in a single file above which a ``large_change``
        finding is emitted (default 300).
    """

    def __init__(
        self,
        *,
        large_change_threshold: int = _LARGE_CHANGE_THRESHOLD,
    ) -> None:
        self.large_change_threshold = large_change_threshold

    # -- individual checks ---------------------------------------------------

    def check_unexpected_files(
        self,
        changed_files: list[str],
        plan: VerifiablePlan | None = None,
    ) -> list[DiffFinding]:
        """Flag files not listed in the plan's *target_files*."""
        if plan is None or not plan.target_files:
            return []

        findings: list[DiffFinding] = []
        for path in changed_files:
            if not any(target in path or path in target for target in plan.target_files):
                findings.append(
                    DiffFinding(
                        file_path=path,
                        finding_type=FindingType.unexpected_file,
                        severity=FindingSeverity.warning,
                        message=f"file not listed in plan target_files: {path}",
                    )
                )
        return findings

    def check_large_changes(
        self,
        diff_text: str,
    ) -> list[DiffFinding]:
        """Flag files where added lines exceed the threshold."""
        counts = _count_added_lines_per_file(diff_text)
        findings: list[DiffFinding] = []
        for path, added in counts.items():
            if added > self.large_change_threshold:
                findings.append(
                    DiffFinding(
                        file_path=path,
                        finding_type=FindingType.large_change,
                        severity=FindingSeverity.warning,
                        message=f"{added} lines added (threshold {self.large_change_threshold})",
                    )
                )
        return findings

    def check_missing_tests(
        self,
        changed_files: list[str],
    ) -> list[DiffFinding]:
        """Flag source files that were changed without a corresponding test file."""
        source_files = [f for f in changed_files if _is_source_file(f) and not _is_test_file(f)]
        test_files = {f for f in changed_files if _is_test_file(f)}

        if not source_files:
            return []

        has_any_test = len(test_files) > 0
        if has_any_test:
            return []

        findings: list[DiffFinding] = []
        for path in source_files:
            findings.append(
                DiffFinding(
                    file_path=path,
                    finding_type=FindingType.missing_test,
                    severity=FindingSeverity.blocking,
                    message="source file changed but no test files in diff",
                )
            )
        return findings

    def check_generated_artifacts(
        self,
        changed_files: list[str],
    ) -> list[DiffFinding]:
        """Flag files that look like generated artifacts."""
        findings: list[DiffFinding] = []
        for path in changed_files:
            for pattern in _GENERATED_PATTERNS:
                if pattern in path:
                    findings.append(
                        DiffFinding(
                            file_path=path,
                            finding_type=FindingType.generated_artifact,
                            severity=FindingSeverity.warning,
                            message=f"looks like a generated artifact ({pattern})",
                        )
                    )
                    break
        return findings

    # -- aggregate -----------------------------------------------------------

    def verify(
        self,
        diff_text: str,
        plan: VerifiablePlan | None = None,
    ) -> DiffReport:
        """Run all checks and produce a :class:`DiffReport`.

        Verdict logic:
        - Any *blocking* finding -> ``block``
        - Any *warning* finding -> ``warn``
        - Otherwise -> ``pass``
        """
        changed_files = _parse_changed_files(diff_text)

        findings: list[DiffFinding] = []
        findings.extend(self.check_unexpected_files(changed_files, plan))
        findings.extend(self.check_large_changes(diff_text))
        findings.extend(self.check_missing_tests(changed_files))
        findings.extend(self.check_generated_artifacts(changed_files))

        # Determine verdict
        has_blocking = any(f.severity == FindingSeverity.blocking for f in findings)
        has_warning = any(f.severity == FindingSeverity.warning for f in findings)

        if has_blocking:
            verdict = DiffVerdict.block
        elif has_warning:
            verdict = DiffVerdict.warn
        else:
            verdict = DiffVerdict.passed

        # Build summary
        if not findings:
            summary = f"diff looks clean — {len(changed_files)} file(s) changed"
        else:
            by_type: dict[str, int] = {}
            for f in findings:
                by_type[f.finding_type.value] = by_type.get(f.finding_type.value, 0) + 1
            parts = [f"{count} {ftype}" for ftype, count in by_type.items()]
            summary = f"{len(findings)} finding(s): {', '.join(parts)}"

        return DiffReport(verdict=verdict, findings=findings, summary=summary)
