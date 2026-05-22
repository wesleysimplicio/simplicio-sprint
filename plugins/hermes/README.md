# SendSprint — Hermes Agent plugin

Plugin package for [Hermes](https://hermes-agent.dev) that registers SendSprint as the local sprint control plane and delivery executor.

## What you get

- `hermes-plugin.json` — Hermes-compatible plugin manifest.
- `skills/sendsprint.md` — full skill manifest with triggers, steps, DoD.
- `commands/` — `sprint`, `doctor`, `watch`, `full`, `web`.
- `hooks/` — pre-commit, post-edit, session-start shell hooks.

## Install

### Option A — Hermes plugin folder

```bash
mkdir -p ~/.hermes/plugins
cp -r plugins/hermes ~/.hermes/plugins/sendsprint
```

Hermes auto-loads any `~/.hermes/plugins/*/hermes-plugin.json` on startup.

### Option B — via the SendSprint CLI

```bash
sendsprint plugins install --platform hermes --packaged
```

Copies the tree into `.hermes/plugins/sendsprint/` inside the current repo.

## Requirements

- Hermes Agent ≥ 1.0.
- `sendsprint` on PATH (`pip install sendsprint`).
- One-time login: `sendsprint login jira` / `sendsprint login azuredevops`.

## Boundary

Hermes treats SendSprint as an **external module**. The plugin never re-implements the 10-step flow; it always invokes the CLI and inspects:

- `report.json` (final run report)
- `evidence/` (Playwright screenshots, test outputs)
- `RunReport.summary` (includes `RALPH_STATUS` block)
- `RunReport.prs[]` (created PR URLs)

For OSS contribution mode, the plugin runs `sendsprint catalog list` and dedup checks before kicking off delivery.

See [skills/sendsprint.md](./skills/sendsprint.md) for the canonical contract.
