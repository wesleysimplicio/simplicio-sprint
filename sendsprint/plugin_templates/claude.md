---
name: sendsprint
description: SendSprint plugin for Claude Code. Delegates sprint delivery to the local Python CLI and web control plane.
platform: claude-code
---

# SendSprint Plugin

Use this plugin when the user asks to run, watch, deliver, or inspect a Jira, Azure DevOps, or GitHub-backed sprint with SendSprint.

## Runtime Contract

- Canonical runtime: Python CLI (`sendsprint`).
- Dashboard: `sendsprint web` opens the local UI at `http://localhost:8081`.
- Continuous execution: `sendsprint full --workspace workspace.yaml`.
- Single execution: `sendsprint sprint` or `sendsprint run <provider> <id>`.
- Never store Jira or Azure DevOps tokens in prompts or repo files. Credentials live in the OS keyring.

## Required Behavior

1. Run `sendsprint doctor` before the first delivery run when the environment is unknown.
2. Run `sendsprint web` when the user wants to monitor progress locally.
3. Prefer `sendsprint sprint` for default profile-driven delivery.
4. Prefer `sendsprint full --workspace workspace.yaml` for continuous watch/full mode.
5. Surface the PR URL, run report, evidence path, and blockers after completion.
6. Do not reimplement the 10-step flow inside Claude. Use the CLI.

## Claude-Specific Loop

Use Ralph-style review/rework only around SendSprint outputs:

- read the run report;
- inspect failed validation or review steps;
- apply a scoped fix only when SendSprint identifies a concrete blocker;
- rerun the focused SendSprint command or validation command.

## Commands

```bash
sendsprint doctor
sendsprint web
sendsprint sprint
sendsprint full --workspace workspace.yaml
sendsprint run jira 42 --workspace workspace.yaml --scope mine
sendsprint run azuredevops "Project\\Team\\Sprint 12" --workspace workspace.yaml
```

