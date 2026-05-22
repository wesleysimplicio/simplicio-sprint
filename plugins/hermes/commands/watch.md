---
name: watch
description: Continuously deliver new sprint items as they appear.
exec: sendsprint watch
---

Long-running. Defaults: `sendsprint watch --workspace workspace.yaml --scope mine`.

Hermes should run this in background, print PID + log path, and suggest `/web` for live monitoring. Do not stream the entire output back into the chat.
