"""Install the SendSprint skill into each agent's convention.

One canonical skill body, many destinations. Dedicated files (Cursor, Claude,
Kiro) are written outright; shared root files (AGENTS.md, GEMINI.md) get an
idempotent managed block so an existing file is never clobbered. Tools that read
AGENTS.md (Codex, OpenCode, Antigravity, and the Hermes/openclaw fallback) all
share that one block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

BLOCK_BEGIN = "<!-- BEGIN sendsprint skill (managed) -->"
BLOCK_END = "<!-- END sendsprint skill (managed) -->"

SKILL_DESCRIPTION = (
    "Autonomous sprint delivery: read a Jira/Azure DevOps/GitHub sprint, delegate "
    "each card to simplicio-cli, capture evidence, open a draft PR."
)

SKILL_BODY = """# SendSprint — finish my sprint

You are the agent; `sendsprint` is your tooling and **simplicio-cli** is the
executor. Don't reimplement the flow — shell out to the CLI.

**Trigger:** "rode o sendsprint", "executar/entregar sprint", "run/ship/deliver my
sprint", "ejecutar sprint", `/sendsprint`, or a sprint id + source + repo.

**Run:**

```bash
sendsprint update            # pull latest simplicio-cli / -prompt / -mapper
sendsprint run <jira|azuredevops|github> <sprint> \\
  --repo <path> --repo-slug <owner/repo> --scope mine
```

Each card → simplicio-mapper spec (`.specs/`) → `simplicio task` → tests + screen
evidence → commit → **draft PR** → ticket "In Review". `--fanout` adds a
simplicio-prompt subagent brainstorm (opt-in). MCP is host-driven: register tenant
data via `sendsprint.operators._mcp_bridge.register_provider(<source>, fn)` before
reading, else it falls back to REST.

**Unattended:** `sendsprint watch <source> <sprint> --repo <path> --once`.
"""


@dataclass(frozen=True)
class Target:
    """One agent's skill destination."""

    name: str
    path: str
    mode: str  # "file" | "block"
    frontmatter: str = ""

    def render(self) -> str:
        if self.mode == "block" or not self.frontmatter:
            return SKILL_BODY
        return f"{self.frontmatter}\n\n{SKILL_BODY}"


@dataclass
class InstallResult:
    target: str
    path: str
    action: str  # "created" | "updated" | "unchanged"

    def line(self) -> str:
        return f"{self.target} → {self.path} ({self.action})"


_CLAUDE_FM = (
    "---\n"
    "name: sendsprint\n"
    f"description: {SKILL_DESCRIPTION}\n"
    "command: sendsprint\n"
    "version: 3.0.0\n"
    "platform: claude-code\n"
    "---"
)
_CURSOR_FM = f"---\ndescription: {SKILL_DESCRIPTION}\nalwaysApply: false\n---"
_KIRO_FM = "---\ninclusion: manual\n---"

TARGETS: dict[str, Target] = {
    "claude": Target("claude", ".claude/skills/sendsprint/SKILL.md", "file", _CLAUDE_FM),
    "cursor": Target("cursor", ".cursor/rules/sendsprint.mdc", "file", _CURSOR_FM),
    "kiro": Target("kiro", ".kiro/steering/sendsprint.md", "file", _KIRO_FM),
    "gemini": Target("gemini", "GEMINI.md", "block"),
    "codex": Target("codex", "AGENTS.md", "block"),
    "opencode": Target("opencode", "AGENTS.md", "block"),
    "antigravity": Target("antigravity", "AGENTS.md", "block"),
    "hermes": Target("hermes", "AGENTS.md", "block"),
    "openclaw": Target("openclaw", "AGENTS.md", "block"),
}


def install(repo_root: str | Path, names: list[str]) -> list[InstallResult]:
    """Install the skill for each named target under ``repo_root``."""
    root = Path(repo_root)
    results: list[InstallResult] = []
    for name in names:
        target = TARGETS.get(name.lower())
        if target is None:
            raise ValueError(f"unknown target {name!r}; choose from {sorted(TARGETS)}")
        path = root / target.path
        if target.mode == "file":
            action = _write_file(path, target.render())
        else:
            action = _write_block(path, target.render())
        results.append(InstallResult(name.lower(), target.path, action))
    return results


def _write_file(path: Path, content: str) -> str:
    content = content.rstrip() + "\n"
    if path.exists() and path.read_text(encoding="utf-8") == content:
        return "unchanged"
    action = "updated" if path.exists() else "created"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return action


def _write_block(path: Path, body: str) -> str:
    block = f"{BLOCK_BEGIN}\n{body.strip()}\n{BLOCK_END}"
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    if BLOCK_BEGIN in existing and BLOCK_END in existing:
        pattern = re.compile(re.escape(BLOCK_BEGIN) + r".*?" + re.escape(BLOCK_END), re.DOTALL)
        new = pattern.sub(lambda _: block, existing)
        action = "unchanged" if new == existing else "updated"
    elif existing.strip():
        new = f"{existing.rstrip()}\n\n{block}\n"
        action = "updated"
    else:
        new = f"{block}\n"
        action = "created"
    if action != "unchanged":
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(new, encoding="utf-8")
    return action
