---
description: Run a SendSprint preflight (dry-run validation) before delivering a sprint.
argument-hint: "<provider> <sprint-id> [--workspace path]"
allowed-tools: Bash
---

Preflight validates inputs, credentials and workspace **without** writing commits or PRs:

```bash
sendsprint preflight $ARGUMENTS
```

Use this whenever:

- the user is about to run `/sendsprint` on a sprint they have not delivered before,
- they changed their `workspace.yaml`,
- they rotated Jira/ADO credentials.

Report the preflight verdict in two lines:

1. `READY` / `BLOCKED` and the reason.
2. The next recommended command (`/sendsprint` if green, the specific fix if red).
