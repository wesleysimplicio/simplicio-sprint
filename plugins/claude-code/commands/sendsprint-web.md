---
description: Start the local SendSprint web dashboard at http://localhost:8081.
argument-hint: "[--port 8081] [--host 127.0.0.1]"
allowed-tools: Bash
---

Start the dashboard in the background so the user can monitor runs in the browser:

```bash
sendsprint web $ARGUMENTS
```

After launch:

- print the URL (default `http://localhost:8081`),
- confirm the process is listening,
- if a port is already in use, suggest `--port 8082` (or whatever is free).

Do **not** open the URL on the user's behalf — just print it.
