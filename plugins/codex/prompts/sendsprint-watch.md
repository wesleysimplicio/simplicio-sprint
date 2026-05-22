---
name: sendsprint-watch
description: Start `sendsprint watch` to deliver new sprint items continuously.
---

```bash
sendsprint watch {{ARGS:--workspace workspace.yaml --scope mine}}
```

This is long-running. Spawn it via Codex background execution and:

- print the PID + log path,
- remind the user how to stop it,
- suggest `sendsprint web` (`http://localhost:8081`) for live monitoring.

Do not poll the watch output yourself.
