---
name: full
description: Continuous autonomous delivery mode (`sendsprint full`).
exec: sendsprint full
---

Use only when the user explicitly asks for autonomous mode:

```bash
sendsprint full --workspace workspace.yaml
```

Hermes wraps the loop, tracks per-cycle outcomes, and stops when:

- the workspace is drained, OR
- the configured cycle budget is reached, OR
- a red doctor/preflight check appears.

Never plow through a red blocker.
