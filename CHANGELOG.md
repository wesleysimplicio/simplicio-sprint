# Changelog

## 1.1.0

simplicio-mapper + MCP integration, plus the simplicio-prompt subagent fan-out.

- **MCP transport now works.** A host-injected seam
  (`operators/_mcp_bridge.py`) lets the agent feed MCP tool results to the Jira /
  Azure DevOps / GitHub operators, which reuse their REST→`Sprint` mappers. With
  no provider registered, `auto` transport falls back to REST as before.
- **simplicio-mapper adapter** (`mapper/`): renders a `Sprint` into the
  `.specs/sprints/sprint-XX/` format (`SPRINT.md`, `BACKLOG.md`, and one
  `NN-slug.task.md` per card with frontmatter + Acceptance Criteria, Test plan,
  Definition of Done). The flow writes each card's spec into the worktree so
  simplicio-cli has structured context.
- **simplicio-prompt fan-out** (`prompt/`): `PromptFanout` shells out to the
  Tuple-Space + Yool kernel (`--subagents 600`) to brainstorm edge cases and a
  plan per card, folding the result into the simplicio task. Opt-in via
  `sendsprint run --fanout`; degrades gracefully when the kernel is absent.
- **`sendsprint update`** (`bootstrap.py`): pulls the latest simplicio-cli (pip),
  simplicio-prompt kernel (git) and simplicio-mapper (git), and wires the
  previously-inert `verify_dependencies_on_start` / `update_*_on_start` profile
  flags so `run`/`watch` refresh tools at start (`--no-update` /
  `SENDSPRINT_NO_UPDATE=1` to skip). The fan-out auto-discovers the cached kernel.

## 1.0.0

Full rewrite around the simplicio-cli executor model.

- **SendSprint is the agent; simplicio-cli is the executor.** Each task is sent
  to `simplicio task` (one task → applied diff); SendSprint owns branching,
  evidence, commits, PRs and the review loop.
- Task sources: Jira, Azure DevOps, and **GitHub Issues** (new), transport mcp → api.
- Delivery layer: worktree isolation, commit + push with backoff, evidence
  (tests + Playwright screenshots), draft PR creation with embedded evidence.
- PR review loop: `revise_pr` feeds reviewer feedback back to simplicio and
  re-collects evidence.
- Unattended trigger: `sendsprint watch ... --once` (cron / GitHub Action /
  Claude Code on the web scheduled trigger), scoped with `--scope mine`.
- Removed the previous web/dashboard/API surfaces, the v2 cloud provider
  adapters, the yool/tuple/HAMT runtime, and the multi-IDE plugin packages —
  the repo is now just the agent flow.
