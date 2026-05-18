# Domain Map

SendSprint's domain is sprint delivery automation with explicit safety gates.

## Core Concepts

| Concept | Meaning | Source files |
|---|---|---|
| Sprint | A backlog iteration read from Jira or Azure DevOps | `sendsprint/models/sprint.py` |
| Sprint item | Story/task/bug/feature/issue to route into delivery | `sendsprint/models/sprint.py` |
| Workspace | Multi-repo delivery configuration | `sendsprint/models/workspace.py` |
| Repo config | Repo path, role, branch target, reviewers, custom commands | `sendsprint/models/workspace.py` |
| Scope | Which sprint items are allowed into the run | `sendsprint/scope.py` |
| Delivery plan | Dry-run plan of item/repo/branch/target/confidence | `sendsprint/planning.py` |
| Run state | Resumable progress for a run id | `sendsprint/run_state.py` |
| Run report | Auditable result with steps, evidence, PRs, failures | `sendsprint/models/reports.py` |
| Evidence | Test/log/screenshot artifacts attached to reports and PRs | `sendsprint/models/reports.py` |

## Invariants

- Dry-run must be read-only.
- Security findings are reported, not auto-fixed.
- Push, PR, release, and deploy are side effects and must be policy-gated.
- Worktree isolation protects unrelated local changes.
- Reports are the shared contract for CLI, API, dashboard, PR body, GitHub issue
  comments, executive reports, and release notes.

## Tracker Sources

- Jira and Azure DevOps are implemented operators.
- GitHub Issues is a roadmap target and should share the same planning/report
  contracts instead of becoming a separate delivery path.

## Autonomy Levels

The roadmap asks for explicit levels: `observe`, `plan`, `execute`, `commit`,
`push`, `pr`, `release`, and `deploy-callback`. New code should centralize these
checks so CLI flags, dry-run output, API runs, and issue updates agree.
