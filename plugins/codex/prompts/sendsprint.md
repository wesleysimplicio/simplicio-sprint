---
name: sendsprint
description: Run the SendSprint 10-step delivery flow on the current sprint.
---

You are running the **SendSprint delivery flow** through the Codex CLI.

## Inputs

If the user provided arguments, use them. Otherwise:

1. Read the cached profile via `sendsprint sprint` (zero-arg).
2. Only ask for provider/sprint id when no cache is available.

## Execution

```bash
sendsprint sprint {{ARGS}}
```

Or, when provider + id are explicit:

```bash
sendsprint run {{ARGS}}
```

## After

- Print `RunReport.summary` and PR URL(s).
- If `failed=true`, identify the failing step, propose ONE scoped fix, then rerun the focused validation only.
- Persist `report.json`.
- Never auto-fix security findings (ADR-005 — flag-only).
