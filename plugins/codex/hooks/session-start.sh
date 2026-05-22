#!/usr/bin/env bash
# SendSprint Codex plugin — SessionStart hook.
cat <<'BANNER'
[SendSprint Codex plugin loaded]

Prompts:
  /sendsprint           run the 10-step delivery flow
  /sendsprint-doctor    readiness check
  /sendsprint-watch     continuous watch
  /sendsprint-full      autonomous /goal loop

Chat triggers: "rode o sendsprint" · "run sendsprint" · "ejecutar sprint".
Credentials: OS keyring via `sendsprint login jira` / `sendsprint login azuredevops`.
BANNER
