#!/usr/bin/env bash
# PostToolUse hook for Python edits on POSIX shells.
# Best effort: format/check only the edited file and never blocks the agent flow.

set -u

payload="$(cat)"

file_path=""
success="true"
if command -v jq >/dev/null 2>&1; then
  file_path="$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.path // empty')"
  success="$(printf '%s' "$payload" | jq -r '.tool_response.success // true')"
else
  file_path="$(printf '%s' "$payload" | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/')"
fi

[ -z "$file_path" ] && exit 0
[ "$success" = "false" ] && exit 0
[ "${file_path##*.}" != "py" ] && exit 0
[ ! -f "$file_path" ] && exit 0

case "$file_path" in
  */.venv/*|*/venv/*|*/node_modules/*|*/dist/*|*/build/*|*/.tox/*) exit 0 ;;
esac

if command -v ruff >/dev/null 2>&1; then
  ruff format "$file_path" >/dev/null 2>&1 || true
  ruff check "$file_path" --output-format=concise >/dev/null 2>&1 || true
elif command -v python >/dev/null 2>&1; then
  python -m ruff format "$file_path" >/dev/null 2>&1 || true
  python -m ruff check "$file_path" --output-format=concise >/dev/null 2>&1 || true
fi

exit 0
