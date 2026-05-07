"""SecurityReviewer: flag-only static analysis. Reports findings, does NOT auto-fix."""

from __future__ import annotations

import json
import logging
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..models.reports import SecurityFinding, StepReport
from ..tech import TechFingerprint

logger = logging.getLogger(__name__)

SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)(api[_-]?key|apikey)\s*[:=]\s*['\"][A-Za-z0-9_\-]{16,}['\"]", "hardcoded-api-key"),
    (r"(?i)(secret|password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{8,}['\"]", "hardcoded-secret"),
    (r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}", "bearer-token-in-source"),
    (r"-----BEGIN\s+(RSA\s+)?PRIVATE\sKEY-----", "private-key-in-source"),
    (r"(?i)(aws_access_key_id|aws_secret_access_key)\s*=\s*\S+", "aws-credential"),
    (r"ghp_[A-Za-z0-9]{36}", "github-pat"),
    (r"sk-[A-Za-z0-9]{20,}", "openai-key"),
    (r"https://hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+", "slack-webhook"),
    (r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}", "jwt-in-source"),
    (r"xox[bporas]-[A-Za-z0-9\-]{10,}", "slack-token"),
    (r"(?i)(mongodb(\+srv)?://)[^\s'\"]+", "database-connection-string"),
    (r"(?i)(postgres(ql)?://)[^\s'\"]+", "database-connection-string"),
]

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    "bin", "obj", "target", ".next", ".angular", "coverage",
}

SCAN_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".cs", ".java", ".go", ".rs",
    ".rb", ".php", ".yaml", ".yml", ".json", ".toml", ".env", ".cfg",
    ".sh", ".bash", ".zsh", ".tf", ".hcl",
}

MAX_FILE_SIZE = 512_000


class SecurityReviewer:
    """Scans source for common security issues. Flag-only — never modifies files."""

    def __init__(self, repo_path: str | Path, fingerprint: TechFingerprint) -> None:
        self.repo = Path(repo_path).resolve()
        self.fp = fingerprint

    def scan(self) -> StepReport:
        report = StepReport(step=6, name="security-review", repo=str(self.repo))
        report.started_at = datetime.now(tz=timezone.utc)
        report.status = "running"

        findings: list[SecurityFinding] = []
        findings.extend(self._scan_secrets())
        findings.extend(self._scan_env_files())
        findings.extend(self._scan_dependency_audit())

        report.findings = findings
        report.status = (
            "ok" if not any(f.severity in ("high", "critical") for f in findings) else "failed"
        )
        report.message = f"{len(findings)} finding(s) flagged"
        report.finished_at = datetime.now(tz=timezone.utc)
        return report

    def _scan_secrets(self) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for fpath in self._iter_source_files():
            try:
                text = fpath.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = str(fpath.relative_to(self.repo))
            for lineno, line in enumerate(text.splitlines(), 1):
                for pattern, rule in SECRET_PATTERNS:
                    if re.search(pattern, line):
                        findings.append(
                            SecurityFinding(
                                rule=rule,
                                severity="high",
                                file=rel,
                                line=lineno,
                                message=f"potential secret detected: {rule}",
                                recommendation="move to env var or secrets manager",
                            )
                        )
        return findings

    def _scan_env_files(self) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        for env in self.repo.rglob(".env*"):
            if env.is_dir() or env.name == ".env.example":
                continue
            if any(p in IGNORE_DIRS for p in env.parts):
                continue
            gitignore = self.repo / ".gitignore"
            ignored = False
            if gitignore.exists():
                try:
                    gi_text = gitignore.read_text(encoding="utf-8", errors="ignore")
                    if env.name in gi_text or ".env" in gi_text:
                        ignored = True
                except OSError:
                    pass
            if not ignored:
                findings.append(
                    SecurityFinding(
                        rule="env-not-gitignored",
                        severity="medium",
                        file=str(env.relative_to(self.repo)),
                        message=f"{env.name} may not be gitignored",
                        recommendation="add to .gitignore",
                    )
                )
        return findings

    def _scan_dependency_audit(self) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        if (self.repo / "package-lock.json").exists() or (self.repo / "package.json").exists():
            findings.extend(self._npm_audit())
        if (self.repo / "requirements.txt").exists() or (self.repo / "pyproject.toml").exists():
            findings.extend(self._pip_audit())
        if (self.repo / "Cargo.toml").exists():
            findings.extend(self._cargo_audit())
        return findings

    def _npm_audit(self) -> list[SecurityFinding]:
        try:
            result = subprocess.run(
                ["npm", "audit", "--json"],
                cwd=str(self.repo),
                capture_output=True,
                text=True,
                timeout=60,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        if result.returncode == 0:
            return []
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return []
        vulns = data.get("vulnerabilities") or {}
        out: list[SecurityFinding] = []
        for pkg, info in list(vulns.items())[:20]:
            sev = (info.get("severity") or "medium").lower()
            mapped = {"low": "low", "moderate": "medium", "high": "high", "critical": "critical"}
            out.append(
                SecurityFinding(
                    rule="npm-audit",
                    severity=mapped.get(sev, "medium"),  # type: ignore[arg-type]
                    file="package.json",
                    message=f"{pkg}: {info.get('title', sev)} vulnerability",
                    recommendation=f"npm audit fix or upgrade {pkg}",
                )
            )
        return out

    def _pip_audit(self) -> list[SecurityFinding]:
        try:
            result = subprocess.run(
                ["pip-audit", "--format=json", "--desc"],
                cwd=str(self.repo),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        if result.returncode == 0:
            return []
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return []
        out: list[SecurityFinding] = []
        for vuln in (data if isinstance(data, list) else data.get("dependencies", []))[:20]:
            name = vuln.get("name", "unknown")
            for v in vuln.get("vulns", []):
                vid = v.get("id", "")
                desc = v.get("description", "")[:200]
                sev = v.get("fix_versions") and "high" or "medium"
                out.append(
                    SecurityFinding(
                        rule="pip-audit",
                        severity=sev,
                        file="requirements.txt",
                        message=f"{name}: {vid} — {desc}",
                        recommendation=f"upgrade {name}",
                    )
                )
        return out

    def _cargo_audit(self) -> list[SecurityFinding]:
        try:
            result = subprocess.run(
                ["cargo", "audit", "--json"],
                cwd=str(self.repo),
                capture_output=True,
                text=True,
                timeout=120,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return []
        if result.returncode == 0:
            return []
        try:
            data = json.loads(result.stdout)
        except (json.JSONDecodeError, ValueError):
            return []
        out: list[SecurityFinding] = []
        for vuln in data.get("vulnerabilities", {}).get("list", [])[:20]:
            advisory = vuln.get("advisory", {})
            pkg = advisory.get("package", "unknown")
            title = advisory.get("title", "vulnerability")
            out.append(
                SecurityFinding(
                    rule="cargo-audit",
                    severity="high",
                    file="Cargo.toml",
                    message=f"{pkg}: {title}",
                    recommendation=f"upgrade {pkg}",
                )
            )
        return out

    def _iter_source_files(self):
        for fpath in self.repo.rglob("*"):
            if fpath.is_dir():
                continue
            if any(p in IGNORE_DIRS for p in fpath.parts):
                continue
            if fpath.suffix not in SCAN_EXTENSIONS:
                continue
            try:
                if fpath.stat().st_size > MAX_FILE_SIZE:
                    continue
            except OSError:
                continue
            yield fpath
