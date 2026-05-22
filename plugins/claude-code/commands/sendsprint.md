---
description: Run the SendSprint 10-step sprint delivery flow (Jira/ADO → PR). Uses the cached profile + OS keyring credentials.
argument-hint: "[provider] [sprint-id] [--workspace path] [--scope mine]"
allowed-tools: Bash, Read, Edit, Write
---

You are about to run the **SendSprint sprint delivery flow** end-to-end.

## Pre-flight

1. If `$ARGUMENTS` is empty → use `sendsprint sprint` (profile + cached defaults).
2. If `$ARGUMENTS` begins with `jira <id>` or `azuredevops <iter>` → use `sendsprint run $ARGUMENTS`.
3. Always honour `--workspace` and `--scope` if the user supplied them.

## Execution

Run the command with `Bash`:

```bash
sendsprint sprint $ARGUMENTS
```

(or `sendsprint run $ARGUMENTS` when provider+id were given).

## After it finishes

- Print the **summary** block from `RunReport.summary` (already on stdout).
- Surface the **PR URL(s)** from `RunReport.prs[]`.
- If `RunReport.failed == true`, show the failing step and propose a scoped fix — do **not** rerun blindly.
- If the report mentions security findings, flag-only — never auto-fix (ADR-005).
- Write the JSON report to `report.json` if not already written.

## Definition of Done

See [DoD checklist in SKILL.md](../skills/sendsprint/SKILL.md#definition-of-done).
