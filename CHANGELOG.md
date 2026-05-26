# Changelog

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
