"""Discover likely frontend routes from common framework sources."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from sendsprint.models.workspace import RepoConfig
from sendsprint.tech.detector import TechFingerprint

RouteSourceKind = Literal[
    "next_app",
    "next_pages",
    "router_declaration",
    "static_html",
]

ROUTE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".vue"}
NEXT_PAGE_EXTENSIONS = {".js", ".jsx", ".ts", ".tsx", ".mdx"}
HTML_EXTENSIONS = {".html", ".htm"}
IGNORED_DIRS = {
    ".git",
    ".hg",
    ".next",
    ".nuxt",
    ".svelte-kit",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "out",
    "target",
    "vendor",
}
IGNORED_NEXT_FILES = {
    "_app",
    "_document",
    "_error",
    "404",
    "500",
}
IGNORED_ROUTE_FILE_SUFFIXES = {
    ".avif",
    ".css",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".json",
    ".md",
    ".mdx",
    ".pdf",
    ".png",
    ".svg",
    ".txt",
    ".webp",
    ".xml",
}


class FrontendRoute(BaseModel):
    """A route discovered from framework source or static HTML."""

    path: str
    source: str
    source_kind: RouteSourceKind
    title: str | None = None
    label: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reasons: list[str] = Field(default_factory=list)


class FrontendFlowDiscovery(BaseModel):
    """Deterministic route discovery result for one frontend repo."""

    repo_path: str
    routes: list[FrontendRoute] = Field(default_factory=list)


def is_front_repo(
    repo: RepoConfig | None = None,
    fingerprint: TechFingerprint | None = None,
) -> bool:
    """Return true when workspace metadata or detected tech roles mark a frontend repo."""
    if repo and repo.role == "front":
        return True
    return bool(fingerprint and "front" in fingerprint.roles)


def discover_frontend_flows(repo_path: str | Path) -> FrontendFlowDiscovery:
    """Scan frontend route sources and return stable, deduplicated route candidates."""
    repo = Path(repo_path).expanduser().resolve()
    if not repo.exists():
        raise FileNotFoundError(f"repo path not found: {repo}")

    routes: list[FrontendRoute] = []
    routes.extend(_discover_next_app_routes(repo))
    routes.extend(_discover_next_pages_routes(repo))
    routes.extend(_discover_router_declarations(repo))
    routes.extend(_discover_static_html_routes(repo))

    return FrontendFlowDiscovery(repo_path=str(repo), routes=_dedupe_routes(routes))


def _discover_next_app_routes(repo: Path) -> list[FrontendRoute]:
    routes: list[FrontendRoute] = []
    for app_dir in _candidate_dirs(repo, "app"):
        for page in _walk_files(app_dir, NEXT_PAGE_EXTENSIONS):
            if page.stem != "page":
                continue
            route_path = _next_app_path(app_dir, page)
            routes.append(
                FrontendRoute(
                    path=route_path,
                    source=_relative_source(repo, page),
                    source_kind="next_app",
                    title=_title_from_path(route_path),
                    confidence=0.98,
                    reasons=["Next.js app directory page file"],
                )
            )
    return routes


def _discover_next_pages_routes(repo: Path) -> list[FrontendRoute]:
    routes: list[FrontendRoute] = []
    for pages_dir in _candidate_dirs(repo, "pages"):
        for page in _walk_files(pages_dir, NEXT_PAGE_EXTENSIONS):
            if page.stem in IGNORED_NEXT_FILES or page.stem.startswith("_"):
                continue
            route_path = _next_pages_path(pages_dir, page)
            if route_path.startswith("/api/") or route_path == "/api":
                continue
            routes.append(
                FrontendRoute(
                    path=route_path,
                    source=_relative_source(repo, page),
                    source_kind="next_pages",
                    title=_title_from_path(route_path),
                    confidence=0.96,
                    reasons=["Next.js pages directory route file"],
                )
            )
    return routes


def _discover_router_declarations(repo: Path) -> list[FrontendRoute]:
    routes: list[FrontendRoute] = []
    for file_path in _walk_files(repo, ROUTE_EXTENSIONS):
        text = _read_text(file_path)
        if not _looks_like_router_source(text, file_path):
            continue
        for match in _router_path_matches(text):
            raw_path = match.group("path")
            route_path = _normalize_declared_path(raw_path)
            if not route_path:
                continue
            routes.append(
                FrontendRoute(
                    path=route_path,
                    source=_relative_source(repo, file_path),
                    source_kind="router_declaration",
                    title=_nearby_title(text, match.start()) or _title_from_path(route_path),
                    confidence=0.86,
                    reasons=["Router declaration contains a path entry"],
                )
            )
        for match in _route_component_matches(text):
            raw_path = match.group("path")
            route_path = _normalize_declared_path(raw_path)
            if not route_path:
                continue
            routes.append(
                FrontendRoute(
                    path=route_path,
                    source=_relative_source(repo, file_path),
                    source_kind="router_declaration",
                    title=_nearby_title(text, match.start()) or _title_from_path(route_path),
                    confidence=0.84,
                    reasons=["Route component declares a path prop"],
                )
            )
    return routes


def _discover_static_html_routes(repo: Path) -> list[FrontendRoute]:
    routes: list[FrontendRoute] = []
    for file_path in _walk_files(repo, HTML_EXTENSIONS):
        text = _read_text(file_path)
        for match in re.finditer(
            r"<a\b(?=[^>]*\bhref\s*=\s*(?P<quote>['\"])(?P<href>[^'\"]+)(?P=quote))[^>]*>"
            r"(?P<label>.*?)</a>",
            text,
            flags=re.IGNORECASE | re.DOTALL,
        ):
            route_path = _normalize_href(match.group("href"))
            if not route_path:
                continue
            label = _clean_label(match.group("label"))
            routes.append(
                FrontendRoute(
                    path=route_path,
                    source=_relative_source(repo, file_path),
                    source_kind="static_html",
                    label=label,
                    title=label or _title_from_path(route_path),
                    confidence=0.68,
                    reasons=["Static HTML anchor links to an internal route"],
                )
            )
    return routes


def _candidate_dirs(repo: Path, name: str) -> list[Path]:
    candidates = [repo / name, repo / "src" / name]
    return [path for path in candidates if path.is_dir()]


def _walk_files(root: Path, extensions: set[str]) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.suffix not in extensions:
            continue
        relative_parts = path.relative_to(root).parts
        if any(part in IGNORED_DIRS for part in relative_parts):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.as_posix())


def _next_app_path(app_dir: Path, page: Path) -> str:
    parts = list(page.parent.relative_to(app_dir).parts)
    visible_parts = [
        _normalize_segment(part)
        for part in parts
        if not part.startswith("(") and not part.startswith("@")
    ]
    return _join_route_parts(visible_parts)


def _next_pages_path(pages_dir: Path, page: Path) -> str:
    relative = page.relative_to(pages_dir).with_suffix("")
    parts = list(relative.parts)
    if parts[-1] == "index":
        parts = parts[:-1]
    return _join_route_parts(_normalize_segment(part) for part in parts)


def _join_route_parts(parts: Iterable[str]) -> str:
    cleaned = [part for part in parts if part]
    return "/" + "/".join(cleaned) if cleaned else "/"


def _normalize_segment(segment: str) -> str:
    if segment.startswith("[[...") and segment.endswith("]]"):
        return f":{segment[5:-2]}*"
    if segment.startswith("[...") and segment.endswith("]"):
        return f":{segment[4:-1]}*"
    if segment.startswith("[") and segment.endswith("]"):
        return f":{segment[1:-1]}"
    return segment


def _looks_like_router_source(text: str, file_path: Path) -> bool:
    lower_name = file_path.name.lower()
    if "router" in lower_name or "routes" in lower_name:
        return True
    markers = ("createbrowserrouter", "createrouter", "routermodule.forroot", "<route ")
    return any(marker in text.lower() for marker in markers)


def _router_path_matches(text: str) -> list[re.Match[str]]:
    return list(
        re.finditer(
            r"\bpath\s*:\s*(?P<quote>['\"])(?P<path>/[^'\"]*|[^'\"#?][^'\"]*)(?P=quote)",
            text,
        )
    )


def _route_component_matches(text: str) -> list[re.Match[str]]:
    return list(
        re.finditer(
            r"<Route\b[^>]*\bpath\s*=\s*(?P<quote>['\"])(?P<path>[^'\"]+)(?P=quote)",
            text,
            flags=re.IGNORECASE,
        )
    )


def _normalize_declared_path(path: str) -> str | None:
    cleaned = path.strip()
    if not cleaned or cleaned == "*":
        return None
    if cleaned.startswith(("http://", "https://", "mailto:", "tel:", "#")):
        return None
    if cleaned.startswith(":") or not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    cleaned = _strip_query_or_hash(cleaned.rstrip("/") or "/")
    if _looks_like_asset_path(cleaned):
        return None
    return cleaned


def _normalize_href(href: str) -> str | None:
    cleaned = href.strip()
    if not cleaned or cleaned.startswith(("http://", "https://", "mailto:", "tel:", "#")):
        return None
    if not cleaned.startswith("/"):
        return None
    return _strip_query_or_hash(cleaned.rstrip("/") or "/")


def _strip_query_or_hash(path: str) -> str:
    return re.split(r"[?#]", path, maxsplit=1)[0] or "/"


def _nearby_title(text: str, position: int) -> str | None:
    window = text[position : position + 300]
    object_end = window.find("}")
    if object_end != -1:
        window = window[:object_end]
    match = re.search(
        r"\b(?:title|label|name)\s*:\s*(?P<quote>['\"])(?P<title>[^'\"]+)(?P=quote)",
        window,
    )
    if match:
        return match.group("title").strip()
    return None


def _title_from_path(path: str) -> str:
    if path == "/":
        return "Home"
    segment = path.rstrip("/").split("/")[-1]
    segment = segment.lstrip(":").rstrip("*")
    return segment.replace("-", " ").replace("_", " ").title()


def _clean_label(label: str) -> str | None:
    label = re.sub(r"<[^>]+>", "", label)
    label = re.sub(r"\s+", " ", label).strip()
    return label or None


def _looks_like_asset_path(path: str) -> bool:
    if path == "/":
        return False
    suffix = Path(path).suffix.lower()
    return suffix in IGNORED_ROUTE_FILE_SUFFIXES


def _dedupe_routes(routes: list[FrontendRoute]) -> list[FrontendRoute]:
    by_key: dict[tuple[str, str], FrontendRoute] = {}
    for route in sorted(routes, key=lambda item: (-item.confidence, item.path, item.source)):
        key = (route.path, route.source_kind)
        if key not in by_key:
            by_key[key] = route
    return sorted(by_key.values(), key=lambda item: (item.path, item.source_kind, item.source))


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def _relative_source(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()
