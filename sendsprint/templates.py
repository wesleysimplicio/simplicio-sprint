"""Validation template catalog for common project stacks."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from sendsprint.tech import TechFingerprint


class ValidationTemplate(BaseModel):
    """Stack-specific command recipe used by doctor and dry-run planning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    stacks: list[str] = Field(default_factory=list)
    role: str = "other"
    install: str | None = None
    lint: str | None = None
    typecheck: str | None = None
    build: str | None = None
    unit: str | None = None
    e2e: str | None = None
    security: str | None = None
    changelog: str | None = None
    release: str | None = None
    expectations: list[str] = Field(default_factory=list)

    def commands(self) -> list[str]:
        """Return non-empty validation commands in operator order."""
        return [
            cmd
            for cmd in (
                self.install,
                self.lint,
                self.typecheck,
                self.build,
                self.unit,
                self.e2e,
                self.security,
                self.changelog,
                self.release,
            )
            if cmd
        ]


TEMPLATE_CATALOG: tuple[ValidationTemplate, ...] = (
    ValidationTemplate(
        name="angular",
        stacks=["angular"],
        role="front",
        install="npm ci",
        lint="npx ng lint",
        typecheck="npx tsc --noEmit",
        build="npx ng build",
        unit="npx ng test --watch=false --browsers=ChromeHeadless",
        e2e="npx playwright test",
        security="npm audit --audit-level=high",
        changelog="update CHANGELOG.md when release-relevant",
        release="npm version <semver> --no-git-tag-version when package versioned",
        expectations=["Playwright traces/screenshots for UI flows"],
    ),
    ValidationTemplate(
        name="react",
        stacks=["react", "nextjs"],
        role="front",
        install="npm ci",
        lint="npx eslint . --max-warnings=0",
        typecheck="npx tsc --noEmit",
        build="npm run build",
        unit="npm test",
        e2e="npx playwright test",
        security="npm audit --audit-level=high",
        changelog="update CHANGELOG.md when release-relevant",
        release="npm version <semver> --no-git-tag-version when package versioned",
        expectations=["Framework-specific build must pass before PR"],
    ),
    ValidationTemplate(
        name="vue",
        stacks=["vue"],
        role="front",
        install="npm ci",
        lint="npx eslint . --max-warnings=0",
        typecheck="npx vue-tsc --noEmit",
        build="npm run build",
        unit="npm test -- --run",
        e2e="npx playwright test",
        security="npm audit --audit-level=high",
        changelog="update CHANGELOG.md when release-relevant",
        release="npm version <semver> --no-git-tag-version when package versioned",
        expectations=["Component and browser flows covered"],
    ),
    ValidationTemplate(
        name="nodejs-api",
        stacks=["node", "express", "nestjs", "bun", "deno"],
        role="api",
        install="npm ci",
        lint="npx eslint .",
        typecheck="npx tsc --noEmit",
        build="npm run build",
        unit="npm test",
        e2e="npx playwright test",
        security="npm audit --audit-level=high",
        changelog="update CHANGELOG.md when release-relevant",
        release="npm version <semver> --no-git-tag-version when package versioned",
        expectations=["API/library validation can skip browser E2E when no app URL exists"],
    ),
    ValidationTemplate(
        name="python",
        stacks=["python", "fastapi", "django", "flask"],
        role="api",
        install="python -m pip install -e .[dev]",
        lint="python -m ruff check .",
        typecheck="python -m mypy .",
        build="python -m build",
        unit="python -m pytest",
        e2e="npx playwright test",
        security="pip-audit --format=json",
        changelog="update CHANGELOG.md when release-relevant",
        release="python -m build",
        expectations=["Use pytest for core behavior and Playwright for exposed web flows"],
    ),
    ValidationTemplate(
        name="php",
        stacks=["php", "laravel"],
        role="api",
        install="composer install",
        lint="vendor/bin/phpcs",
        typecheck="vendor/bin/phpstan analyse",
        build=None,
        unit="vendor/bin/phpunit",
        e2e="npx playwright test",
        security="composer audit",
        changelog="update CHANGELOG.md when release-relevant",
        release="tag release after composer/package metadata is aligned",
    ),
    ValidationTemplate(
        name="dotnet",
        stacks=["dotnet"],
        role="api",
        install="dotnet restore",
        lint="dotnet format --verify-no-changes",
        typecheck="dotnet build --no-restore",
        build="dotnet build",
        unit="dotnet test",
        e2e="dotnet test --filter Category=E2E",
        security="dotnet list package --vulnerable",
        changelog="update CHANGELOG.md when release-relevant",
        release="dotnet pack",
    ),
    ValidationTemplate(
        name="mobile",
        stacks=["flutter", "ios", "android"],
        role="mobile",
        install="flutter pub get",
        lint="dart analyze",
        build="flutter build",
        unit="flutter test",
        e2e="flutter test integration_test",
        security="review mobile secrets and signing files",
        changelog="update CHANGELOG.md when release-relevant",
        release="follow app-store/internal release checklist",
    ),
    ValidationTemplate(
        name="monorepo",
        stacks=["monorepo"],
        role="workspace",
        install="npm ci",
        lint="npm run lint",
        typecheck="npm run typecheck",
        build="npm run build",
        unit="npm test",
        e2e="npx playwright test",
        security="npm audit --audit-level=high",
        changelog="update root CHANGELOG.md and package changelogs when present",
        release="run workspace release tooling",
        expectations=["Route checks per package/app before opening PR"],
    ),
)


def select_validation_template(
    fingerprint: TechFingerprint,
    repo_path: str | Path | None = None,
) -> ValidationTemplate:
    """Select the best validation template for a repo fingerprint."""
    repo = Path(repo_path).expanduser().resolve() if repo_path else None
    techs = set(fingerprint.techs)
    roles = set(fingerprint.roles)

    if repo and _looks_like_monorepo(repo):
        return _template("monorepo")
    for name in ("angular", "react", "vue"):
        if name in techs or (name == "react" and "nextjs" in techs):
            return _template(name)
    if techs & {"node", "express", "nestjs", "bun", "deno"}:
        return _template("nodejs-api")
    if techs & {"python", "fastapi", "django", "flask"}:
        return _template("python")
    if techs & {"php", "laravel"}:
        return _template("php")
    if "dotnet" in techs:
        return _template("dotnet")
    if techs & {"flutter", "ios", "android"} or "mobile" in roles:
        return _template("mobile")
    return _template("python")


def catalog() -> list[ValidationTemplate]:
    """Return all shipped validation templates."""
    return list(TEMPLATE_CATALOG)


def _template(name: str) -> ValidationTemplate:
    for item in TEMPLATE_CATALOG:
        if item.name == name:
            return item
    raise KeyError(name)


def _looks_like_monorepo(repo: Path) -> bool:
    if any((repo / marker).exists() for marker in ("pnpm-workspace.yaml", "lerna.json", "nx.json")):
        return True
    package_json = repo / "package.json"
    if package_json.exists():
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            data = {}
        if data.get("workspaces"):
            return True
    sibling_manifests = 0
    for base in ("apps", "packages", "services", "projects"):
        root = repo / base
        if not root.is_dir():
            continue
        sibling_manifests += sum(
            1
            for child in root.iterdir()
            if child.is_dir()
            and any((child / manifest).exists() for manifest in ("package.json", "pyproject.toml"))
        )
    return sibling_manifests >= 2
