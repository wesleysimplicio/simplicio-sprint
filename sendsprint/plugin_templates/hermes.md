---
name: sendsprint
description: SendSprint plugin for Hermes Agent. Uses SendSprint as the local sprint control plane and delivery executor.
platform: hermes
---

# SendSprint Plugin

Hermes should use SendSprint as an external sprint execution module, not as copied internal logic.

## Runtime Contract

- Runtime: Python CLI (`sendsprint`).
- Dashboard: `sendsprint web`.
- Full mode: `sendsprint full --workspace workspace.yaml`.
- One-shot: `sendsprint sprint` or `sendsprint run <provider> <id>`.
- Evidence and state are written under `.sendsprint/` and `evidence/`.

## Required Behavior

1. Start with `sendsprint doctor` when machine readiness is unknown.
2. Start `sendsprint web` for local monitoring.
3. Use `sendsprint full --workspace workspace.yaml` for continuous autonomous delivery.
4. Use SendSprint evidence, readiness score, quality gate, and run report before claiming completion.
5. Prefer review/consolidation when an area already has active PRs.
6. For OSS contribution mode, check duplicates before implementation.

## Commands

```bash
sendsprint doctor
sendsprint web
sendsprint sprint
sendsprint full --workspace workspace.yaml
sendsprint catalog list
sendsprint sprint snapshot
```

