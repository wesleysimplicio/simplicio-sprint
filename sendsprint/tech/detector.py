"""Detect a repository's technology stack from filesystem markers."""

from __future__ import annotations

import contextlib
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

KNOWN_TECHS = {
    "dotnet": "C# / .NET",
    "node": "Node.js",
    "bun": "Bun",
    "deno": "Deno",
    "angular": "Angular",
    "react": "React",
    "vue": "Vue",
    "nextjs": "Next.js",
    "nestjs": "NestJS",
    "express": "Express",
    "vitest": "Vitest",
    "jest": "Jest",
    "eslint": "ESLint",
    "python": "Python",
    "django": "Django",
    "fastapi": "FastAPI",
    "flask": "Flask",
    "java": "Java",
    "spring": "Spring Boot",
    "go": "Go",
    "rust": "Rust",
    "flutter": "Flutter",
    "ios": "iOS / Swift",
    "android": "Android",
    "ruby": "Ruby",
    "php": "PHP",
    "laravel": "Laravel",
    "terraform": "Terraform",
    "docker": "Docker",
    "k8s": "Kubernetes",
    "ansible": "Ansible",
}

FRONT_TECHS = {"angular", "react", "vue", "nextjs"}
BACK_TECHS = {
    "dotnet",
    "node",
    "bun",
    "deno",
    "express",
    "nestjs",
    "python",
    "django",
    "fastapi",
    "flask",
    "java",
    "spring",
    "go",
    "rust",
    "ruby",
    "php",
    "laravel",
}
MOBILE_TECHS = {"flutter", "ios", "android"}
INFRA_TECHS = {"terraform", "docker", "k8s", "ansible"}
MONOREPO_CONTAINER_DIRS = {
    "apps",
    "clients",
    "frontend",
    "packages",
    "services",
}
SCAN_DIR_SKIP = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".sendsprint",
    ".tox",
    ".venv",
    "dist",
    "node_modules",
    "venv",
}
STACK_MARKER_FILES = {
    "package.json",
    "deno.json",
    "deno.jsonc",
    "deno.lock",
    "bun.lockb",
    "bunfig.toml",
    "pyproject.toml",
    "requirements.txt",
    "setup.py",
    "Pipfile",
    "go.mod",
    "Cargo.toml",
    "pubspec.yaml",
    "Gemfile",
    "composer.json",
    "Dockerfile",
    "Podfile",
    "angular.json",
    "build.gradle",
    "build.gradle.kts",
}
STACK_MARKER_GLOBS = {
    ".eslintrc.*",
    "eslint.config.*",
    "jest.config.*",
    "vitest.config.*",
}


class TechFingerprint(BaseModel):
    repo_path: str
    roles: list[str] = Field(default_factory=list)
    techs: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    signals: dict[str, str] = Field(default_factory=dict)
    tech_roots: dict[str, str] = Field(default_factory=dict)

    @property
    def primary_tech(self) -> str | None:
        return self.techs[0] if self.techs else None

    @property
    def primary_role(self) -> str | None:
        return self.roles[0] if self.roles else None


def _add(fp_techs: list[str], fp_signals: dict[str, str], tech: str, marker: str) -> None:
    if tech not in fp_techs:
        fp_techs.append(tech)
    fp_signals[marker] = tech


def _scan_bun(repo: Path, techs: list[str], signals: dict[str, str], pms: list[str]) -> None:
    """Detect Bun runtime (bun.lockb or bunfig.toml).

    Wins over generic ``node`` when both markers coexist (AC-2 of TASK-001).
    Frameworks declared in ``package.json`` (Angular/React/Vue/etc.) are still
    layered on top by ``_scan_node`` because Bun can run them.
    """
    if (repo / "bun.lockb").exists():
        _add(techs, signals, "bun", "bun.lockb")
        if "bun" not in pms:
            pms.append("bun")
    elif (repo / "bunfig.toml").exists():
        _add(techs, signals, "bun", "bunfig.toml")
        if "bun" not in pms:
            pms.append("bun")


def _scan_deno(repo: Path, techs: list[str], signals: dict[str, str], pms: list[str]) -> None:
    """Detect Deno runtime (deno.json, deno.jsonc, or deno.lock)."""
    for marker in ("deno.json", "deno.jsonc", "deno.lock"):
        if (repo / marker).exists():
            _add(techs, signals, "deno", marker)
            if "deno" not in pms:
                pms.append("deno")
            return


def _scan_node(repo: Path, techs: list[str], signals: dict[str, str], pms: list[str]) -> None:
    pkg = repo / "package.json"
    if not pkg.exists():
        return
    if "npm" not in pms:
        pms.append("npm")
    if (repo / "yarn.lock").exists() and "yarn" not in pms:
        pms.append("yarn")
    if (repo / "pnpm-lock.yaml").exists() and "pnpm" not in pms:
        pms.append("pnpm")
    if (repo / "bun.lockb").exists() and "bun" not in pms:
        pms.append("bun")
    runtime_locked = any(t in techs for t in ("bun", "deno"))
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        if not runtime_locked:
            _add(techs, signals, "node", "package.json")
        return
    deps: dict[str, str] = {}
    for k in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(data.get(k) or {})
    scripts = data.get("scripts") if isinstance(data.get("scripts"), dict) else {}
    script_text = "\n".join(str(value) for value in scripts.values())
    angular_config = (repo / "angular.json").exists()
    if "@angular/core" in deps:
        _add(techs, signals, "angular", "package.json:@angular/core")
    elif "@angular/cli" in deps:
        _add(techs, signals, "angular", "package.json:@angular/cli")
    elif angular_config:
        _add(techs, signals, "angular", "angular.json")
    if "react" in deps:
        if "next" in deps:
            _add(techs, signals, "nextjs", "package.json:next")
        else:
            _add(techs, signals, "react", "package.json:react")
    if "vue" in deps or "nuxt" in deps:
        _add(techs, signals, "vue", "package.json:vue")
    if "@nestjs/core" in deps:
        _add(techs, signals, "nestjs", "package.json:@nestjs/core")
    elif "express" in deps or "fastify" in deps or "koa" in deps:
        _add(techs, signals, "express", "package.json")
    framework_detected = any(
        t in techs for t in ("angular", "react", "vue", "nextjs", "nestjs", "express")
    )
    if not framework_detected and not runtime_locked:
        _add(techs, signals, "node", "package.json")
    if (
        "vitest" in deps
        or re.search(r"\bvitest\b", script_text)
        or any(repo.glob("vitest.config.*"))
    ):
        _add(techs, signals, "vitest", "package.json:vitest")
    if "jest" in deps or re.search(r"\bjest\b", script_text) or any(repo.glob("jest.config.*")):
        _add(techs, signals, "jest", "package.json:jest")
    if (
        "eslint" in deps
        or re.search(r"\beslint\b", script_text)
        or any(repo.glob("eslint.config.*"))
        or any(repo.glob(".eslintrc.*"))
    ):
        _add(techs, signals, "eslint", "package.json:eslint")


def _scan_python(repo: Path, techs: list[str], signals: dict[str, str], pms: list[str]) -> None:
    markers = ["pyproject.toml", "requirements.txt", "setup.py", "Pipfile"]
    found = next((m for m in markers if (repo / m).exists()), None)
    if not found:
        return
    if "pip" not in pms:
        pms.append("pip")
    if (repo / "poetry.lock").exists() and "poetry" not in pms:
        pms.append("poetry")
    if (repo / "uv.lock").exists() and "uv" not in pms:
        pms.append("uv")
    text = ""
    with contextlib.suppress(OSError):
        text = (repo / found).read_text(encoding="utf-8", errors="ignore")
    text_l = text.lower()
    if "django" in text_l:
        _add(techs, signals, "django", f"{found}:django")
    elif "fastapi" in text_l:
        _add(techs, signals, "fastapi", f"{found}:fastapi")
    elif "flask" in text_l:
        _add(techs, signals, "flask", f"{found}:flask")
    else:
        _add(techs, signals, "python", found)


def _scan_dotnet(repo: Path, techs: list[str], signals: dict[str, str], pms: list[str]) -> None:
    if any(repo.glob("*.sln")) or any(repo.glob("*.csproj")) or any(repo.rglob("*.csproj")):
        _add(techs, signals, "dotnet", ".sln/.csproj")
        if "nuget" not in pms:
            pms.append("nuget")


def _scan_java(repo: Path, techs: list[str], signals: dict[str, str], pms: list[str]) -> None:
    pom = repo / "pom.xml"
    gradle = (repo / "build.gradle").exists() or (repo / "build.gradle.kts").exists()
    if pom.exists():
        _add(techs, signals, "java", "pom.xml")
        if "maven" not in pms:
            pms.append("maven")
        try:
            text = pom.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            text = ""
        if re.search(r"spring-boot", text):
            _add(techs, signals, "spring", "pom.xml:spring-boot")
    elif gradle:
        _add(techs, signals, "java", "build.gradle")
        if "gradle" not in pms:
            pms.append("gradle")


def _scan_misc(repo: Path, techs: list[str], signals: dict[str, str], pms: list[str]) -> None:
    if (repo / "go.mod").exists():
        _add(techs, signals, "go", "go.mod")
        if "go" not in pms:
            pms.append("go")
    if (repo / "Cargo.toml").exists():
        _add(techs, signals, "rust", "Cargo.toml")
        if "cargo" not in pms:
            pms.append("cargo")
    if (repo / "pubspec.yaml").exists():
        _add(techs, signals, "flutter", "pubspec.yaml")
        if "pub" not in pms:
            pms.append("pub")
    if (repo / "Podfile").exists() or any(repo.glob("*.xcodeproj")):
        _add(techs, signals, "ios", "Podfile/.xcodeproj")
    if (repo / "build.gradle").exists() and (repo / "AndroidManifest.xml").exists():
        _add(techs, signals, "android", "AndroidManifest.xml")
    if (repo / "Gemfile").exists():
        _add(techs, signals, "ruby", "Gemfile")
        if "bundler" not in pms:
            pms.append("bundler")
    if (repo / "composer.json").exists():
        _add(techs, signals, "php", "composer.json")
        if "composer" not in pms:
            pms.append("composer")
        try:
            comp = json.loads((repo / "composer.json").read_text(encoding="utf-8"))
            req = comp.get("require") or {}
            if "laravel/framework" in req:
                _add(techs, signals, "laravel", "composer.json:laravel/framework")
        except (json.JSONDecodeError, OSError):
            pass
    if (repo / "Dockerfile").exists():
        _add(techs, signals, "docker", "Dockerfile")
    if any(repo.rglob("*.tf")):
        _add(techs, signals, "terraform", "*.tf")
    if (repo / "helm").is_dir() or (repo / "kustomization.yaml").exists():
        _add(techs, signals, "k8s", "helm/ or kustomization.yaml")


def _roles_for(techs: list[str]) -> list[str]:
    roles: list[str] = []
    if any(t in FRONT_TECHS for t in techs):
        roles.append("front")
    if any(t in BACK_TECHS for t in techs):
        roles.append("back")
    if any(t in MOBILE_TECHS for t in techs):
        roles.append("mobile")
    if any(t in INFRA_TECHS for t in techs):
        roles.append("infra")
    if not roles:
        roles.append("other")
    return roles


def _has_stack_marker(path: Path) -> bool:
    if any((path / marker).exists() for marker in STACK_MARKER_FILES):
        return True
    if any(any(path.glob(pattern)) for pattern in STACK_MARKER_GLOBS):
        return True
    return any(path.glob("*.sln")) or any(path.glob("*.csproj")) or any(path.glob("*.xcodeproj"))


def _candidate_roots(repo: Path) -> list[Path]:
    """Return root plus nearby package roots for common frontend/backend monorepos."""
    roots = [repo]
    seen = {repo.resolve()}

    def add(path: Path) -> None:
        resolved = path.resolve()
        if resolved not in seen and _has_stack_marker(path):
            seen.add(resolved)
            roots.append(path)

    with contextlib.suppress(OSError):
        for child in repo.iterdir():
            if not child.is_dir() or child.name in SCAN_DIR_SKIP:
                continue
            add(child)
            if child.name not in MONOREPO_CONTAINER_DIRS:
                continue
            with contextlib.suppress(OSError):
                for grandchild in child.iterdir():
                    if grandchild.is_dir() and grandchild.name not in SCAN_DIR_SKIP:
                        add(grandchild)

    return roots


def detect_tech(repo_path: str | Path) -> TechFingerprint:
    """Inspect filesystem markers and return a TechFingerprint."""
    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"repo path not found: {repo}")

    techs: list[str] = []
    signals: dict[str, str] = {}
    pms: list[str] = []
    tech_roots: dict[str, str] = {}

    for root in _candidate_roots(repo):
        before = set(techs)
        _scan_bun(root, techs, signals, pms)
        _scan_deno(root, techs, signals, pms)
        _scan_node(root, techs, signals, pms)
        _scan_python(root, techs, signals, pms)
        _scan_dotnet(root, techs, signals, pms)
        _scan_java(root, techs, signals, pms)
        _scan_misc(root, techs, signals, pms)
        root_rel = _relative_root(repo, root)
        for tech in techs:
            if tech not in before and tech not in tech_roots:
                tech_roots[tech] = root_rel

    return TechFingerprint(
        repo_path=str(repo),
        roles=_roles_for(techs),
        techs=techs,
        package_managers=pms,
        signals=signals,
        tech_roots=tech_roots,
    )


def _relative_root(repo: Path, root: Path) -> str:
    with contextlib.suppress(ValueError):
        rel = root.relative_to(repo)
        return "." if rel == Path(".") else rel.as_posix()
    return str(root)
