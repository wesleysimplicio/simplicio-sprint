#!/usr/bin/env bash
# SendSprint Claude Code plugin — PreToolUse hook for git commit.
# Blocks the commit when staged Python changes fail ruff critical or pytest.

set -u
payload="$(cat)"

cmd=""
if command -v jq >/dev/null 2>&1; then
  cmd="$(printf '%s' "$payload" | jq -r '.tool_input.command // empty')"
else
  cmd="$(printf '%s' "$payload" | grep -o '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 | sed 's/.*"command"[[:space:]]*:[[:space:]]*"\([^"]*\)"/\1/')"
fi

[ -z "$cmd" ] && exit 0
case "$cmd" in
  *"git commit"*) ;;
  *) exit 0 ;;
esac
case "$cmd" in
  *"--no-verify"*|*"git commit --amend"*) exit 0 ;;
esac

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[ -z "$repo_root" ] && exit 0
cd "$repo_root" || exit 0

staged_py="$(git diff --cached --name-only --diff-filter=ACMR | grep '\.py$' || true)"
[ -z "$staged_py" ] && exit 0

failed=""
if command -v ruff >/dev/null 2>&1; then
  printf '%s\n' "$staged_py" | xargs ruff check --select E9,F63,F7,F82 --output-format=concise >&2 \
    || failed="${failed}ruff critical, "
fi
if command -v pytest >/dev/null 2>&1; then
  pytest tests -q >&2 || failed="${failed}pytest tests -q, "
fi

if [ -n "$failed" ]; then
  reason="SendSprint pre-commit blocked: ${failed%, } failed. Fix before committing or pass --no-verify intentionally."
  if command -v jq >/dev/null 2>&1; then
    printf '{"decision":"block","reason":%s}\n' "$(printf '%s' "$reason" | jq -Rs .)"
  else
    printf '{"decision":"block","reason":"%s"}\n' "$reason"
  fi
fi

exit 0
