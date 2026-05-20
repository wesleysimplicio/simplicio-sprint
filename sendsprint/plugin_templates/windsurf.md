---
description: SendSprint plugin for Windsurf. Delegates sprint delivery to the local Python CLI and localhost control plane.
trigger: always_on
---

# SendSprint Plugin

When the user asks to run SendSprint, deliver sprint work, process Jira/Azure DevOps items, or open the dashboard, use the SendSprint Python CLI.

## Runtime Contract

- Canonical runtime: `sendsprint`.
- Dashboard: `sendsprint web`.
- Default execution: `sendsprint sprint`.
- Continuous execution: `sendsprint full --workspace workspace.yaml`.
- Credentials stay in the OS keyring through SendSprint auth/login flows.

## Rules

- Do not reimplement the SendSprint delivery pipeline inside Windsurf.
- Inspect SendSprint reports and evidence before applying repair work.
- Keep fixes scoped to the blocker reported by SendSprint.
- Report PR URL, run report, evidence path, validation results, and blockers.

## Commands

```bash
sendsprint doctor
sendsprint web
sendsprint sprint
sendsprint watch --workspace workspace.yaml
sendsprint full --workspace workspace.yaml
sendsprint run jira 42 --workspace workspace.yaml --scope mine
sendsprint run azuredevops "Project\\Team\\Sprint 12" --workspace workspace.yaml
```
