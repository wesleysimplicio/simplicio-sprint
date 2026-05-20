---
name: sendsprint
description: SendSprint plugin for OpenClaw. Uses OpenClaw as an independent review and security agent around SendSprint runs.
platform: openclaw
---

# SendSprint Plugin

OpenClaw should use SendSprint as the canonical sprint executor and focus on review, security, and independent validation.

## Runtime Contract

- Runtime: Python CLI (`sendsprint`).
- Dashboard: `sendsprint web`.
- Evidence source: `.sendsprint/`, `evidence/`, run reports, PR links.
- Security behavior: flag-only for secrets and risky changes.

## Required Behavior

1. Run or inspect `sendsprint doctor` before validating an unknown environment.
2. Use SendSprint run reports and evidence bundles as the review input.
3. Prefer `sendsprint run ... --dry-run` before risky delivery.
4. Review diff, test evidence, security findings, and PR body completeness.
5. Do not bypass SendSprint's policy gates.

## Commands

```bash
sendsprint doctor
sendsprint preflight jira 42 --workspace workspace.yaml
sendsprint run jira 42 --workspace workspace.yaml --dry-run
sendsprint sprint inspect <run_id> --cost
```

