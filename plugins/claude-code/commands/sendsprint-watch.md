---
description: Start `sendsprint watch` to continuously deliver new sprint items as they land in Jira/ADO.
argument-hint: "[--workspace workspace.yaml] [--scope mine]"
allowed-tools: Bash
---

Launch the continuous watch loop:

```bash
sendsprint watch $ARGUMENTS
```

Default: `sendsprint watch --workspace workspace.yaml --scope mine` when no args were passed.

This is a **long-running** command. Run it with `run_in_background: true` so the user keeps their session free. When started:

- print the PID and the log path,
- remind the user how to stop it (`Ctrl-C` in that shell, or `pkill -f "sendsprint watch"`),
- suggest `/sendsprint-web` to monitor live progress.

Do **not** poll the watch output yourself — the local dashboard or `tail -f` is the right tool for the user.
