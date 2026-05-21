"""TestRunner: unit + E2E (Playwright) with screenshot evidence."""

from __future__ import annotations

import logging
import os
import re
import shlex
import subprocess
import time
import urllib.error
import urllib.request
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

from sendsprint.frontend_flows import FrontendRoute, discover_frontend_flows, is_front_repo
from sendsprint.models.workspace import (
    FrontendFlowConfig,
    PlaywrightAutoFlowsConfig,
    RepoConfig,
)

from ..models.reports import StepReport, TestEvidence
from ..tech import TechFingerprint

logger = logging.getLogger(__name__)

OPTIONAL_RUNTIMES = {"bun", "deno"}

UNIT_COMMANDS: dict[str, list[str]] = {
    "angular": ["npx", "ng", "test", "--watch=false", "--browsers=ChromeHeadless"],
    "react": ["npx", "react-scripts", "test", "--watchAll=false"],
    "nextjs": ["npm", "test", "--", "--passWithNoTests"],
    "vue": ["npm", "test", "--", "--run"],
    "nestjs": ["npm", "test"],
    "node": ["npm", "test"],
    "bun": ["bun", "test"],
    "deno": ["deno", "test", "--quiet"],
    "dotnet": ["dotnet", "test"],
    "spring": ["mvn", "test"],
    "java": ["mvn", "test"],
    "python": ["pytest", "--tb=short", "-q"],
    "django": ["python", "manage.py", "test"],
    "fastapi": ["pytest", "--tb=short", "-q"],
    "flask": ["pytest", "--tb=short", "-q"],
    "go": ["go", "test", "./..."],
    "rust": ["cargo", "test"],
    "flutter": ["flutter", "test"],
    "ruby": ["bundle", "exec", "rspec"],
    "php": ["vendor/bin/phpunit"],
    "laravel": ["vendor/bin/phpunit"],
}

E2E_COMMANDS: dict[str, list[str]] = {
    "angular": ["npx", "playwright", "test"],
    "react": ["npx", "playwright", "test"],
    "nextjs": ["npx", "playwright", "test"],
    "vue": ["npx", "playwright", "test"],
    "nestjs": ["npx", "playwright", "test"],
    "node": ["npx", "playwright", "test"],
    "dotnet": ["dotnet", "test", "--filter", "Category=E2E"],
    "flutter": ["flutter", "test", "integration_test"],
}

SCREENSHOT_DIR = "sendsprint-evidence"


class DevServerStartError(RuntimeError):
    """Raised when an auto-flow dev server cannot be started or reached."""


class TestRunner:
    """Runs unit tests + Playwright E2E with screenshot capture."""

    def __init__(
        self,
        repo_path: str | Path,
        fingerprint: TechFingerprint,
        *,
        custom_unit_cmd: str | None = None,
        custom_e2e_cmd: str | None = None,
        repo_config: RepoConfig | None = None,
        frontend_config: FrontendFlowConfig | None = None,
        auto_flows_config: PlaywrightAutoFlowsConfig | None = None,
    ) -> None:
        self.repo = Path(repo_path).resolve()
        self.fp = fingerprint
        self.custom_unit_cmd = custom_unit_cmd
        self.custom_e2e_cmd = custom_e2e_cmd
        self.repo_config = repo_config
        self.frontend_config = frontend_config or FrontendFlowConfig()
        self.auto_flows_config = auto_flows_config or PlaywrightAutoFlowsConfig()
        self.evidence_dir = self.repo / SCREENSHOT_DIR
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    def run_unit(self) -> StepReport:
        report = StepReport(step=5, name="unit-tests", repo=str(self.repo))
        report.status = "running"
        if self.custom_unit_cmd:
            cmd = self.custom_unit_cmd.split()
        else:
            tech = self.fp.primary_tech
            cmd_list = UNIT_COMMANDS.get(tech) if tech else None
            if not cmd_list:
                report.status = "skipped"
                report.message = f"no unit test command for tech={tech}"
                return report
            cmd = list(cmd_list)
        return self._exec(cmd, report, kind="unit")

    def run_e2e(self) -> StepReport:
        report = StepReport(step=5, name="e2e-tests", repo=str(self.repo))
        report.status = "running"
        if self.custom_e2e_cmd:
            cmd = self.custom_e2e_cmd.split()
            return self._exec(cmd, report, kind="e2e")
        if self._should_run_frontend_auto_flows():
            return self.run_frontend_flows()
        else:
            tech = self.fp.primary_tech
            cmd_list = E2E_COMMANDS.get(tech) if tech else None
            if not cmd_list:
                report.status = "skipped"
                report.message = (
                    f"frontend auto-flow skipped because repo is not front; "
                    f"no e2e command for tech={tech}"
                )
                return report
            cmd = list(cmd_list)
        pw_args = ["--reporter=json", f"--output={self.evidence_dir}"]
        if cmd[0] == "npx" and cmd[1] == "playwright":
            cmd.extend(pw_args)
        return self._exec(cmd, report, kind="e2e")

    def run_frontend_flows(self) -> StepReport:
        report = StepReport(step=5, name="frontend-flow-smoke", repo=str(self.repo))
        report.status = "running"
        if not self._should_run_frontend_auto_flows():
            report.status = "skipped"
            report.message = "frontend auto-flow skipped because repo is not front or disabled"
            return report

        discovery = discover_frontend_flows(self.repo)
        max_routes = self._frontend_max_routes()
        routes = discovery.routes[:max_routes]
        if not routes:
            report.status = "skipped"
            report.message = "frontend auto-flow skipped because no routes were discovered"
            return report

        spec = self._write_frontend_flow_spec(routes)
        report.evidence.append(
            TestEvidence(
                kind="e2e",
                title="frontend route inventory",
                passed=True,
                path=str(spec.relative_to(self.repo)),
                message=f"{len(routes)} route(s) discovered for generated Playwright smoke",
            )
        )
        cmd = [
            "npx",
            "playwright",
            "test",
            str(spec.relative_to(self.repo)),
            "--reporter=json",
            f"--output={self.evidence_dir}",
        ]
        base_url = self._frontend_base_url()
        env = {"BASE_URL": base_url} if base_url else None
        try:
            server = self._start_dev_server(base_url)
        except DevServerStartError as exc:
            report.status = "failed"
            report.message = str(exc)
            report.finished_at = datetime.now(tz=UTC)
            return report
        try:
            return self._exec(
                cmd,
                report,
                kind="e2e",
                env=env,
                timeout=self._frontend_timeout(),
            )
        finally:
            if server is not None and server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()

    def run_all(self) -> list[StepReport]:
        return [self.run_unit(), self.run_e2e()]

    def _exec(
        self,
        cmd: list[str],
        report: StepReport,
        *,
        kind: str,
        env: dict[str, str] | None = None,
        timeout: int = 600,
    ) -> StepReport:
        report.started_at = datetime.now(tz=UTC)
        known_artifacts = self._known_evidence_paths()
        try:
            child_env = os.environ.copy()
            if env:
                child_env.update(env)
            result = subprocess.run(
                cmd,
                cwd=str(self.repo),
                capture_output=True,
                text=True,
                timeout=timeout,
                env=child_env,
            )
            passed = result.returncode == 0
            report.status = "ok" if passed else "failed"
            report.message = (
                result.stdout[:3000] if passed else result.stderr[:3000] or result.stdout[:3000]
            )
            report.evidence.append(
                TestEvidence(
                    kind=kind,  # type: ignore[arg-type]
                    title=f"{kind} tests",
                    passed=passed,
                    message=report.message,
                )
            )
        except FileNotFoundError:
            if cmd and cmd[0] in OPTIONAL_RUNTIMES:
                report.status = "skipped"
                report.message = f"{cmd[0]} not installed"
            else:
                report.status = "failed"
                report.message = f"command not found: {cmd[0]}"
        except subprocess.TimeoutExpired:
            report.status = "failed"
            report.message = f"timeout after {timeout}s: {' '.join(cmd)}"
        finally:
            self._collect_screenshots(report, known_artifacts)
        report.finished_at = datetime.now(tz=UTC)
        return report

    def _known_evidence_paths(self) -> set[Path]:
        return {path.resolve() for path in self._iter_evidence_files()}

    def _iter_evidence_files(self) -> Iterable[Path]:
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            yield from self.evidence_dir.rglob(ext)

    def _collect_screenshots(self, report: StepReport, known_artifacts: set[Path]) -> None:
        for file_path in self._iter_evidence_files():
            resolved = file_path.resolve()
            if resolved in known_artifacts:
                continue
            report.evidence.append(
                TestEvidence(
                    kind="screenshot",
                    title=file_path.name,
                    passed=report.status == "ok",
                    path=str(file_path.relative_to(self.repo)),
                )
            )

    def _should_run_frontend_auto_flows(self) -> bool:
        if not self.auto_flows_config.enabled:
            return False
        if self.frontend_config.flow_inventory == "off":
            return False
        if not self.frontend_config.generate_route_smokes:
            return False
        return is_front_repo(repo=self.repo_config, fingerprint=self.fp)

    def _frontend_base_url(self) -> str:
        return (
            self.frontend_config.base_url
            or self.auto_flows_config.frontend_base_url
            or os.environ.get("BASE_URL")
            or "http://127.0.0.1:3000"
        )

    def _frontend_timeout(self) -> int:
        if "timeout_seconds" in self.frontend_config.model_fields_set:
            return self.frontend_config.timeout_seconds
        return self.auto_flows_config.timeout_seconds

    def _frontend_max_routes(self) -> int:
        if "max_routes" in self.frontend_config.model_fields_set:
            return self.frontend_config.max_routes
        return self.auto_flows_config.max_routes

    def _start_dev_server(self, base_url: str) -> subprocess.Popen[str] | None:
        command = (
            self.frontend_config.dev_server_command or self.auto_flows_config.dev_server_command
        )
        if not command:
            return None
        args = shlex.split(command, posix=os.name != "nt")
        try:
            server = subprocess.Popen(
                args,
                cwd=str(self.repo),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except OSError as exc:
            raise DevServerStartError(
                f"could not start frontend dev server: {command} ({exc})"
            ) from exc
        if not self._wait_for_base_url(base_url):
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
            raise DevServerStartError(
                f"frontend dev server did not become ready at {base_url} within "
                f"{self._frontend_timeout()}s"
            )
        return server

    def _wait_for_base_url(self, base_url: str) -> bool:
        deadline = time.monotonic() + self._frontend_timeout()
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(base_url, timeout=1):
                    return True
            except urllib.error.HTTPError:
                return True
            except OSError:
                time.sleep(0.5)
        return False

    def _write_frontend_flow_spec(self, routes: list[FrontendRoute]) -> Path:
        spec_path = self.evidence_dir / "sendsprint-auto-flows.spec.ts"
        lines = [
            "import { test, expect } from '@playwright/test';",
            "",
            "test.describe('SendSprint generated frontend route smokes', () => {",
        ]
        for route in routes:
            path = _playwright_path(route.path)
            title = _js_string(f"{route.path} from {route.source}")
            screenshot_name = _screenshot_name(route.path)
            lines.extend(
                [
                    f"  test({title}, async ({{ page }}, testInfo) => {{",
                    f"    await page.goto({_js_string(path)});",
                    "    await expect(page.locator('body')).not.toBeEmpty();",
                ]
            )
            if self.frontend_config.screenshot_evidence:
                lines.append(
                    "    await page.screenshot({ "
                    f"path: testInfo.outputPath({_js_string(screenshot_name)}), "
                    "fullPage: true });"
                )
            lines.append("  });")
        lines.append("});")
        spec_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return spec_path


def _playwright_path(path: str) -> str:
    cleaned = re.sub(r":([A-Za-z0-9_]+)\\*", "sample", path)
    cleaned = re.sub(r":([A-Za-z0-9_]+)", "sample", cleaned)
    return cleaned or "/"


def _screenshot_name(path: str) -> str:
    slug = path.strip("/") or "home"
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", slug).strip("-") or "route"
    return f"{slug}.png"


def _js_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"
