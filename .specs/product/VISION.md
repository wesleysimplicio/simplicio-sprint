# SendSprint — Vision

> One-page product north star. Why this exists, who uses it, what it solves.

---

## Why

Engineering teams running Scrum/Kanban with **Jira** or **Azure DevOps** lose 20–40% of sprint time on **manual delivery overhead**:

- Pulling sprint items, deciding what's "mine"
- Switching between repos, branches, worktrees
- Running `npm install` / `pip install` / `dotnet restore` per stack
- Running lint, unit tests, E2E tests, security scans manually
- Crafting commit messages, opening PRs, writing PR descriptions
- Re-running everything when something breaks (the "fix loop")

Each step is mechanical and high-context. Each is also where **quality regressions hide** when humans rush.

**SendSprint replaces that loop with a deterministic pipeline that runs end-to-end from a single command, while keeping risky actions behind explicit policy and evidence gates.**

---

## What

A Python multi-agent CLI that, given a sprint id (Jira) or iteration path (ADO), produces:

1. **Read sprint** → structured `Sprint` object with all items
2. **Architecture mapping** → baseline doc score per repo
3. **Dev** (per repo): detect stack, create worktree, install + build
4. **Lint** per stack (eslint, ruff, clippy, golangci-lint, phpcs, …)
5. **Tests** unit + Playwright E2E with screenshot evidence
6. **Security review** (flag-only — never auto-fix)
7. **Fix loop** — max 3 rounds, re-run dev/lint/tests/security
8. **Optional code generation** — gated by provider, model, token, and cost budget
9. **Commit + push** with remote-safety checks
10. **PR creation** via `gh`, Jira/Azure DevOps context, or tracker-native callbacks
11. **Optional deploy callback** — idempotent status synchronization after PR handoff
12. **PR review + Delivered** — diff static checks + `report.json`

Output: `RunReport` (pydantic v2) with steps, durations, errors, PR URLs.

---

## Who

**Primary users:**
- **Engineering ICs** running their own sprint (`--scope mine`)
- **Engineering managers** auditing sprint delivery (full scope)
- **Platform / DevEx teams** adopting it as a CI primitive

**Secondary users:**
- **AI agents** (Codex, Claude Code, Hermes, Openclaw, Copilot) invoking SendSprint as a skill
- **CI/CD pipelines** wrapping `sendsprint run` to auto-deliver bot-assigned tickets

---

## Problem solved

| Pain | SendSprint answer |
|------|-------------------|
| Manual sprint pull → forget items | Operator reads sprint atomically via API/MCP/Playwright fallback |
| Stack-specific install commands | `detect_tech` + `DevAgent.install_and_build` handle 19 stacks |
| Inconsistent quality gates | Same lint + test + security battery per repo, every run |
| No audit trail per sprint | `RunReport.to_json()` = full evidence pack |
| PRs without context | `PrCreator` writes structured PR body from sprint items |
| Security findings shipped accidentally | Flag-only halt (ADR-005), never auto-fix |
| Multi-repo sprints | `workspace.yaml` + `WorktreeManager` for parallel-safe branches |
| Agent cost risk | Opt-in LLM code generation with provider, model, token, and budget controls |
| Post-PR tracker drift | Deploy/status callbacks keep Jira and Azure DevOps synchronized |

---

## Non-goals

- **Not a planning tool.** SendSprint reads sprints, doesn't plan them. Use Jira/ADO for that.
- **Not an uncontrolled code generator.** LLM code generation is opt-in, budgeted, and must pass validation gates.
- **Not a security scanner.** Step 6 flags known patterns (12 secret regexes, dep audits). Not a replacement for Snyk/Semgrep/Trivy.
- **Not a deploy orchestrator.** Merge and deployment remain human- or CI-controlled; SendSprint can only call configured status/deploy callbacks.

---

## Success metrics

- **Time to PR**: < 8 min for single-repo sprint with ≤ 5 items
- **Fix loop convergence**: ≥ 80% of runs converge in ≤ 1 round
- **False-positive rate** (security flags): < 5%
- **Adoption**: skill manifest auto-loaded by ≥ 4 AI platforms (Codex / Claude / Hermes / Openclaw / Copilot)
- **Operator trust**: every autonomous run produces a dry-run plan plus an evidence bundle suitable for human review

---

## See also

- [DOMAIN.md](DOMAIN.md) — entities and relationships
- [/AGENTS.md](../../AGENTS.md) — canonical project instructions
- [/.specs/architecture/DESIGN.md](../architecture/DESIGN.md) — system design
- [/docs/roadmap/sprint-autopilot-roadmap.md](../../docs/roadmap/sprint-autopilot-roadmap.md) — next operator roadmap
