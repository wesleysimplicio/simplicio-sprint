---
name: sendsprint-full
description: Run `sendsprint full` (continuous autonomous delivery wrapped in a Codex /goal loop).
---

Wrap the continuous delivery in a Codex goal loop. Use this only when the user explicitly asks for long-running autonomous mode.

```bash
sendsprint full --workspace workspace.yaml {{ARGS}}
```

Codex `/goal` should:

1. Track the run report after each cycle.
2. Stop when the workspace is drained (no eligible items) OR after the configured cycle budget.
3. Surface PR URLs per cycle, not the raw step-by-step output.
4. Pause on red doctor / red preflight, never plow through.
