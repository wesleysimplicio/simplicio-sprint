"""Evidence collection: test results + screen captures, attached to the PR.

After simplicio applies a diff, SendSprint proves the work: it runs the test
command (capturing pass/fail + log) and, for front repos, captures a Playwright
screenshot of the screen. Artifacts are written under
``.sendsprint/evidence/<key>/`` in the worktree so they get committed on the
branch and can be embedded in the PR comment as markdown images.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from sendsprint.models.reports import TestEvidence

logger = logging.getLogger(__name__)

Runner = Callable[..., subprocess.CompletedProcess[str]]

EVIDENCE_DIRNAME = ".sendsprint/evidence"
LOG_TAIL_CHARS = 4000


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
        if not test_command:
            return TestEvidence(
                kind="unit",
                title="tests",
                passed=True,
                message="no test command configured; skipped",
            )
        try:
            proc = self._runner(
                test_command,
                cwd=str(self.work_dir),
                shell=True,
                capture_output=True,
                text=True,
                timeout=self._test_timeout_s,
            )
        except FileNotFoundError:
            return TestEvidence(
                kind="unit", title=test_command, passed=False, message="test runner not found"
            )
        except subprocess.TimeoutExpired:
            return TestEvidence(
                kind="unit",
                title=test_command,
                passed=False,
                message=f"tests timed out after {self._test_timeout_s}s",
            )
        log = ((proc.stdout or "") + (proc.stderr or ""))[-LOG_TAIL_CHARS:]
        log_path = self._write("tests.log", log)
        return TestEvidence(
            kind="unit",
            title=test_command,
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

    def _write(self, name: str, content: str) -> Path:
        self.evidence_dir.mkdir(parents=True, exist_ok=True)
        path = self.evidence_dir / name
        path.write_text(content, encoding="utf-8")
        return path


def _playwright_screenshot(url: str, out_path: str) -> bool:
    """Capture ``url`` to ``out_path``. Returns False when Playwright is absent."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False
    with sync_playwright() as pw:  # pragma: no cover - requires a browser
        browser = pw.chromium.launch()
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.screenshot(path=out_path, full_page=True)
        browser.close()
    return True
