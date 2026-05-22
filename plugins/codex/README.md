# SendSprint — Codex CLI plugin

Drop-in Codex plugin that wires the `sendsprint` Python CLI as the canonical sprint delivery engine inside Codex.

## What you get

- **`AGENTS.md`** — instruction file Codex auto-loads from repo root.
- **`config.toml`** — Codex CLI config snippet (sandbox, approval, `[features].goals = true`, safe_commands).
- **`prompts/`** — slash prompts (`/sendsprint`, `/sendsprint-doctor`, `/sendsprint-watch`, `/sendsprint-full`).
- **`hooks/`** — pre-commit + post-edit shell hooks + `hooks.json`.

Codex uses the SendSprint CLI as the executor and stays as **planner + reviewer + repair agent** around it.

## Install

### Option A — drop into your Codex profile

```bash
mkdir -p ~/.codex/plugins
cp -r plugins/codex ~/.codex/plugins/sendsprint
```

Then in your repo:

```bash
# Copy AGENTS.md to repo root so Codex picks it up
cp ~/.codex/plugins/sendsprint/AGENTS.md ./AGENTS.md

# Append the config snippet to the project codex config
mkdir -p .codex
cat ~/.codex/plugins/sendsprint/config.toml >> .codex/config.toml
```

### Option B — via `sendsprint plugins install`

```bash
sendsprint plugins install --platform codex --packaged
```

Copies the full plugin tree into `.codex/plugins/sendsprint/` and merges `AGENTS.md` / `.codex/config.toml` for you.

## Requirements

- [Codex CLI ≥ 0.128.0](https://github.com/openai/codex) (`goals` feature).
- `sendsprint` on PATH: `pip install sendsprint`.
- One-time login: `sendsprint login jira` / `sendsprint login azuredevops`.

## How it integrates

Codex `/goal` loop is wrapped **around** SendSprint commands — never used as a substitute. The plugin's prompts always shell out to `sendsprint sprint` / `sendsprint run` and let Codex inspect the artifacts (`report.json`, `evidence/`, PR URL) for the next iteration.

See [AGENTS.md](./AGENTS.md) in this folder for the full Codex contract.
