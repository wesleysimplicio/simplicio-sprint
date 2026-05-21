"""Tests for deterministic frontend flow discovery."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from sendsprint.frontend_flows import (
    FrontendFlowDiscovery,
    discover_frontend_flows,
    is_front_repo,
)
from sendsprint.models.workspace import RepoConfig
from sendsprint.tech.detector import TechFingerprint


def _write(path: Path, content: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_next_app_routes_are_discovered_with_dynamic_segments(tmp_path: Path) -> None:
    _write(tmp_path / "app" / "page.tsx")
    _write(tmp_path / "app" / "dashboard" / "page.tsx")
    _write(tmp_path / "app" / "(marketing)" / "pricing" / "page.tsx")
    _write(tmp_path / "app" / "blog" / "[slug]" / "page.tsx")
    _write(tmp_path / "app" / "@modal" / "login" / "page.tsx")

    result = discover_frontend_flows(tmp_path)

    assert isinstance(result, FrontendFlowDiscovery)
    assert [(route.path, route.source_kind) for route in result.routes] == [
        ("/", "next_app"),
        ("/blog/:slug", "next_app"),
        ("/dashboard", "next_app"),
        ("/login", "next_app"),
        ("/pricing", "next_app"),
    ]
    assert result.routes[0].confidence == pytest.approx(0.98)
    assert "Next.js app directory page file" in result.routes[0].reasons


def test_next_pages_routes_skip_api_and_framework_files(tmp_path: Path) -> None:
    _write(tmp_path / "pages" / "index.tsx")
    _write(tmp_path / "pages" / "about.tsx")
    _write(tmp_path / "pages" / "docs" / "[[...slug]].tsx")
    _write(tmp_path / "pages" / "api" / "health.ts")
    _write(tmp_path / "pages" / "_app.tsx")
    _write(tmp_path / "pages" / "404.tsx")

    result = discover_frontend_flows(tmp_path)

    assert [route.path for route in result.routes] == ["/", "/about", "/docs/:slug*"]
    assert all(route.source_kind == "next_pages" for route in result.routes)


def test_react_router_declarations_include_titles(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "routes.tsx",
        """
        import { createBrowserRouter, Route } from "react-router-dom";

        export const router = createBrowserRouter([
          { path: "/", element: <Home />, title: "Home screen" },
          { path: "settings/profile", element: <Profile />, label: "Profile settings" },
        ]);

        export function AppRoutes() {
          return <Route path="/reports/:id" element={<Report />} />;
        }
        """,
    )

    result = discover_frontend_flows(tmp_path)

    routes = {route.path: route for route in result.routes}
    assert sorted(routes) == ["/", "/reports/:id", "/settings/profile"]
    assert routes["/"].title == "Home screen"
    assert routes["/settings/profile"].title == "Profile settings"
    assert routes["/reports/:id"].source == "src/routes.tsx"
    assert routes["/reports/:id"].confidence == pytest.approx(0.84)


def test_router_titles_do_not_bleed_into_previous_route(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "routes.ts",
        """
        export const routes = [
          { path: "/alpha", element: AlphaScreen },
          { path: "/beta", element: BetaScreen, title: "Beta title" },
        ];
        """,
    )

    result = discover_frontend_flows(tmp_path)

    routes = {route.path: route for route in result.routes}
    assert routes["/alpha"].title == "Alpha"
    assert routes["/beta"].title == "Beta title"


def test_vue_and_angular_router_declarations_are_framework_tolerant(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "router.ts",
        """
        const routes = [
          { path: "/users", name: "Users" },
          { path: "/users/:id", component: UserDetail },
        ];
        """,
    )
    _write(
        tmp_path / "src" / "app-routing.module.ts",
        """
        RouterModule.forRoot([
          { path: "admin", component: AdminComponent, title: "Admin area" },
        ]);
        """,
    )

    result = discover_frontend_flows(tmp_path)

    assert [route.path for route in result.routes] == ["/admin", "/users", "/users/:id"]
    assert {route.path: route.title for route in result.routes}["/admin"] == "Admin area"


def test_router_discovery_ignores_asset_like_paths(tmp_path: Path) -> None:
    _write(
        tmp_path / "src" / "routes.ts",
        """
        export const routes = [
          { path: "/settings", title: "Settings" },
          { path: "/images/logo.svg", title: "Logo asset" },
          { path: "/docs/help.pdf", title: "Help PDF" },
          { path: ":id", title: "User detail" },
        ];
        """,
    )

    result = discover_frontend_flows(tmp_path)

    assert [route.path for route in result.routes] == ["/:id", "/settings"]


def test_static_html_anchors_keep_internal_routes_and_labels(tmp_path: Path) -> None:
    _write(
        tmp_path / "public" / "index.html",
        """
        <nav>
          <a href="/docs/getting-started">Start <strong>here</strong></a>
          <a href="/pricing?plan=pro">Pricing</a>
          <a href="https://example.com">External</a>
          <a href="#local">Hash</a>
        </nav>
        """,
    )

    result = discover_frontend_flows(tmp_path)

    assert [(route.path, route.label, route.source_kind) for route in result.routes] == [
        ("/docs/getting-started", "Start here", "static_html"),
        ("/pricing", "Pricing", "static_html"),
    ]


def test_discovery_is_deterministic_and_ignores_generated_directories(tmp_path: Path) -> None:
    _write(tmp_path / "src" / "routes.ts", 'export const routes = [{ path: "/b" }];')
    _write(tmp_path / "pages" / "a.tsx")
    _write(
        tmp_path / "node_modules" / "pkg" / "routes.ts",
        'export const routes = [{ path: "/bad" }];',
    )
    _write(tmp_path / "dist" / "index.html", '<a href="/bad">Bad</a>')

    first = discover_frontend_flows(tmp_path)
    second = discover_frontend_flows(tmp_path)

    assert first.model_dump() == second.model_dump()
    assert [route.path for route in first.routes] == ["/a", "/b"]


def test_discovery_does_not_ignore_repo_because_ancestor_folder_name_matches_generated_dir(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "dist" / "actual-repo"
    _write(repo / "pages" / "index.tsx")

    result = discover_frontend_flows(repo)

    assert [route.path for route in result.routes] == ["/"]


def test_is_front_repo_from_repo_config_role() -> None:
    assert is_front_repo(repo=RepoConfig(name="web", path=".", role="front"))
    assert not is_front_repo(repo=RepoConfig(name="api", path=".", role="api"))


def test_is_front_repo_from_tech_fingerprint_roles() -> None:
    assert is_front_repo(
        fingerprint=TechFingerprint(repo_path=".", roles=["front"], techs=["react"])
    )
    assert not is_front_repo(
        fingerprint=TechFingerprint(repo_path=".", roles=["back"], techs=["fastapi"])
    )


def test_nonexistent_repo_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        discover_frontend_flows(tmp_path / "missing")


def test_pydantic_result_serializes_cleanly(tmp_path: Path) -> None:
    _write(tmp_path / "pages" / "index.tsx")

    result = discover_frontend_flows(tmp_path)

    assert json.loads(result.model_dump_json())["routes"][0]["path"] == "/"
