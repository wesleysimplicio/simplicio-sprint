#!/usr/bin/env bash
# SendSprint Claude Code plugin — SessionStart hook.
# Reminds the user of available SendSprint commands and trigger phrases.

cat <<'EOF'
[SendSprint plugin loaded]

Commands:
  /sendsprint              run the 10-step delivery flow
  /sendsprint-doctor       readiness check
  /sendsprint-watch        continuous watch on a workspace
  /sendsprint-web          start the local dashboard
  /sendsprint-preflight    dry-run validation

Chat triggers (auto-invoke the `sendsprint` skill):
  pt-BR: "rode o sendsprint", "executar sprint", "entregar sprint"
  en:    "run sendsprint", "ship my sprint", "deliver sprint"
  es:    "ejecutar sprint", "procesar sprint"

Credentials live in the OS keyring (one-time `sendsprint login jira` / `sendsprint login azuredevops`).
EOF
