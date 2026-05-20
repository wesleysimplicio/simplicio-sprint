---
name: sendsprint
description: SendSprint plugin for GitHub Copilot. Provides repo instructions that delegate sprint delivery to the Python CLI.
platform: github-copilot
---

# SendSprint Plugin

When the user asks Copilot to run SendSprint, deliver sprint tasks, process Jira/Azure DevOps/GitHub work, or monitor the local dashboard, use the SendSprint CLI.

## Runtime Contract

- Runtime: Python CLI (`sendsprint`).
- Local UI: `sendsprint web`.
- Default delivery: `sendsprint sprint`.
- Continuous delivery: `sendsprint full --workspace workspace.yaml`.
- Credentials: OS keyring only.

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

## Rules

- Do not manually duplicate the SendSprint pipeline.
- Do not commit secrets or write PAT/API tokens to files.
- Use SendSprint reports, evidence bundles, readiness scores, and PR links as source of truth.
- Surface blockers and exact validation commands.

