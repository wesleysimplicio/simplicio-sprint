# ADR-0001: Keep SendSprint as a Python-first local operator

- Status: Accepted
- Date: 2026-05-18
- Project: SendSprint

## Context

SendSprint coordinates tracker reads, repository mutation, tests, evidence, PRs,
and local dashboard status. The product has a Python package and CLI at the
center, with a FastAPI API and a separate web dashboard for local visualization.

## Decision

Keep the orchestration core in Python and treat the dashboard as a consumer of
the same run/report/evidence contracts instead of a second source of truth.

The authoritative flow remains:

- `sendsprint/cli.py` for operator entry points.
- `sendsprint/flow/sprint_flow.py` for the delivery sequence.
- `sendsprint/models/` for shared contracts.
- `sendsprint/api/` and `web/` for local visualization.

## Consequences

- New roadmap features should introduce reusable Python modules first, then
  wire CLI/API/dashboard surfaces on top.
- Side-effecting operations must be enforceable centrally, not only in UI code.
- Report and evidence schemas must remain stable enough for CLI, API, PR body,
  GitHub issue comments, and executive reports.
- JavaScript changes should mostly be presentation and type/schema alignment.

## Alternatives Considered

- Dashboard-first control plane: rejected because it would duplicate CLI state
  and weaken headless automation.
- Tracker-specific implementations: rejected because Jira, Azure DevOps, and
  GitHub Issues should share planning, policy, worktree, evidence, and report
  primitives.
