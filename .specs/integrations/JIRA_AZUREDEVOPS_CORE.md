# Jira and Azure DevOps Core Guide

Stable operating rules for agents working with Jira or Azure DevOps inside SendSprint.
Use this guide before changing operators, task planning, work-item creation, or PR
linking behavior.

## Decision

Keep a local core guide plus live transports.

- Local guide: stable semantics, safe defaults, hierarchy rules, fallback behavior.
- MCP: preferred for live organization/project data, user session, work-item CRUD, sprint content, and tool-specific capabilities.
- REST API: deterministic fallback when credentials are configured and MCP is unavailable.
- Playwright/browser: last fallback for authenticated UI-only flows or when API/MCP lacks access.

Do not copy large vendor documentation into the repo. Store only durable rules and
official source links; refresh details from MCP/API/vendor docs when behavior depends
on current tenant configuration.

## Transport Rules

Priority is always:

1. `mcp`
2. `api`
3. `playwright`

Do not reorder this chain. MCP is best for authenticated Azure DevOps/Jira workspace
operations because it sees the current account and installed tool capabilities. API is
best for repeatable automation and tests. Browser fallback is slow and should be used
only when the first two transports cannot answer or mutate the target.

## Azure DevOps Rules

### Identity

- Required stable profile fields: organization, project, and optionally team.
- Prefer project GUID when MCP path encoding fails for names with spaces, accents, or
  special characters.
- Never assume a project process. Agile, Scrum, CMMI, and inherited processes can have
  different backlog levels and work item types.

### Work Item Types

Normalize Azure DevOps types into SendSprint types:

- `User Story`, `Product Backlog Item` -> `Story`
- `Task` -> `Task`
- `Bug` -> `Bug`
- `Feature` -> `Feature`
- `Epic` -> `Epic`
- `Issue` -> `Issue`
- unknown -> `Issue`

### Hierarchy and Links

Before creating or preserving a parent-child relation, validate that the parent type is
allowed for the child in the current planning context.

Safe SendSprint default:

- `Story -> Task`: parent-child allowed.
- `Bug -> Task`: parent-child allowed.
- `Issue -> Task`: do not create as parent-child by default; use `Related`.
- Unknown parent type -> use `Related`, not parent-child.

Reason: Azure DevOps backlog views can reject same-category hierarchy or hierarchy
links where a work item is not shown on the current backlog level. A known symptom is:

```text
There is same category hierarchy on this backlog. You cannot reorder work items...
See work item(s) ... to either remove the parent to child link or change the link type to 'Related'.
```

Required behavior:

- Detect invalid `Task/Subtask.parent_key` when sprint source is `azuredevops`.
- Remove `parent_key` locally before delivery planning.
- Add a `Related` link to preserve traceability.
- When creating Azure work items, create the `Related` link instead of a hierarchy link
  for invalid combinations.
- Descriptions must say `related item`, not `parent item`, when the relationship is not
  a hierarchy relation.

### Fields

Use only fields confirmed by API/MCP or profile configuration:

- `System.Title`
- `System.Description`
- `System.WorkItemType`
- `System.State`
- `System.AreaPath`
- `System.IterationPath`
- `System.AssignedTo`
- `System.Tags`
- `Microsoft.VSTS.Common.AcceptanceCriteria`
- `Microsoft.VSTS.Scheduling.StoryPoints`

Do not assign users unless the source task already has an assignee or the user
explicitly requested assignment.

### Sprint Reads

When reading a sprint:

- Query by `System.IterationPath`.
- Include parent fields and relations when available.
- Preserve source URL for traceability.
- If the UI shows `New` work items, treat them as unclaimed unless an assignee exists.

### Pull Requests

Before creating an Azure DevOps PR:

- Push the source branch first; never create a PR from a branch that only exists locally.
- Link the originating work item by ID whenever possible.
- Preserve reviewer rules from `workspace.yaml`.
- Use `required_pr_reviewers` for project policies such as mandatory lead review.
- For Azure DevOps REST PR creation, send required reviewers with `isRequired: true`.
- If REST/MCP cannot create the PR but the authenticated browser can, capture the final PR
  URL, reviewers, linked work items, conflict status, and any evidence limitation.

## Jira Rules

### Identity

- Required stable profile fields: base URL and email/account identity.
- API token belongs in OS keyring only; never write it to repo files.
- Prefer account ID over display name for assignment/scope filtering.

### Issue Types

Normalize Jira issue types into SendSprint types:

- `Story`, `User Story` -> `Story`
- `Task` -> `Task`
- `Sub-task`, `Subtask` -> `Subtask`
- `Bug` -> `Bug`
- `Epic` -> `Epic`
- unknown -> `Issue`

### Hierarchy and Links

Jira hierarchy differs from Azure DevOps:

- Subtasks use the issue `parent`.
- Stories/tasks under epics commonly use epic-specific fields or parent behavior that
  can vary by Jira product and configuration.
- Generic traceability should use issue links rather than inventing hierarchy.

Required behavior:

- Do not assume Azure hierarchy rules apply to Jira.
- Preserve Jira `parent` when returned by the API.
- For generated delivery tasks, prefer explicit links/metadata unless the Jira project
  configuration is known to support the target parent relation.
- Do not create or mutate Jira issue links without knowing the link type names available
  in that Jira instance.

### Sprint Reads

When reading Jira sprint data:

- Prefer Jira Software Agile sprint endpoints for board/sprint context.
- Use issue fields to resolve parent, status, assignee, labels, story points, and
  acceptance criteria when available.
- Treat custom fields as tenant-specific. Discover them rather than hard-coding IDs.

## Generated Task Rules

When a Story/User Story has no child tasks:

- Generate front/back tasks in memory for delivery planning.
- Add labels `auto:generated` and `scope:front` or `scope:back`.
- Do not mention product/tool branding in generated work item descriptions.
- Default branch name is `feature/{number}-{title}`.
- If materializing tasks remotely, validate hierarchy rules before linking.

When the source item is not a delivery parent type:

- Keep the generated task deliverable.
- Link it as `Related`.
- Make the description say the item is related, not parented.

## Delivery Routing Rules

For multi-repo delivery:

- Start from a clean `develop` or configured base branch in isolated worktrees.
- If the user's original checkout is dirty, do not switch branches there; create a
  separate worktree from the remote base branch.
- Route changes only to repos that need code changes. If API contracts already satisfy
  the task and targeted API tests pass, report the API as validated and do not open an
  empty API PR.
- Still run targeted validation on unaffected repos when the work item asked for
  front/back investigation.
- Keep branch-per-task naming; the default remains `feature/{number}-{title}` unless
  the workspace or user config overrides it.

## Evidence and Regression Rules

For every delivery:

- Record build, unit, and E2E evidence separately per repo.
- Capture screenshot and video evidence when the authenticated UI is reachable.
- If auth, tenant membership, SSO, or browser policy blocks visual validation, save an
  explicit blocker artifact and mention exactly which validation was blocked.
- Distinguish unrelated regression failures from affected-area failures. Full-suite
  failures outside the changed area must be reported, while targeted tests for the
  affected service/page still decide whether the fix is technically sound.
- Do not hide warnings from private package feeds, vulnerability feeds, or analyzers;
  classify them as existing/environmental only when supported by the run output.

## Error Handling Checklist

Before finishing any Jira/Azure sprint task:

- Confirm every generated/mutated work item has the expected link type.
- Check for Azure backlog hierarchy errors and normalize parent-child links when needed.
- Check that no generated description mentions internal tooling unless explicitly
  requested.
- Check that no task was assigned to a user unless explicitly requested or inherited.
- Check that required PR reviewers were applied when configured.
- Check that every PR links the originating work item when the provider supports it.
- Check that visual evidence exists or that an auth/environment blocker artifact was
  captured.
- Re-read changed work items through MCP/API when possible.

## Official References

- Azure DevOps work item link types:
  https://learn.microsoft.com/en-us/azure/devops/boards/queries/link-type-reference
- Azure DevOps work item REST API:
  https://learn.microsoft.com/en-us/rest/api/azure/devops/wit/work-items
- Azure DevOps WIQL:
  https://learn.microsoft.com/en-us/azure/devops/boards/queries/wiql-syntax
- Azure DevOps MCP server:
  https://github.com/microsoft/azure-devops-mcp
- Jira Cloud REST API v3:
  https://developer.atlassian.com/cloud/jira/platform/rest/v3/
- Jira Software Cloud REST API:
  https://developer.atlassian.com/cloud/jira/software/rest/
- Jira issue links:
  https://developer.atlassian.com/cloud/jira/platform/issue-linking-model/
