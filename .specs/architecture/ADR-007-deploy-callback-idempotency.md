# ADR-007: Keep deploy callbacks idempotent and non-blocking

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-05-18 |
| Deciders | wesleysimplicio |
| Supersedes | — |

---

## Context

Sprint 2 also adds `DeployTrigger`, which extends the delivery flow with an
optional webhook callback and a best-effort ticket status update after PR
creation.

The missing policy decisions were:

- whether deploy callback failure should fail the whole run;
- how to prevent duplicate deploy triggers on resumed runs or repeated commands;
- how ticket status updates should behave when the webhook succeeds but the
  backlog provider rejects the state transition.

SendSprint already treats the PR as the primary delivery artifact. The deploy
callback is an integration hook, not the system of record.

---

## Decision

Deploy callbacks are an **opt-in, post-PR, idempotent hook**.

Implementation rules:

1. The hook is disabled by default: `deploy.enabled = false`.
2. The orchestrator runs it only after a PR exists; no PR means the deploy step
   is skipped explicitly.
3. Every webhook request carries:
   - `Idempotency-Key: sha256(run_id + ":" + item_key)[:32]`
4. Retry policy is conservative:
   - retry transport errors and HTTP `5xx`
   - do not retry HTTP `4xx`
5. Webhook failure must not erase the successful PR outcome:
   the deploy step may fail, but the PR remains the source of truth.
6. Ticket status updates are best-effort:
   operators attempt the state change plus comment, and failures are logged
   without crashing the whole flow.

---

## Consequences

### Positive

- Re-running the same sprint item does not spam downstream deploy hooks with a
  different idempotency key.
- Operational teams can wire status transitions to Jira or Azure DevOps without
  turning those APIs into hard blockers for PR creation.
- The run report shows deploy callback health separately from code validation.

### Negative

- A successful PR can coexist with a failed deploy hook, so operators must read
  the report rather than assuming the final hook always ran.
- Ticket state transitions depend on provider workflow availability; some Jira
  workflows may not expose the requested final status.

---

## Alternatives considered

### Make deploy success mandatory before delivery is considered complete

- Rejected because SendSprint's guaranteed artifact is the validated PR, not the
  downstream deployment environment.

### Use raw `run_id:item_key` as the idempotency key

- Rejected because hashing yields a stable short header value that works across
  providers with tighter header limits.

### Retry all non-2xx responses

- Rejected because `4xx` usually means a bad URL, auth, or payload shape, and
  blind retries only create spam.

---

## Links

- Issue: https://github.com/wesleysimplicio/SendSprint/issues/17
- Related issue: https://github.com/wesleysimplicio/SendSprint/issues/10
- Related ADRs: [ADR-004](./ADR-004-worktree-isolation.md), [ADR-008](./ADR-008-mcp-server-schema.md)
