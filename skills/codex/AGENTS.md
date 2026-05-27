---
name: sendsprint
description: Autonomous sprint delivery via the sendsprint CLI + simplicio-cli executor.
command: sendsprint
version: 1.1.0
platform: codex
---

# SendSprint — Codex rule

You are the agent. The `sendsprint` CLI is your tooling; **simplicio-cli** is the
executor. Never reimplement the flow — shell out to the CLI.

## When to run

Trigger phrases: "run sendsprint", "rode o sendsprint", "executar sprint",
"deliver my sprint", "ejecutar sprint". Also when the user names a sprint id +
source (jira/azuredevops/github) + repo.

## Command

```bash
sendsprint run <jira|azuredevops|github> <sprint> \
  --repo <path> --repo-slug <owner/repo> --scope mine
```

Each card → simplicio-mapper spec (`.specs/`) → `simplicio task` → evidence
(tests + screenshot) → commit → draft PR → ticket "In Review". The draft PR is
the user's review surface. `--fanout` adds a simplicio-prompt subagent brainstorm
per card (opt-in); `--no-specs` skips the spec.

MCP is host-driven: register the tenant data via
`sendsprint.operators._mcp_bridge.register_provider(<source>, fn)` before
reading, else it falls back to REST.

## Unattended

`sendsprint watch <source> <sprint> --repo <path> --repo-slug <owner/repo> --once`
from a cron / CI schedule.

## Prereqs

`pip install -e . && pip install simplicio-cli`. `sendsprint update` pulls the
latest simplicio-cli / -prompt / -mapper (also at start per the profile;
`--no-update` to skip). Credentials via `sendsprint login <provider>` or env
vars (`GITHUB_TOKEN` for GitHub).
