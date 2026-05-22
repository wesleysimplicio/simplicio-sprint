---
name: inspect-run
description: Forensic inspection of a SendSprint run — cost, step durations, evidence.
exec: sendsprint sprint inspect
---

```bash
sendsprint sprint inspect {{RUN_ID}} --cost
```

Report:

- total wall-clock time and per-step durations,
- LLM token cost (if `--cost` produces data),
- evidence files present (Playwright screenshots, test outputs),
- the Ralph fix-loop round count.

Highlight outliers: any step > 5 minutes, any cost > $1, any missing evidence for a `passed` step.
