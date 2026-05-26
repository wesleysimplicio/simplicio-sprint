# CLAUDE.md

Claude-specific notes for SendSprint. **Read [AGENTS.md](./AGENTS.md) FIRST** —
it's the canonical source. This file only adds Claude-specific behavior.

## You are the agent

SendSprint is not a separate program with its own intelligence — **you are the
agent**. The `sendsprint` CLI is your tooling; `simplicio-cli` is the executor
you call per task. The skill is just the trigger + procedure.

## Skill invocation

When the user says any of — pt-BR: "rode o sendsprint", "executar sprint",
"entregar sprint"; en: "run sendsprint", "ship my sprint", "deliver my sprint";
es: "ejecutar sprint"; or `/sendsprint` — run the flow per
[`skills/claude/SKILL.md`](./skills/claude/SKILL.md):

```bash
sendsprint run <jira|azuredevops|github> <sprint> --repo . --repo-slug owner/repo --scope mine
```

## Unattended

For "finish my cards without me", the user wants a trigger, not manual
invocation. Use a scheduled `sendsprint watch ... --once` (GitHub Action, cron,
or a Claude Code on the web scheduled trigger). The PR review loop can also be
driven by `subscribe_pr_activity` reacting to review events.

## Tool preferences

- Edit > Write for existing files; read before editing.
- Bash only for tests/lint/git — never to read or write file content.
- Run `pytest tests/ -q` and `ruff check sendsprint/` before committing.
