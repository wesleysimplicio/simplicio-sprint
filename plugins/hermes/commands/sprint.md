---
name: sprint
description: Run the full SendSprint 10-step delivery flow.
exec: sendsprint sprint
---

Default delivery command. Uses the cached profile + OS keyring credentials.

## Usage

```
/sprint                                    # default profile, scope=mine
/sprint jira 42                            # explicit Jira sprint
/sprint azuredevops "Team\\Sprint 12"      # explicit ADO iteration
/sprint --workspace ./workspace.yaml       # override workspace
```

## After execution

- Print summary + PR URLs.
- Persist `report.json`.
- On `failed=true`, surface the failing step and propose ONE scoped fix.
