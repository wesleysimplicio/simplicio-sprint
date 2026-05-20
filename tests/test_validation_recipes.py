"""Tests for stack-specific validation recipes (#112)."""

from __future__ import annotations

from pathlib import Path

from sendsprint.tech.detector import TechFingerprint
from sendsprint.validation_recipes import (
    COPILOT_RECIPE,
    GO_RECIPE,
    NODE_RECIPE,
    PYTHON_RECIPE,
    RUST_RECIPE,
    RecipeSelector,
    ValidationRecipe,
    format_for_pr_body,
)

# ---------------------------------------------------------------------------
# Model basics
# ---------------------------------------------------------------------------


class TestValidationRecipeModel:
    def test_recipe_fields(self):
        r = ValidationRecipe(
            stack="demo", commands=["echo ok"], windows_notes="n/a", required_tools=["echo"]
        )
        assert r.stack == "demo"
        assert r.commands == ["echo ok"]
        assert r.windows_notes == "n/a"
        assert r.required_tools == ["echo"]

    def test_defaults(self):
        r = ValidationRecipe(stack="empty")
        assert r.commands == []
        assert r.windows_notes == ""
        assert r.required_tools == []


# ---------------------------------------------------------------------------
# Built-in recipe constants
# ---------------------------------------------------------------------------


class TestBuiltinRecipes:
    def test_python_recipe_has_pytest_and_ruff(self):
        assert any("pytest" in c for c in PYTHON_RECIPE.commands)
        assert any("ruff check" in c for c in PYTHON_RECIPE.commands)
        assert "pytest" in PYTHON_RECIPE.required_tools
        assert "ruff" in PYTHON_RECIPE.required_tools
        assert PYTHON_RECIPE.windows_notes

    def test_go_recipe_has_test_and_vet(self):
        assert "go test ./..." in GO_RECIPE.commands
        assert "go vet ./..." in GO_RECIPE.commands
        assert "go" in GO_RECIPE.required_tools
        assert GO_RECIPE.windows_notes

    def test_rust_recipe_has_test_and_clippy(self):
        assert "cargo test" in RUST_RECIPE.commands
        assert "cargo clippy -- -D warnings" in RUST_RECIPE.commands
        assert "cargo" in RUST_RECIPE.required_tools
        assert RUST_RECIPE.windows_notes

    def test_node_recipe_has_test_build_playwright(self):
        assert "npm test" in NODE_RECIPE.commands
        assert "npm run build" in NODE_RECIPE.commands
        assert "npx playwright test" in NODE_RECIPE.commands
        assert "npm" in NODE_RECIPE.required_tools
        assert NODE_RECIPE.windows_notes

    def test_copilot_recipe_references_instructions_file(self):
        assert any("copilot-instructions.md" in c for c in COPILOT_RECIPE.commands)
        assert COPILOT_RECIPE.required_tools == []
        assert COPILOT_RECIPE.windows_notes


# ---------------------------------------------------------------------------
# RecipeSelector
# ---------------------------------------------------------------------------


def _fp(techs: list[str], repo_path: str = "/fake") -> TechFingerprint:
    return TechFingerprint(repo_path=repo_path, techs=techs)


class TestRecipeSelector:
    def test_python_detected(self):
        sel = RecipeSelector(_fp(["python"]))
        recipes = sel.select()
        assert len(recipes) == 1
        assert recipes[0].stack == "python"

    def test_django_maps_to_python(self):
        sel = RecipeSelector(_fp(["django"]))
        recipes = sel.select()
        assert len(recipes) == 1
        assert recipes[0].stack == "python"

    def test_fastapi_maps_to_python(self):
        sel = RecipeSelector(_fp(["fastapi"]))
        assert sel.select()[0].stack == "python"

    def test_go_detected(self):
        sel = RecipeSelector(_fp(["go"]))
        assert sel.select()[0].stack == "go"

    def test_rust_detected(self):
        sel = RecipeSelector(_fp(["rust"]))
        assert sel.select()[0].stack == "rust"

    def test_node_detected(self):
        sel = RecipeSelector(_fp(["node"]))
        assert sel.select()[0].stack == "node"

    def test_react_maps_to_node(self):
        sel = RecipeSelector(_fp(["react"]))
        assert sel.select()[0].stack == "node"

    def test_angular_maps_to_node(self):
        sel = RecipeSelector(_fp(["angular"]))
        assert sel.select()[0].stack == "node"

    def test_bun_maps_to_node(self):
        sel = RecipeSelector(_fp(["bun"]))
        assert sel.select()[0].stack == "node"

    def test_multi_stack_dedup(self):
        """django + fastapi should yield one python recipe, not two."""
        sel = RecipeSelector(_fp(["django", "fastapi"]))
        recipes = sel.select()
        assert len(recipes) == 1
        assert recipes[0].stack == "python"

    def test_multi_stack_mixed(self):
        sel = RecipeSelector(_fp(["python", "go", "rust"]))
        recipes = sel.select()
        stacks = [r.stack for r in recipes]
        assert stacks == ["python", "go", "rust"]

    def test_unknown_tech_yields_empty(self):
        sel = RecipeSelector(_fp(["terraform"]))
        assert sel.select() == []

    def test_copilot_appended_when_file_exists(self, tmp_path: Path):
        (tmp_path / ".github").mkdir()
        (tmp_path / ".github" / "copilot-instructions.md").write_text("x")
        sel = RecipeSelector(_fp(["python"], repo_path=str(tmp_path)))
        recipes = sel.select()
        stacks = [r.stack for r in recipes]
        assert "python" in stacks
        assert "copilot" in stacks

    def test_copilot_not_appended_without_file(self, tmp_path: Path):
        sel = RecipeSelector(_fp(["python"], repo_path=str(tmp_path)))
        recipes = sel.select()
        assert all(r.stack != "copilot" for r in recipes)

    def test_from_path(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'demo'\n")
        sel = RecipeSelector.from_path(tmp_path)
        recipes = sel.select()
        assert any(r.stack == "python" for r in recipes)


# ---------------------------------------------------------------------------
# PR body formatting (snapshot-style)
# ---------------------------------------------------------------------------


class TestFormatForPrBody:
    def test_empty_recipes_returns_empty(self):
        assert format_for_pr_body([]) == ""

    def test_single_recipe_structure(self):
        body = format_for_pr_body([PYTHON_RECIPE])
        assert "## Validation recipes" in body
        assert "### python" in body
        assert "```bash" in body
        assert "pytest" in body
        assert "> **Windows:**" in body

    def test_multiple_recipes(self):
        body = format_for_pr_body([GO_RECIPE, RUST_RECIPE])
        assert "### go" in body
        assert "### rust" in body
        assert "go test" in body
        assert "cargo test" in body

    def test_snapshot_python_recipe(self):
        """Snapshot: full rendered output for python recipe."""
        body = format_for_pr_body([PYTHON_RECIPE])
        expected = (
            "## Validation recipes\n"
            "\n"
            "### python\n"
            "\n"
            "```bash\n"
            "python -m pytest tests/ -v\n"
            "ruff check .\n"
            "ruff format --check .\n"
            "```\n"
            "\n"
            "> **Windows:** Use `python` (not `python3`) on Windows.  "
            "Ensure `.venv\\Scripts\\activate` is used instead of `source .venv/bin/activate`.\n"
        )
        assert body == expected

    def test_snapshot_go_recipe(self):
        body = format_for_pr_body([GO_RECIPE])
        assert body.startswith("## Validation recipes\n")
        assert "### go\n" in body
        assert "go test ./...\ngo vet ./..." in body
        assert "> **Windows:** CGO may require" in body

    def test_snapshot_rust_recipe(self):
        body = format_for_pr_body([RUST_RECIPE])
        assert "### rust\n" in body
        assert "cargo test\ncargo clippy -- -D warnings" in body
        assert "MSVC toolchain" in body

    def test_snapshot_node_recipe(self):
        body = format_for_pr_body([NODE_RECIPE])
        assert "### node\n" in body
        assert "npm test\nnpm run build\nnpx playwright test" in body
        assert "npx.cmd" in body

    def test_snapshot_copilot_recipe(self):
        body = format_for_pr_body([COPILOT_RECIPE])
        assert "### copilot\n" in body
        assert "copilot-instructions.md" in body

    def test_no_internal_process_leak(self):
        """PR body must not expose internal tool names like SendSprint."""
        body = format_for_pr_body([PYTHON_RECIPE, GO_RECIPE, RUST_RECIPE, NODE_RECIPE])
        assert "SendSprint" not in body
        assert "sendsprint" not in body
