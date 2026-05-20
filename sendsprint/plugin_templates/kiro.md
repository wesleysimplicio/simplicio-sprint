---
description: SendSprint steering rule for Kiro. Uses SendSprint as the local sprint-to-PR execution engine.
---

# SendSprint Steering

Use SendSprint when the user asks to deliver sprint work, run Jira/Azure DevOps tasks, inspect a sprint, or monitor the local dashboard.

## Runtime Contract

- Canonical runtime: Python CLI (`sendsprint`).
- Local dashboard: `sendsprint web`.
- Profile-driven run: `sendsprint sprint`.
- Continuous mode: `sendsprint full --workspace workspace.yaml`.
- Secrets must stay in the OS keyring and must not be written to prompts or repo files.

## Behavior

1. Run `sendsprint doctor` when dependency readiness is unknown.
2. Use the CLI and generated artifacts as source of truth.
3. Do not duplicate the SendSprint 10-step flow inside Kiro.
4. For failures, inspect the run report, evidence, and validation output before changing code.
5. Report exact commands, PR URL, evidence path, blockers, and next actions.

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
