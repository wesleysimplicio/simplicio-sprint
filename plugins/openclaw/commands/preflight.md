---
name: preflight
description: Validate inputs and credentials before any delivery write happens.
exec: sendsprint preflight
---

```bash
sendsprint preflight {{ARGS}}
```

OpenClaw runs the preflight and reports in two lines:

1. `READY` or `BLOCKED` with the single most important reason.
2. The exact next action (one specific fix, or `/sprint` if green).

Never proceed to delivery from OpenClaw — that's another plugin's job.
