# Sprint Autopilot Roadmap

SendSprint's next product step is to become a reliable sprint operator: it should read real backlog, plan the run, isolate execution, produce evidence, synchronize trackers, and leave humans with a clean review trail.

This roadmap turns the next improvements into implementation-ready workstreams. Each workstream should become a GitHub issue with acceptance criteria and validation steps before implementation starts.

## GitHub issue map

| Priority | Issue | Workstream |
| --- | --- | --- |
| P0 | [#27](https://github.com/wesleysimplicio/SendSprint/issues/27) | Real PyPI trusted publishing |
| P0 | [#28](https://github.com/wesleysimplicio/SendSprint/issues/28) | `sendsprint doctor` |
| P0 | [#29](https://github.com/wesleysimplicio/SendSprint/issues/29) | Full dry-run execution plan |
| P0 | [#30](https://github.com/wesleysimplicio/SendSprint/issues/30) | Per-task worktree isolation |
| P0 | [#31](https://github.com/wesleysimplicio/SendSprint/issues/31) | Evidence bundle |
| P1 | [#32](https://github.com/wesleysimplicio/SendSprint/issues/32) | GitHub Issues as a first-class tracker |
| P1 | [#33](https://github.com/wesleysimplicio/SendSprint/issues/33) | Configurable autonomy policy |
| P1 | [#34](https://github.com/wesleysimplicio/SendSprint/issues/34) | Native Ralph and Goal loop semantics |
| P1 | [#35](https://github.com/wesleysimplicio/SendSprint/issues/35) | Stack templates |
| P1 | [#36](https://github.com/wesleysimplicio/SendSprint/issues/36) | Local dashboard |
| P2 | [#37](https://github.com/wesleysimplicio/SendSprint/issues/37) | Sprint Autopilot demo |
| P2 | [#38](https://github.com/wesleysimplicio/SendSprint/issues/38) | Executive report |
| P2 | [#39](https://github.com/wesleysimplicio/SendSprint/issues/39) | Multi-agent control plane |

## North star

SendSprint should let an operator say "finish this sprint" and get a bounded, auditable delivery loop:

1. Inspect local and remote readiness.
2. Build a dry-run execution plan.
3. Run each task in isolated worktrees.
4. Use Ralph Wiggum (`/ralph-loop`) and Codex Goal (`/goal`) semantics as first-class execution loops.
5. Commit, push, open PRs, update issues, and capture validation evidence.
6. Produce human and executive reports at the end of the run.

## Priority 0

### Real PyPI trusted publishing

Current state: `0.13.0` publishes through `PYPI_API_TOKEN` after PyPI rejected the trusted publisher exchange.

Target state: GitHub releases publish to PyPI through trusted publishing without repository tokens.

Acceptance criteria:

- `.github/workflows/pypi-publish.yml` supports PyPI trusted publishing again.
- PyPI project configuration is documented with exact repository, workflow, environment, and tag claims.
- A release dry-run or test package path proves the claims match before changing the production release path.

### `sendsprint doctor`

Current state: readiness checks are spread across taskflow, auth commands, local tests, and per-feature validation.

Target state: one command reports whether the machine and repository are ready for an autonomous sprint run.

Acceptance criteria:

- Checks GitHub auth, tracker auth, clean/dirty git state, remote sync, Python package health, Playwright availability, LLM provider config, budget config, and workspace files.
- Returns structured JSON plus a human console summary.
- Fails with actionable remediation messages.

### Full dry-run execution plan

Current state: dry-run exists, but it should become the operator's safety preview before autonomous execution.

Target state: dry-run shows what SendSprint will read, change, spend, validate, and publish.

Acceptance criteria:

- Prints target issues, repositories, branches, worktrees, expected PR targets, validation commands, LLM provider/model, token/cost budget, and deploy callbacks.
- Requires explicit opt-in before code generation, push, release, or deploy callbacks.
- Writes the plan as an artifact that can be attached to a PR or issue comment.

### Per-task worktree isolation

Current state: SendSprint has worktree concepts, but autonomous multi-issue execution needs stricter isolation.

Target state: every task runs in its own named worktree with predictable cleanup and resume behavior.

Acceptance criteria:

- Creates one worktree per issue/task using a deterministic naming scheme.
- Detects existing worktrees and resumes safely.
- Prevents unrelated local changes from being modified.
- Captures branch, base commit, and cleanup status in the run report.

### Evidence bundle

Current state: reports and taskflow artifacts exist, but evidence is not yet packaged as a single run artifact.

Target state: every autonomous run can produce a portable evidence bundle.

Acceptance criteria:

- Bundle includes run report, command logs, test output, screenshots/traces when present, PR URLs, issue update summaries, diff metadata, and changelog/release notes.
- Bundle path is printed at the end of each run.
- Bundle schema is stable enough for dashboard and executive report consumers.

## Priority 1

### GitHub Issues as a first-class tracker

Current state: SendSprint is strong on Jira and Azure DevOps, while GitHub Issues usage still depends heavily on `gh` workflows around the tool.

Target state: GitHub Issues is a native tracker alongside Jira and Azure DevOps.

Acceptance criteria:

- Reads open issues with labels, assignees, milestones, and linked PRs.
- Scores and prioritizes issues without duplicating already-solved work.
- Comments with evidence, closes completed issues, and records blockers.
- Supports repository batches and per-repository rate limiting.

### Configurable autonomy policy

Current state: some capabilities are controlled through flags, but the overall autonomy level is not a single contract.

Target state: operators can choose exactly how far SendSprint may go.

Acceptance criteria:

- Supports levels such as `observe`, `plan`, `execute`, `commit`, `push`, `pr`, `release`, and `deploy-callback`.
- Enforces the policy centrally before side-effecting operations.
- Records the active policy in plans, reports, and issue comments.

### Native Ralph and Goal loop semantics

Current state: docs reference Claude Code `/ralph-loop` and Codex `/goal`, but SendSprint does not model them as a native execution contract.

Target state: SendSprint can run and report loop attempts with explicit gates and exit signals.

Acceptance criteria:

- Models objective, acceptance criteria, max attempts, validation gates, and exit signal.
- Records each attempt, failing command, applied fix, and final status.
- Supports Claude Code Ralph Wiggum naming and Codex Goal naming in user-facing docs.

### Stack templates

Current state: tech detection exists, but projects still need stronger default validation recipes by stack.

Target state: common stacks ship with tested templates.

Acceptance criteria:

- Adds templates for Angular, React, Vue.js, Node.js, Python, PHP, .NET, mobile, and monorepo projects.
- Frontend templates cover framework-specific install, lint, typecheck, build, and Playwright expectations.
- Node.js templates cover API/library projects separately from browser framework projects.
- Each template defines install, lint, unit, E2E, security, changelog, and release expectations.
- `sendsprint doctor` and dry-run explain which template matched and why.

### Local dashboard

Current state: SendSprint is mostly CLI/API oriented.

Target state: operators can watch sprint execution without parsing terminal output.

Acceptance criteria:

- Shows sprint items, repos, branches, agents, PRs, validations, costs, and blockers.
- Reads from the run report/evidence bundle instead of inventing a separate state model.
- Works locally without requiring a hosted service.

## Priority 2

### Sprint Autopilot demo

Target state: a repeatable demo shows SendSprint reading issues, creating isolated branches, validating changes, opening PRs, updating issues, and producing release notes.

Acceptance criteria:

- Demo repo has realistic issues and fixtures.
- Demo can run in dry-run mode without credentials.
- Demo docs include screenshots or terminal transcript plus expected artifacts.

### Executive report

Target state: each run can generate a concise manager-facing report.

Acceptance criteria:

- Summarizes delivered items, PRs, tests, risk, blockers, cost, and next actions.
- Links to evidence bundle and issue/PR updates.
- Supports Markdown output for GitHub comments or Obsidian notes.

### Multi-agent control plane

Target state: SendSprint can coordinate multiple agents without hiding risk from the operator.

Acceptance criteria:

- Shows active workers, assigned tasks, current status, retries, and blockers.
- Enforces repository and issue ownership so agents do not overwrite each other.
- Integrates with autonomy policy, worktree isolation, and evidence bundle.

## Sequencing

Recommended build order:

1. Trusted publishing and `sendsprint doctor`.
2. Dry-run plan, autonomy policy, and worktree isolation.
3. Evidence bundle and GitHub Issues tracker.
4. Ralph/Goal loop, templates, and dashboard.
5. Demo, executive report, and multi-agent control plane.
