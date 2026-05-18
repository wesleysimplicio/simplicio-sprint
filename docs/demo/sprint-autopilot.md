# Sprint Autopilot Demo

This demo is credential-light and can be run as a dry-run to prove the operator
surface before connecting real Jira/Azure/GitHub trackers.

## Scenario

The operator wants to finish a sprint with:

- transcript-derived task candidates;
- GitHub Issues as the review/apply tracker;
- a dry-run plan that lists repos, branches, worktrees, validation templates,
  LLM budget, deploy callback state, and allowed side effects;
- a portable evidence bundle and executive summary at the end.

## Dry-Run Commands

```bash
.venv/bin/sendsprint doctor --repo .
.venv/bin/sendsprint templates
.venv/bin/sendsprint ingest-transcript docs/demo/transcript-sample.txt \
  -o /tmp/sendsprint-transcript-tasks.json
.venv/bin/sendsprint run jira 42 --repo . --dry-run \
  --plan-output /tmp/sendsprint-plan.json
```

## Apply-Mode Boundary

Creating issues from transcript candidates requires explicit policy:

```bash
.venv/bin/sendsprint ingest-transcript docs/demo/transcript-sample.txt \
  --github-repo wesleysimplicio/SendSprint \
  --apply \
  --autonomy pr
```

Without `--autonomy pr`, the command stays in review mode.

## Expected Artifacts

- `doctor` table with GitHub, git, Python, Playwright, LLM, and validation
  template readiness.
- Transcript task JSON with source line traceability and redaction flags.
- Delivery plan JSON with branch/worktree/template/policy metadata.
- Evidence bundle from `sendsprint bundle-evidence <report.json>`.
- Executive report from `sendsprint executive-report <report.json>`.
