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
    "angular": "Angular",
    "react": "React",
    "vue": "Vue",
    "nextjs": "Next.js",
    "nestjs": "NestJS",
    "express": "Express",
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


class TechFingerprint(BaseModel):
    repo_path: str
    roles: list[str] = Field(default_factory=list)
    techs: list[str] = Field(default_factory=list)
    package_managers: list[str] = Field(default_factory=list)
    signals: dict[str, str] = Field(default_factory=dict)

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
    try:
        data = json.loads(pkg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        _add(techs, signals, "node", "package.json")
        return
    deps: dict[str, str] = {}
    for k in ("dependencies", "devDependencies", "peerDependencies"):
        deps.update(data.get(k) or {})
    if "@angular/core" in deps:
        _add(techs, signals, "angular", "package.json:@angular/core")
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
    if not any(t in techs for t in ("angular", "react", "vue", "nextjs", "nestjs", "express")):
        _add(techs, signals, "node", "package.json")


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


def detect_tech(repo_path: str | Path) -> TechFingerprint:
    """Inspect filesystem markers and return a TechFingerprint."""
    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"repo path not found: {repo}")

    techs: list[str] = []
    signals: dict[str, str] = {}
    pms: list[str] = []

    _scan_node(repo, techs, signals, pms)
    _scan_python(repo, techs, signals, pms)
    _scan_dotnet(repo, techs, signals, pms)
    _scan_java(repo, techs, signals, pms)
    _scan_misc(repo, techs, signals, pms)

    return TechFingerprint(
        repo_path=str(repo),
        roles=_roles_for(techs),
        techs=techs,
        package_managers=pms,
        signals=signals,
    )
