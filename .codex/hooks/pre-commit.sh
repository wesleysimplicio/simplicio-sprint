#!/usr/bin/env bash
# PreToolUse hook for git commit on POSIX shells.
# Blocks only when staged Python changes fail the local Python quality gate.

set -u

payload="$(cat)"

cmd=""
if command -v jq >/dev/null 2>&1; then
  cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')"
else
  cmd="$(printf '%s' "$payload" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/')"
fi

if [ -n "$cmd" ]; then
  case "$cmd" in
    *"git commit"*) ;;
    *) exit 0 ;;
  esac
  case "$cmd" in
    *"--no-verify"*|*"git commit --amend"*|*"git commit -m \"Merge"*) exit 0 ;;
  esac
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -z "$repo_root" ] && exit 0
cd "$repo_root" || exit 0

staged_python_files="$(git diff --cached --name-only --diff-filter=ACMR | grep '\.py$' || true)"
[ -z "$staged_python_files" ] && exit 0

failed=""

if command -v ruff >/dev/null 2>&1; then
  if ! printf '%s\n' "$staged_python_files" | xargs ruff check --select E9,F63,F7,F82 --output-format=concise >&2; then
    failed="${failed}ruff critical check, "
  fi
elif command -v python >/dev/null 2>&1; then
  if ! printf '%s\n' "$staged_python_files" | xargs python -m ruff check --select E9,F63,F7,F82 --output-format=concise >&2; then
    failed="${failed}ruff critical check, "
  fi
fi

if command -v pytest >/dev/null 2>&1; then
  if ! pytest tests -q >&2; then
    failed="${failed}pytest tests -q, "
  fi
elif command -v python >/dev/null 2>&1; then
  if ! python -m pytest tests -q >&2; then
    failed="${failed}pytest tests -q, "
  fi
fi

if [ -n "$failed" ]; then
  reason="pre-commit bloqueado: ${failed%, } falhou. Corrija antes do commit ou use --no-verify conscientemente."
  if command -v jq >/dev/null 2>&1; then
    printf '{"decision":"block","reason":%s}\n' "$(printf '%s' "$reason" | jq -Rs .)"
  else
    printf '{"decision":"block","reason":"%s"}\n' "$reason"
  fi
fi

exit 0
