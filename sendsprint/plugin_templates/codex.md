---
name: sendsprint
description: SendSprint plugin for Codex. Delegates work to the local Python CLI and keeps Codex as planner, reviewer, and repair agent.
platform: codex
---

# SendSprint Plugin

Use this plugin when the user asks Codex to deliver sprint work, run SendSprint, monitor a local dashboard, or process Jira/Azure DevOps/GitHub work items.

## Runtime Contract

- Canonical runtime: Python CLI (`sendsprint`).
- Local dashboard: `sendsprint web`.
- Goal loop: use Codex `/goal` around SendSprint commands only when the user asks for a long-running autonomous loop.
- Continuous mode: `sendsprint full --workspace workspace.yaml`.
- Default mode: `sendsprint sprint`.

## Required Behavior

1. Check the real repo state before invoking write actions.
2. Run `sendsprint doctor` when dependency readiness is unknown.
3. Run `sendsprint web` when the user wants localhost monitoring.
4. Use `sendsprint sprint` for profile-driven execution.
5. Use `sendsprint full --workspace workspace.yaml` for looping watch/full mode.
6. Do not duplicate the SendSprint pipeline in Codex. Invoke the CLI and inspect its artifacts.
7. Report exact commands, test evidence, blockers, PR URLs, and next actions.

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

