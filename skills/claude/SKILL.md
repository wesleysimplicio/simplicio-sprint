---
name: sendsprint
description: Autonomous sprint delivery. Reads a Jira / Azure DevOps / GitHub sprint, delegates each task's code edit to simplicio-cli, captures evidence, and opens a draft PR. Triggers on "rode o sendsprint", "executar sprint", "entregar sprint", "run sendsprint", "ship my sprint", "deliver my sprint", "ejecutar sprint".
command: sendsprint
version: 1.0.0
platform: claude-code
---

# SendSprint — Claude Code skill

You are the agent. The `sendsprint` CLI is your tooling; **simplicio-cli** is the
executor you call per task. Do not reimplement the flow — shell out to the CLI.

## Trigger

Invoke when the user says (any language):

- pt-BR: "rode o sendsprint", "executar sprint", "entregar sprint", "faça minhas tarefas da sprint"
- en: "run sendsprint", "ship my sprint", "deliver my sprint", "process my Jira sprint"
- es: "ejecutar sprint", "procesar sprint"
- slash: `/sendsprint`

Also auto-invoke when the user mentions a sprint id + source + repo together.

## Run

```bash
sendsprint run <jira|azuredevops|github> <sprint> \
  --repo <path> --repo-slug <owner/repo> --scope mine
```

- `--scope mine` delivers only the cards assigned to the user.
- Each card → `simplicio task` → test + screen evidence → commit → **draft PR** → ticket "In Review".
- The PR is a draft on purpose: the user reviews and approves.

## Unattended

If the user wants it to run without them at the keyboard, set up a scheduled
trigger instead of invoking manually:

```bash
sendsprint watch <source> <sprint> --repo <path> --repo-slug <owner/repo> --once
```

from a GitHub Action / cron / Claude Code on the web scheduled trigger.

## PR review loop

After a PR exists, you can `subscribe_pr_activity` and, on
`CHANGES_REQUESTED`, the flow's `revise_pr` feeds the feedback back to
simplicio, re-collects evidence, and pushes — until the user approves.

## Prereqs

- `pip install -e . && pip install simplicio-cli`
- Credentials: `sendsprint login jira` / `sendsprint login azuredevops`; `GITHUB_TOKEN` for GitHub.
