---
description: Run `sendsprint doctor` to verify the local environment is ready for autonomous sprint delivery.
allowed-tools: Bash
---

Run the SendSprint readiness check:

```bash
sendsprint doctor $ARGUMENTS
```

Interpret the output:

- **green** rows → ready, no action needed.
- **yellow** rows → degraded but recoverable; suggest the fix (install missing tool, set env var, run `sendsprint login`).
- **red** rows → blocker; do **not** run `/sendsprint` until resolved.

If the user passed `--llm-codegen`, also report on the LLM provider check and cost ceiling.

When asked "am I ready?", answer ONLY with green/yellow/red counts and the first blocker, not the full table.
