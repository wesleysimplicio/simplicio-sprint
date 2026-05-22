# SendSprint — Multi-host plugin packages

SendSprint ships as a **plugin** for four AI coding hosts:

| Host | Folder | Manifest | Install target |
|---|---|---|---|
| [Claude Code](./claude-code/) | `plugins/claude-code/` | `.claude-plugin/plugin.json` | `~/.claude/plugins/sendsprint/` |
| [Codex CLI](./codex/) | `plugins/codex/` | `plugin.toml` + `AGENTS.md` + `config.toml` | `~/.codex/plugins/sendsprint/` |
| [Hermes Agent](./hermes/) | `plugins/hermes/` | `hermes-plugin.json` | `~/.hermes/plugins/sendsprint/` |
| [OpenClaw](./openclaw/) | `plugins/openclaw/` | `openclaw-plugin.json` | `~/.openclaw/plugins/sendsprint/` |

All four packages share the same **runtime contract**: the SendSprint Python CLI (`sendsprint`) is the canonical executor — the host plugins delegate to it and never re-implement the 10-step flow.

## Install any plugin

### CLI (recommended)

```bash
# All four
sendsprint plugins install --packaged --all

# Just one
sendsprint plugins install --packaged --platform claude
sendsprint plugins install --packaged --platform codex
sendsprint plugins install --packaged --platform hermes
sendsprint plugins install --packaged --platform openclaw
```

### Manual

Each subfolder has a `README.md` with the host-specific install path and required env vars.

## Common requirements

- `pip install sendsprint` (Python ≥ 3.11).
- `playwright install chromium` for the E2E step.
- One-time credentials in the OS keyring: `sendsprint login jira` / `sendsprint login azuredevops`.

## Plugin contracts

| Plugin | Role | Writes commits/PRs? | Auto-fixes security? |
|---|---|---|---|
| claude-code | full delivery + review | yes (via CLI) | no (ADR-005) |
| codex | full delivery + `/goal` loop | yes (via CLI) | no (ADR-005) |
| hermes | continuous delivery control plane | yes (via CLI) | no (ADR-005) |
| openclaw | independent reviewer + security | **no** | **no** |

OpenClaw is intentionally **read-only-by-default** — it cross-checks SendSprint's artifacts (`report.json`, `evidence/`, PR diff) without touching the repo.

## See also

- [AGENTS.md](../AGENTS.md) — canonical project rules.
- [CLAUDE.md](../CLAUDE.md) — Claude Code-specific extension.
- [skills/](../skills/) — flat per-IDE rule files (legacy install mode).
