# SendSprint — Claude Code plugin

Official Claude Code plugin package for [SendSprint](https://github.com/wesleysimplicio/sendsprint). Wraps the `sendsprint` Python CLI as commands, sub-agents, a skill and hooks.

## What you get

- **`/sendsprint`** — run the full 10-step sprint delivery flow.
- **`/sendsprint-doctor`** — environment + credential readiness check.
- **`/sendsprint-watch`** — continuous watch over a workspace.
- **`/sendsprint-web`** — start the local dashboard at `http://localhost:8081`.
- **`/sendsprint-preflight`** — dry-run validation before delivery.
- **Agents**: `sprint-deliverer` (full execution), `sprint-reviewer` (review-only).
- **Skill**: `sendsprint` — chat-trigger phrases auto-route here.
- **Hooks**: pre-commit (ruff + pytest gates) and post-edit (ruff format).

## Install

### Option A — via Claude Code marketplace / plugins folder

```bash
# Drop the plugin in the user-level plugins folder
mkdir -p ~/.claude/plugins
cp -r plugins/claude-code ~/.claude/plugins/sendsprint
```

Claude Code auto-discovers `~/.claude/plugins/*/.claude-plugin/plugin.json` on the next session.

### Option B — via `sendsprint plugins install`

```bash
sendsprint plugins install --platform claude --packaged
```

This copies the entire plugin tree into `.claude/plugins/sendsprint/` inside the current repo.

## Requirements

- Python ≥ 3.11
- `sendsprint` CLI on PATH: `pip install sendsprint`
- Playwright browsers (for E2E step): `playwright install chromium`
- Credentials configured one-time: `sendsprint login jira` / `sendsprint login azuredevops`

## How it works

The plugin **never re-implements** the 10-step flow inside Claude. Every command shells out to the `sendsprint` CLI. Claude is used for:

- inputs disambiguation (which sprint? which workspace?),
- Ralph-style review/rework on artifacts produced by SendSprint,
- explaining failures and pushing scoped fixes.

See [AGENTS.md](../../AGENTS.md) for the canonical project rules.
