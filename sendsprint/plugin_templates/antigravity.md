---
name: sendsprint
description: SendSprint plugin for Antigravity. Delegates sprint delivery to the local Python CLI and control plane.
---

# SendSprint Plugin

Use this rule when the user asks Antigravity to deliver sprint work, process Jira/Azure DevOps/GitHub items, run SendSprint, or monitor the localhost dashboard.

## Runtime Contract

- Canonical runtime: `sendsprint`.
- Local dashboard: `sendsprint web`.
- Default execution: `sendsprint sprint`.
- Continuous mode: `sendsprint full --workspace workspace.yaml`.
- Credentials are managed by SendSprint in the OS keyring.

## Required Behavior

1. Check repo state before write actions.
2. Run `sendsprint doctor` if the environment is unknown.
3. Invoke the SendSprint CLI instead of reimplementing delivery logic.
4. Inspect run reports, evidence bundles, and quality gates before repair work.
5. Report PR URLs, validation status, evidence path, blockers, and next actions.

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
