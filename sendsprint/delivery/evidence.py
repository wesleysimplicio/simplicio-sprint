"""Evidence collection: test results + screen captures, attached to the PR.

After simplicio applies a diff, SendSprint proves the work: it runs the test
command (capturing pass/fail + log) and, for front repos, captures a Playwright
screenshot of the screen. Artifacts are written under
``.sendsprint/evidence/<key>/`` in the worktree so they get committed on the
branch and can be embedded in the PR comment as markdown images.
"""

from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from sendsprint.models.reports import TestEvidence
from sendsprint.tech import TechFingerprint

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

EVIDENCE_DIRNAME = ".sendsprint/evidence"
LOG_TAIL_CHARS = 4000

EvidenceKind = Literal["unit", "e2e", "lint", "build", "screenshot", "log"]


@dataclass(frozen=True)
class EvidenceCommand:
    kind: EvidenceKind
    title: str
    command: str | None
    log_name: str
    skip_message: str = "no command configured; skipped"
    work_subdir: str = "."


class EvidenceCollector:
    """Collect test + screen evidence inside a worktree."""

    def __init__(
        self,
        work_dir: str | Path,
        *,
        item_key: str,
        runner: Runner = subprocess.run,
        test_timeout_s: int = 1200,
    ) -> None:
        self.work_dir = Path(work_dir)
        self.item_key = item_key
        self._runner = runner
        self._test_timeout_s = test_timeout_s

    @property
    def evidence_dir(self) -> Path:
        return self.work_dir / EVIDENCE_DIRNAME / self.item_key

    def collect_tests(self, test_command: str | None) -> TestEvidence:
        """Run the configured test command and capture the result + log."""
        title = test_command or "tests"
        return self.collect_command(EvidenceCommand("unit", title, test_command, "tests.log"))

    def collect_detected(self, fingerprint: TechFingerprint | None) -> list[TestEvidence]:
        """Run test/lint commands selected from a repository tech fingerprint."""
        commands = select_evidence_commands(fingerprint)
        if not commands:
            return [self.collect_tests(None)]
        return [self.collect_command(command) for command in commands]

    def collect_command(self, evidence_command: EvidenceCommand) -> TestEvidence:
        """Run one evidence command and capture the result + log."""
        if not evidence_command.command:
            return TestEvidence(
                kind=evidence_command.kind,
                title=evidence_command.title,
                passed=True,
                message=evidence_command.skip_message,
            )
        try:
            cwd = self._command_cwd(evidence_command)
            proc = self._runner(
                evidence_command.command,
                cwd=str(cwd),
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._test_timeout_s,
            )
        except FileNotFoundError:
            return TestEvidence(
                kind=evidence_command.kind,
                title=evidence_command.title,
                passed=False,
                message="test runner not found",
            )
        except subprocess.TimeoutExpired:
            return TestEvidence(
                kind=evidence_command.kind,
                title=evidence_command.title,
                passed=False,
                message=f"tests timed out after {self._test_timeout_s}s",
            )
        log = ((proc.stdout or "") + (proc.stderr or ""))[-LOG_TAIL_CHARS:]
        log_path = self._write(evidence_command.log_name, log)
        return TestEvidence(
            kind=evidence_command.kind,
            title=evidence_command.title,
            passed=proc.returncode == 0,
            path=str(log_path),
            message=f"exit {proc.returncode}",
        )

    def capture_screenshot(
        self,
        url: str,
        *,
        name: str = "screen",
        screenshot_fn: Callable[[str, str], bool] | None = None,
    ) -> TestEvidence | None:
        """Capture a screenshot of ``url`` with Playwright.

        ``screenshot_fn`` is injectable for tests. Returns ``None`` when neither
        Playwright nor an injected capturer is available.
        """
        if not url:
            return None
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        out = self.evidence_dir / f"{name}.png"
        capture = screenshot_fn or _playwright_screenshot
        try:
            ok = capture(url, str(out))
        except Exception as exc:  # pragma: no cover - environment dependent
            logger.warning("screenshot capture failed: %s", exc)
            return TestEvidence(
                kind="screenshot", title=url, passed=False, message=f"capture failed: {exc}"
            )
        if not ok:
            return TestEvidence(
                kind="screenshot",
                title=url,
                passed=False,
                message="playwright not available",
            )
        return TestEvidence(kind="screenshot", title=url, passed=True, path=str(out))

    def write_manifest(
        self,
        evidence: list[TestEvidence],
        *,
        steps_completed: list[str] | None = None,
        review_feedback: list[Any] | None = None,
    ) -> Path:
        """Write a stable manifest for PR comments and review-loop revisions."""
        artifacts = [_evidence_record(ev) for ev in _dedupe_evidence(evidence)]
        feedback = [_feedback_record(fb) for fb in _dedupe_feedback(review_feedback or [])]
        manifest = {
            "schema": "sendsprint.evidence/v1",
            "item_key": self.item_key,
            "status": "passed" if all(ev.passed for ev in evidence) else "failed",
            "steps_completed": steps_completed or [],
            "artifacts": artifacts,
            "review_feedback": feedback,
            "summary": {
                "passed": sum(1 for ev in evidence if ev.passed),
                "failed": sum(1 for ev in evidence if not ev.passed),
            },
        }
        return self._write("manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    def _write(self, name: str, content: str) -> Path:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        path = self.evidence_dir / name
        path.write_text(content, encoding="utf-8")
        return path

    def _command_cwd(self, evidence_command: EvidenceCommand) -> Path:
        if evidence_command.work_subdir in {"", "."}:
            return self.work_dir
        return self.work_dir / evidence_command.work_subdir


def select_evidence_commands(fingerprint: TechFingerprint | None) -> list[EvidenceCommand]:
    if fingerprint is None:
        return []
    techs = set(fingerprint.techs)
    commands: list[EvidenceCommand] = []

    if techs & {"python", "django", "fastapi", "flask"}:
        root = _root_for(fingerprint, "python", "django", "fastapi", "flask")
        commands.append(
            EvidenceCommand("unit", "pytest", "pytest -q", "tests-python.log", work_subdir=root)
        )
        commands.append(
            EvidenceCommand("lint", "ruff", "ruff check", "lint-ruff.log", work_subdir=root)
        )

    if "vitest" in techs:
        commands.append(
            EvidenceCommand(
                "unit",
                "vitest",
                "npx vitest run",
                "tests-vitest.log",
                work_subdir=_root_for(fingerprint, "vitest", "node"),
            )
        )
    elif "jest" in techs:
        commands.append(
            EvidenceCommand(
                "unit",
                "jest",
                "npx jest --ci",
                "tests-jest.log",
                work_subdir=_root_for(fingerprint, "jest", "node"),
            )
        )
    elif "angular" in techs:
        commands.append(
            EvidenceCommand(
                "unit",
                "angular",
                "npx ng test --watch=false",
                "tests-angular.log",
                work_subdir=_root_for(fingerprint, "angular", "node"),
            )
        )
    elif "nextjs" in techs:
        commands.append(
            EvidenceCommand(
                "unit",
                "next test",
                None,
                "tests-next.log",
                "Next.js test runner not detected; skipped",
                work_subdir=_root_for(fingerprint, "nextjs", "node"),
            )
        )

    if "nextjs" in techs:
        commands.append(
            EvidenceCommand(
                "lint",
                "next lint",
                "npx next lint",
                "lint-next.log",
                work_subdir=_root_for(fingerprint, "nextjs", "node"),
            )
        )
    elif "angular" in techs:
        commands.append(
            EvidenceCommand(
                "lint",
                "angular lint",
                "npx ng lint",
                "lint-angular.log",
                work_subdir=_root_for(fingerprint, "angular", "node"),
            )
        )
    elif "eslint" in techs or techs & {"vitest", "jest"}:
        commands.append(
            EvidenceCommand(
                "lint",
                "eslint",
                "npx eslint .",
                "lint-eslint.log",
                work_subdir=_root_for(fingerprint, "eslint", "vitest", "jest", "node"),
            )
        )

    if "go" in techs:
        root = _root_for(fingerprint, "go")
        commands.append(
            EvidenceCommand("unit", "go test", "go test ./...", "tests-go.log", work_subdir=root)
        )
        commands.append(
            EvidenceCommand("lint", "go vet", "go vet ./...", "lint-go-vet.log", work_subdir=root)
        )

    if "dotnet" in techs:
        commands.append(
            EvidenceCommand(
                "unit",
                "dotnet test",
                "dotnet test",
                "tests-dotnet.log",
                work_subdir=_root_for(fingerprint, "dotnet"),
            )
        )

    return commands


def _root_for(fingerprint: TechFingerprint, *techs: str) -> str:
    for tech in techs:
        root = fingerprint.tech_roots.get(tech)
        if root:
            return root
    return "."


def _playwright_screenshot(url: str, out_path: str) -> bool:
    """Capture ``url`` to ``out_path``. Returns False when Playwright is absent."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore[import-not-found]
    except ImportError:
        return False
    with sync_playwright() as pw:  # pragma: no cover - requires a browser
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=out_path, full_page=True)
        browser.close()
    return True


def _evidence_key(ev: TestEvidence) -> tuple[str, str, str, str, bool]:
    return (ev.kind, ev.title, ev.path or "", ev.message or "", ev.passed)


def _dedupe_evidence(evidence: list[TestEvidence]) -> list[TestEvidence]:
    seen: set[tuple[str, str, str, str, bool]] = set()
    result: list[TestEvidence] = []
    for ev in evidence:
        key = _evidence_key(ev)
        if key in seen:
            continue
        seen.add(key)
        result.append(ev)
    return result


def _feedback_key(feedback: Any) -> tuple[str, str, str, int | None, str]:
    return (
        str(getattr(feedback, "reviewer", "") or ""),
        str(getattr(feedback, "body", "") or "").strip(),
        str(getattr(feedback, "path", "") or ""),
        getattr(feedback, "line", None),
        str(getattr(feedback, "state", "") or ""),
    )


def _dedupe_feedback(feedback: list[Any]) -> list[Any]:
    seen: set[tuple[str, str, str, int | None, str]] = set()
    result: list[Any] = []
    for item in feedback:
        key = _feedback_key(item)
        if not key[1] or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _evidence_record(ev: TestEvidence) -> dict[str, Any]:
    payload = {
        "kind": ev.kind,
        "title": ev.title,
        "passed": ev.passed,
        "path": ev.path,
        "message": ev.message,
        "duration_ms": ev.duration_ms,
    }
    compact = json.dumps(payload, sort_keys=True, default=str)
    payload["id"] = hashlib.blake2b(compact.encode("utf-8"), digest_size=8).hexdigest()
    return {key: value for key, value in payload.items() if value is not None}


def _feedback_record(feedback: Any) -> dict[str, Any]:
    payload = {
        "reviewer": getattr(feedback, "reviewer", "unknown"),
        "body": str(getattr(feedback, "body", "") or "").strip(),
        "path": getattr(feedback, "path", None),
        "line": getattr(feedback, "line", None),
        "state": getattr(feedback, "state", "COMMENTED"),
    }
    compact = json.dumps(payload, sort_keys=True, default=str)
    payload["id"] = hashlib.blake2b(compact.encode("utf-8"), digest_size=8).hexdigest()
    return {key: value for key, value in payload.items() if value is not None}
