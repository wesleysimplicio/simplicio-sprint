# ADR-006: Keep LLM code generation opt-in with workspace/CLI budgeting

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-05-18 |
| Deciders | wesleysimplicio |
| Supersedes | — |

---

## Context

Sprint 2 adds `CodeGenerator`, an agent that can propose a unified diff for a
sprint item and hand that patch to the main delivery flow.

The open questions were:

- how to expose the feature without changing the default SendSprint contract;
- how to choose an LLM provider/model without hard-coding one paid vendor;
- how to keep accidental spend bounded when a sprint run touches many tasks.

The repository already had a provider-agnostic `LlmClient` plus optional extras
for Anthropic, OpenAI, Google, Groq, and Ollama. What it did not have was the
policy layer that decides when code generation may run and what limits apply.

---

## Decision

LLM code generation is shipped as an **opt-in hook** between build and lint.

Implementation rules:

1. The default flow remains unchanged: `code_generation.enabled = false`.
2. Enablement can come from either `workspace.yaml` or explicit CLI flags such as
   `--llm-codegen`; CLI flags override workspace defaults for that run.
3. Provider and model remain provider-agnostic:
   - `provider` may be `anthropic`, `openai`, `google`, `groq`, or `ollama`
   - `model` is optional and otherwise falls back to `LlmClient` defaults
4. Every codegen run is bounded by two hard guards:
   - `max_usd` default `1.0`
   - `max_tokens` default `8000`
5. Generated output must be a unified diff and still pass the normal gates:
   `git apply` -> lint -> tests -> PR review.
6. If code generation fails, the run does not crash silently:
   it produces a failed step report and the normal fix/review loop continues.

---

## Consequences

### Positive

- Teams can opt into code generation repo-by-repo or run-by-run without
  surprising existing automations.
- The project keeps a single LLM abstraction instead of coupling the flow to one
  vendor SDK or one API key shape.
- Budget caps are explicit in config and visible in the run report message.

### Negative

- The flow now has one extra moving part between build and lint, so bad diffs
  may fail earlier in the pipeline.
- Cost estimation is approximate rather than provider-billed exact.
- Users still need provider credentials or a local Ollama endpoint when they
  enable the hook.

---

## Alternatives considered

### Enable codegen by default

- Rejected because it would change the default operational contract and surprise
  teams that expect deterministic non-LLM delivery.

### Hard-code Anthropic as the only provider

- Rejected because the repo already ships a multi-provider LLM client and the
  product targets heterogeneous environments.

### Allow unlimited tokens/spend and rely on vendor-side quotas

- Rejected because sprint runs can touch many items, and local config should
  guard cost before network calls become habitual.

---

## Links

- Issue: https://github.com/wesleysimplicio/SendSprint/issues/17
- Related issue: https://github.com/wesleysimplicio/SendSprint/issues/9
- Related ADRs: [ADR-004](./ADR-004-worktree-isolation.md), [ADR-005](./ADR-005-flag-only-security.md)
