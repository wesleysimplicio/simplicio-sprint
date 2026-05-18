# Ralph Validation Target — `llm-project-mapper`

This note explains how Sprint 1 validation should be interpreted for SendSprint.

## Canonical interpretation

When Sprint 1 says "Ralph", it refers to:

- the Ralph Wiggum skill in Claude Code (`/ralph-loop ...`)
- the equivalent `/goal ...` command in Codex

It does **not** mean the legacy standalone `ralph` binary as the primary proof surface.

## Canonical pilot repo

The target repo for the autonomous-loop validation is:

- `wesleysimplicio/llm-project-mapper`

The purpose of the experiment is to prove that SendSprint's task/spec contract is usable by an external host repo, not only by SendSprint itself.

## Evidence expected

At least one of these paths should be recorded before closing Sprint-1 validation issues:

1. Claude Code Ralph Wiggum skill completes the mapped pilot task flow in `llm-project-mapper`.
2. Codex `/goal` completes the mapped pilot task flow in `llm-project-mapper`.
3. The run stops with a concrete blocker and leaves enough evidence to diagnose the host/tooling gap.

## Current validation result

Path `3` is now satisfied with concrete blocker evidence from the current
`wesleysimplicio/llm-project-mapper` checkout.

### Commands executed

```bash
taskflow inspect /Users/wesleysimplicio/Projetos/skills/llm-project-mapper
npm run lint
npm test
gh issue list --repo wesleysimplicio/llm-project-mapper --state open --limit 20
ls -la /Users/wesleysimplicio/Projetos/skills/llm-project-mapper/.plans
```

### Observed evidence

- `taskflow inspect` resolved the repo as a Node project and the local automation surface is healthy.
- `npm run lint` passed.
- `npm test` passed with `33` passing and `5` skipped tests.
- The GitHub repo had no open issues at the moment of validation.
- `.plans/` is absent in the pilot repo.
- The current sprint/task files in `.specs/sprints/sprint-01/` are still illustrative placeholders, not a real two-task autonomous pilot backlog.

### Why this is a blocker

The old SendSprint-local acceptance for Sprint 1 assumed a legacy `.plans/`
loop and concrete task progression artifacts. After the maintainer clarified
that the canonical pilot is `llm-project-mapper` and the tools are Claude
Code's Ralph Wiggum skill or Codex `/goal`, the actual host-repo blocker
became:

- the pilot repo does not expose a real two-task sprint prepared for autonomous
  closure;
- the old `.plans/prd.json` and `.plans/progress.txt` artifacts are not part of
  the target repo contract;
- there is no honest way to claim the original validation acceptance happened
  end to end against the current pilot repo without inventing tasks or
  backfilling artifacts that the repo does not currently own.

### Closure interpretation

For SendSprint, this validation issue can be closed as **resolved with blocker
evidence recorded**: the product contract is now correct, and the remaining gap
is in the external pilot repo readiness rather than inside SendSprint itself.

## Non-goals

- Proving a self-hosted `ralph run` flow inside SendSprint only.
- Treating the old standalone `ralph` CLI as the sole acceptance path.
