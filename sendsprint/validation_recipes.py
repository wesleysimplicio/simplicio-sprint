"""Stack-specific validation recipes for PR bodies and agent instructions.

Each recipe codifies the recommended validation commands, required tools,
and Windows-specific notes for a technology stack.  ``RecipeSelector``
auto-detects applicable recipes from a ``TechFingerprint``.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from sendsprint.tech.detector import TechFingerprint, detect_tech

# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class ValidationRecipe(BaseModel):
    """A single stack validation recipe."""

    stack: str
    commands: list[str] = Field(default_factory=list)
    windows_notes: str = ""
    required_tools: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Built-in recipes
# ---------------------------------------------------------------------------

PYTHON_RECIPE = ValidationRecipe(
    stack="python",
    commands=[
        "python -m pytest tests/ -v",
        "ruff check .",
        "ruff format --check .",
    ],
    windows_notes=(
        "Use `python` (not `python3`) on Windows.  "
        "Ensure `.venv\\Scripts\\activate` is used instead of `source .venv/bin/activate`."
    ),
    required_tools=["pytest", "ruff"],
)

GO_RECIPE = ValidationRecipe(
    stack="go",
    commands=[
        "go test ./...",
        "go vet ./...",
    ],
    windows_notes=(
        "CGO may require a C compiler (mingw-w64) on Windows.  "
        "Use `set` instead of `export` for environment variables in cmd."
    ),
    required_tools=["go"],
)

RUST_RECIPE = ValidationRecipe(
    stack="rust",
    commands=[
        "cargo test",
        "cargo clippy -- -D warnings",
    ],
    windows_notes=(
        "Rust on Windows requires the MSVC toolchain by default.  "
        "Use `rustup default stable-x86_64-pc-windows-msvc` if builds fail."
    ),
    required_tools=["cargo", "clippy"],
)

NODE_RECIPE = ValidationRecipe(
    stack="node",
    commands=[
        "npm test",
        "npm run build",
        "npx playwright test",
    ],
    windows_notes=(
        "Use `npx.cmd` or `npm.cmd` in CI scripts on Windows.  "
        "Playwright browsers may need `npx playwright install` with admin privileges."
    ),
    required_tools=["npm", "node"],
)

COPILOT_RECIPE = ValidationRecipe(
    stack="copilot",
    commands=[
        "# See .github/copilot-instructions.md for repo-specific validation guidance.",
    ],
    windows_notes=(
        "Copilot instructions file uses Unix-style paths; "
        "editors resolve them on Windows automatically."
    ),
    required_tools=[],
)

_ALL_RECIPES: dict[str, ValidationRecipe] = {
    "python": PYTHON_RECIPE,
    "go": GO_RECIPE,
    "rust": RUST_RECIPE,
    "node": NODE_RECIPE,
    "copilot": COPILOT_RECIPE,
}

# Tech keys that map to a recipe.  Multiple detector keys can share one
# recipe (e.g. django/fastapi/flask all use the python recipe).
_TECH_TO_RECIPE: dict[str, str] = {
    "python": "python",
    "django": "python",
    "fastapi": "python",
    "flask": "python",
    "go": "go",
    "rust": "rust",
    "node": "node",
    "angular": "node",
    "react": "node",
    "vue": "node",
    "nextjs": "node",
    "nestjs": "node",
    "express": "node",
    "bun": "node",
    "deno": "node",
}


# ---------------------------------------------------------------------------
# Recipe selector
# ---------------------------------------------------------------------------


class RecipeSelector:
    """Select validation recipes from a workspace fingerprint."""

    def __init__(self, fingerprint: TechFingerprint) -> None:
        self.fingerprint = fingerprint

    @classmethod
    def from_path(cls, repo_path: str | Path) -> RecipeSelector:
        """Build a selector by scanning *repo_path* for tech markers."""
        return cls(detect_tech(repo_path))

    def select(self) -> list[ValidationRecipe]:
        """Return de-duplicated recipes matching the detected techs."""
        seen: set[str] = set()
        recipes: list[ValidationRecipe] = []
        for tech in self.fingerprint.techs:
            recipe_key = _TECH_TO_RECIPE.get(tech)
            if recipe_key and recipe_key not in seen:
                seen.add(recipe_key)
                recipes.append(_ALL_RECIPES[recipe_key])
        # Append copilot recipe when the repo has a copilot instructions file.
        if "copilot" not in seen:
            repo = Path(self.fingerprint.repo_path)
            if (repo / ".github" / "copilot-instructions.md").exists():
                recipes.append(COPILOT_RECIPE)
        return recipes


# ---------------------------------------------------------------------------
# PR body formatting
# ---------------------------------------------------------------------------


def format_for_pr_body(recipes: list[ValidationRecipe]) -> str:
    """Render recipes as a Markdown section suitable for PR body inclusion."""
    if not recipes:
        return ""
    lines: list[str] = ["## Validation recipes", ""]
    for recipe in recipes:
        lines.append(f"### {recipe.stack}")
        lines.append("")
        lines.append("```bash")
        for cmd in recipe.commands:
            lines.append(cmd)
        lines.append("```")
        if recipe.windows_notes:
            lines.append("")
            lines.append(f"> **Windows:** {recipe.windows_notes}")
        lines.append("")
    return "\n".join(lines)
