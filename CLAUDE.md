# CLAUDE.md

Claude Code-specific instructions for SendSprint. **Read [AGENTS.md](./AGENTS.md) FIRST** — that's the canonical source. This file only adds Claude-specific behavior.

---

## Source of truth

All stack, layout, commands, patterns, gotchas, commit conventions, and Definition of Done are in [AGENTS.md](./AGENTS.md). Do not duplicate that content here.

---

## Claude Code-specific behavior

### Skill invocation

When user says any of:
- pt-BR: "rode o sendsprint", "executar sprint", "entregar sprint", "processar sprint do Jira", "processar sprint do ADO"
- en: "run sendsprint", "execute sprint", "deliver sprint", "process Jira sprint", "process ADO sprint"
- es: "ejecutar sprint", "procesar sprint"

→ Invoke the SendSprint flow per `skills/claude/SKILL.md`.

### Subagent delegation

Use specialized subagents in parallel where possible:

| Trigger | Agent |
|---|---|
| Adding new tech stack support | `Explore` (find existing patterns) + `python-reviewer` |
| New agent class | `Plan` + `python-reviewer` after edit |
| Bug in operator | `everything-claude-code:python-reviewer` |
| Test missing | `everything-claude-code:tdd-guide` |
| Build error | `everything-claude-code:build-error-resolver` |
| Security finding in flow | `security-reviewer` (NEVER auto-fix — flag only per ADR-005) |

### Hook integration

Pre-commit hook at `.claude/hooks/pre-commit.sh` blocks commit if `pytest tests/ -v` fails.
Post-edit hook at `.claude/hooks/post-edit.sh` runs `ruff format` on `.py` edits.

### Tool preferences

- **Edit > Write** for existing files
- **Read full file** before edit (mandatory)
- **Bash for tests/lint/git**, never for file content (use Read/Edit/Write)
- **Parallel tool calls** for independent reads (e.g., reading 5 skill manifests at once)

### MCP servers (when available)

- `atlassian` MCP → use for Jira sprint reading instead of REST fallback when configured
- `playwright-global` MCP → use for E2E Playwright fallback when CDP browser unreachable
- `github` MCP → use for PR creation when `gh` CLI absent

Order matches transport priority in AGENTS.md §4: `mcp` → `api` → `playwright`.

<!-- rtk-cli:start -->
## Shell token-smart (RTK CLI, optional)

If `rtk` (https://github.com/rtk-ai/rtk) is installed, prefer `rtk read|grep|find|git|pytest` for exploration and verbose validation. Falls back gracefully when absent. Full rules in AGENTS.md and `.skills/rtk-cli/SKILL.md`.
<!-- rtk-cli:end -->

<!-- yool-tuple-hamt:start -->
## yool / tuple / HAMT (capability addressing)

Vendored spec: https://github.com/wesleysimplicio/yool-tuple-hamt (v0.2).

Agent capabilities exposed as **yools** indexed in a HAMT (`.catalog/hamt.json`).

```bash
sendsprint catalog build
sendsprint catalog list
sendsprint catalog show agent.codex.plan
sendsprint catalog find hermes
```

Source of truth: `sendsprint/agent_registry.py`. Every catalog entry carries the MANDATORY guardrails from spec §11 (Victor's note):

- `cpu_quota_pct` (default 60) — caps CPU via `os.nice`/cgroups/`taskpolicy`. Stops one yool frying the host.
- `disk_quota_mb` (default 100) — kills writes past the cap, recorded as `status="disk_exceeded"`.
- `timeout_s` (default 300) — wall-clock kill.

Disk GC three-tier: hot (≤30d, keep all) / warm (≤365d, purge artifact body) / cold (>365d, purge artifact body). Receipts NEVER deleted — they're the Merkle chain. `DiskPressure` raises before free space < 1000 MB.
<!-- yool-tuple-hamt:end -->

<!-- codex-long-running-agent-overlay:start -->
## Universal Long-Running Agent Overlay

This section complements the repository-specific guidance already in this file. If anything here conflicts with the repo-specific rules above, the repo-specific rules win.

- `PRD.md` is the task source of truth for long-running sessions.
- `PROGRESS.md` is the persistent checkpoint log.
- `GOAL_RESULT.md` is the final execution report.
- Before coding, read this file, `PRD.md`, `PROGRESS.md` when it exists, `README.md`, project manifests, tests, and the relevant source folders.
- Work in small checkpoints, run the smallest relevant validation after each meaningful change, update `PROGRESS.md`, and continue until complete or genuinely blocked.
- Stop only when the requested work is complete, validation is documented, and `GOAL_RESULT.md` reflects the outcome.
- Do not rewrite unrelated architecture, fake successful validation, expose secrets, or push without explicit operator instruction for the active session.
<!-- codex-long-running-agent-overlay:end -->

Use o repo canonico https://github.com/wesleysimplicio/yool-tuple-hamt.
Leia antes de editar: YOOL_TUPLE_HAMT.md, kernel/yool_tuple_kernel.py,
guardrails/cpu_throttle.py, guardrails/disk_gc.py, examples/python/receipts.py
e scripts/build_hamt.py.

Ao receber "Implement X": decomponha em grafo Hilbert-indexed, crie tuple raiz,
use batch_spawn(depth, branching, compression_threshold) para 1.000.000+
subagents sem enumerar, execute work ativo com spawn_agent, roteie por out/in/rd,
route_packet e scan_index, aplique hookwall, compress_token e prune_idle, e use
LaneWorkerPool respeitando YOOL_TUPLE_* env vars.

Execute:
python kernel/yool_tuple_kernel.py

Responda SEMPRE exatamente neste formato (sem variações):
[Tuple Space Snapshot]
[Active Agents/Subagents]
[Total Agents/Subagents]
[Próximo Yool a executar]
[Resultado parcial]
