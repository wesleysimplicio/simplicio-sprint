#!/usr/bin/env bash
# SendSprint Claude Code plugin — PostToolUse hook.
# Best-effort ruff format on edited Python files. Never blocks the agent.

set -u
payload="$(cat)"

file_path=""
if command -v jq >/dev/null 2>&1; then
  file_path="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.path // empty')"
else
  file_path="$(printf '%s' "$payload" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/')"
fi

[ -z "$file_path" ] && exit 0
[ "${file_path##*.}" != "py" ] && exit 0
[ ! -f "$file_path" ] && exit 0
case "$file_path" in
  */.venv/*|*/venv/*|*/node_modules/*|*/dist/*|*/build/*|*/.tox/*) exit 0 ;;
esac

if command -v ruff >/dev/null 2>&1; then
  ruff format "$file_path" >/dev/null 2>&1 || true
fi
exit 0
