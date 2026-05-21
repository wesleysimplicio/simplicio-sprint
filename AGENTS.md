# AGENTS.md — SendSprint

Master instruction file for AI agents working in this repo. Read this FIRST. All other agent files (CLAUDE.md, copilot-instructions.md, skills/) reference this as source of truth.

---

## 1. What this project is

**SendSprint** = multi-agent skill that automates **end-to-end sprint delivery** in a 10-step flow:

1. Read sprint (Jira / Azure DevOps)
2. Architecture mapping (inspect + auto-generate baseline if missing)
3. Dev: tech detection, worktree, install, build
4. Lint (19 stacks)
5. Tests (unit + Playwright E2E with screenshot evidence)
6. Security review (flag-only: secrets, env, npm/pip/cargo audit)
7. Fix loop (max 3 rounds, re-runs lint+tests+security)
8. Commit (worktree branch)
9. Create PR (GitHub `gh` CLI / Azure DevOps REST)
10. PR review (diff static analysis) + Delivered

Transport priority: `mcp` → `api` → `playwright`.

Multi-repo: `workspace.yaml` defines repos with role + tech.

Filtering: `--scope mine` filters items to current user only.

Jira/Azure DevOps operating rules live in
`.specs/integrations/JIRA_AZUREDEVOPS_CORE.md`. Read it before changing
operators, work-item creation, task planning, hierarchy links, sprint reads, or
PR/ticket linking behavior. Use MCP for live tenant state; use the local guide
for stable rules and known error prevention.

---

## 2. Stack

- **Python ≥ 3.11** (3.12 supported in CI matrix)
- **Pydantic v2** for all models
- **Typer + Rich** for CLI
- **httpx** for REST calls
- **playwright** (sync) for browser fallback
- **pyyaml** for workspace config
- **pytest + pytest-asyncio + pytest-cov** for tests
- **ruff + mypy** for lint/type-check
- Build: **hatchling**

---

## 3. Layout

```
sendsprint/
├── operators/         JiraOperator, AzureDevopsOperator (mcp|api|playwright)
├── models/            Sprint, SprintItem, StepReport, RunReport (Pydantic v2)
├── agents/
│   ├── worktree.py    Git worktree isolation
│   ├── dev.py         Install + build (16 package managers)
│   ├── lint_runner.py 19 linters
│   ├── test_runner.py Unit + E2E
│   ├── security_reviewer.py  12 secret patterns + npm/pip/cargo audit
│   ├── pr_creator.py  GitHub gh / Azure DevOps REST
│   └── pr_reviewer.py Diff static checks
├── architecture/
│   ├── mapper.py      Weighted scoring
│   └── builder.py     Auto-generate baseline docs
├── tech/detector.py   25+ tech filesystem markers
├── workspace/loader.py YAML/JSON multi-repo loader
├── scope.py           --scope mine filter
├── flow/sprint_flow.py 10-step orchestrator
├── llm/               Provider-agnostic LLM client
├── credentials.py     OS keyring (Keychain/Secret Service/Credential Manager)
├── profile.py         ~/.config/sendsprint/profile.yaml (chmod 600)
├── scaffolder.py      Auto-discovery + LLM-fill `.specs/` on first run
└── cli.py             Typer CLI entrypoint (commands: version, init, login, logout, sprint, run, …)

skills/                Per-platform manifests
  ├── claude/          SKILL.md (full reference)
  ├── codex/           AGENTS.md
  ├── hermes/          hermes.md
  ├── openclaw/        openclaw.md
  ├── copilot/         copilot-instructions.md
  ├── cursor/          sendsprint.mdc (Cursor rule, alwaysApply)
  ├── windsurf/        sendsprint.md (Windsurf rule, trigger:always_on)
  ├── kiro/            sendsprint.md (.kiro/steering/ placement)
  ├── zed/             sendsprint.md (.rules placement)
  ├── cline/           .clinerules (VSCode Cline)
  ├── continue/        config.json (Continue customCommands + rules)
  ├── aider/           CONVENTIONS.md (aider --read)
  └── cody/            sendsprint.md (Sourcegraph Cody)
.specs/                Product/architecture/workflow specs + ADRs
  └── integrations/    Jira/Azure DevOps core guide and vendor source links
.claude/hooks/         Pre/post-edit hooks
templates/             Task + ADR templates
tests/                 pytest suite (103 tests)
```

---

## 4. Commands

```bash
# Install
pip install -e ".[dev]"
playwright install chromium

# Test (run before any commit)
pytest tests/ -v
pytest tests/ --cov=sendsprint --cov-report=term-missing

# Lint + type check
ruff check sendsprint/
ruff format sendsprint/
mypy sendsprint/

# CLI — chat-trigger UX (single command for the user)
sendsprint sprint                                # zero-arg: uses cached profile + keyring
sendsprint init                                  # auto-discover stack, LLM-fill .specs/
sendsprint login jira                            # store creds in OS keyring (one-time)
sendsprint login azuredevops                     # idem for ADO PAT
sendsprint logout jira                           # delete keyring entry

# CLI — granular (operators)
sendsprint version
sendsprint detect-tech ./repo
sendsprint check-architecture ./repo --build
sendsprint read-jira 42
sendsprint read-ado "Team\\Sprint 12"
sendsprint run jira 42 --workspace workspace.yaml --scope mine -o report.json
sendsprint run azuredevops "Sprint 12" --repo ./repo
```

### Chat-trigger UX

The skill is wired in **8 IDE manifests** under `skills/` so the user types one
phrase in the assistant chat and the agent runs `sendsprint sprint`. Recognised
trigger phrases (any of):

- pt-BR: `rode o sendsprint`, `executar sprint`, `Faça todas as minhas tarefas da sprint`, `entregar sprint`
- en: `run sendsprint`, `ship my sprint`, `deliver my sprint`, `process my Jira sprint`, `process my ADO sprint`
- es: `ejecutar sprint`, `procesar sprint`
- slash: `/sendsprint`

Credentials prompted **only on first run**, then persisted to OS keyring
(Keychain / Secret Service / Credential Manager). Non-secret prefs (org, project,
default sprint, scope) live in `~/.config/sendsprint/profile.yaml` (chmod 600).

| IDE | Manifest path inside repo | Placement in user's repo |
|---|---|---|
| Claude Code | `skills/claude/SKILL.md` | `~/.claude/skills/sendsprint/SKILL.md` |
| GitHub Copilot | `skills/copilot/copilot-instructions.md` | `.github/copilot-instructions.md` |
| Codex CLI | `skills/codex/AGENTS.md` | `AGENTS.md` |
| Cursor | `skills/cursor/sendsprint.mdc` | `.cursor/rules/sendsprint.mdc` |
| Windsurf | `skills/windsurf/sendsprint.md` | `.windsurf/rules/sendsprint.md` |
| Kiro | `skills/kiro/sendsprint.md` | `.kiro/steering/sendsprint.md` |
| Zed | `skills/zed/sendsprint.md` | `.rules` (or appended) |
| Cline (VSCode) | `skills/cline/.clinerules` | `.clinerules` |
| Continue | `skills/continue/config.json` | `~/.continue/config.json` or `.continue/config.json` |
| Aider | `skills/aider/CONVENTIONS.md` | `CONVENTIONS.md` (loaded with `aider --read`) |
| Sourcegraph Cody | `skills/cody/sendsprint.md` | `.sourcegraph/cody/instructions.md` or `.cody/commands/*.json` |
| Hermes | `skills/hermes/hermes.md` | per-tool location |
| Openclaw | `skills/openclaw/openclaw.md` | per-tool location |

---

## 5. Code patterns (HARD RULES)

### Operator
```python
from sendsprint.operators import JiraOperator
op = JiraOperator(base_url="https://org.atlassian.net", transport="auto")
sprint = op.read_sprint(sprint_id=42)
```

### Flow
```python
from sendsprint.flow import SprintFlow
from sendsprint.workspace import load_workspace
from sendsprint.scope import build_scope

ws = load_workspace("workspace.yaml")
scope = build_scope(mode="mine", user_email="dev@example.com")
flow = SprintFlow(operator=op, workspace=ws, scope=scope)
result = flow.run(sprint_id=42)
print(result.run_report.summary)
print(result.to_json())
```

### Adding a new tech to detector
1. Add markers tuple to `KNOWN_TECHS` in `sendsprint/tech/detector.py`
2. Categorize in `FRONT_TECHS` / `BACK_TECHS` / `MOBILE_TECHS` / `INFRA_TECHS`
3. Add lint command to `LINT_COMMANDS` in `sendsprint/agents/lint_runner.py`
4. Add install/build command in `sendsprint/agents/dev.py`
5. Add unit/E2E test command in `sendsprint/agents/test_runner.py`
6. Write tests in `tests/test_tech_detector.py` and `tests/test_agents.py`

### Adding a new agent
1. Create `sendsprint/agents/<name>.py` with class accepting `RepoConfig` + `Path`
2. Method must return `StepReport` (`step`, `name`, `status`, `details`)
3. Wire into `SprintFlow` step ordering (`flow/sprint_flow.py`)
4. Update `MAX_FIX_LOOPS` integration if step participates in fix loop
5. Add to all 5 skill manifests step list

### Mock fallback (when ext tools missing)
```python
try:
    result = subprocess.run([cmd], ...)
except FileNotFoundError:
    return StepReport(step=N, name="...", status="skipped", details={"reason": "tool not installed"})
```

---

## 6. Test rules

- **Every** new agent/operator/model gets a test in `tests/`
- Use `monkeypatch` to mock `httpx.Client.request` and `subprocess.run`
- Test both happy path AND fallback path
- Run full suite (`pytest tests/ -v`) before commit — must be 100% green
- Coverage target: ≥ 85% (currently 103 tests)

---

## 7. Gotchas

- **Transport fallback order is fixed**: `mcp` → `api` → `playwright`. Don't reorder. `auto` resolves first available.
- **Worktree side effects**: `WorktreeManager` creates real git worktrees. Tests must clean up (`tempfile.TemporaryDirectory()`).
- **Fix loop max 3**: hard cap. Beyond that = give up + report failed.
- **Security reviewer is flag-only**: NEVER auto-fix secrets. Always report + halt.
- **Jira/Azure DevOps docs**: read `.specs/integrations/JIRA_AZUREDEVOPS_CORE.md` before changing sprint/work-item behavior.
- **Azure hierarchy safety**: invalid parent-child links like `Issue -> Task` must be normalized to `Related`.
- **Step numbers must match flow order**: changing step order = update step numbers in ALL agent files (`step=N` in StepReport).
- **PR creation requires push first**: `_push_branch()` must run before `pr_creator`. Otherwise commit lives only locally.
- **Workspace `new_projects_dir`**: relative to `root_path`. Don't make absolute.
- **`--scope mine` matches**: account_id (Jira) OR email OR descriptor (ADO) OR display_name. Falsy = no filter.

---

## 8. Commit conventions

- **Language: English, imperative mood** (`add`, `fix`, `refactor`)
- Format: `<type>: <subject>` then blank line then body
- Types: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`
- Body explains **why**, not what (diff shows what)
- Reference ADR if architectural: `Refs ADR-003`
- NEVER commit secrets, `.env`, `uv.lock` (see `.gitignore`)

Example:
```
feat: add cargo-audit to security reviewer

Step 6 now checks Rust dependency vulns via `cargo audit --json`.
Caps at 20 findings per repo to avoid report bloat.

Refs ADR-005
```

---

## 9. Versioning

- **SemVer**. Bump in `sendsprint/__init__.py` + `pyproject.toml` + `README.md` status line + `CHANGELOG.md` entry.
- Patch: bug fix only. Minor: new feature, backwards-compatible. Major: breaking API change.
- All version files must match exactly.

---

## 10. References

- **Vision**: `.specs/product/VISION.md`
- **Domain model**: `.specs/product/DOMAIN.md`
- **Architecture diagram**: `.specs/architecture/DESIGN.md`
- **How-to extend**: `.specs/architecture/PATTERNS.md`
- **ADRs**: `.specs/architecture/ADR-*.md`
- **Workflow**: `.specs/workflow/WORKFLOW.md`
- **Contributing**: `.specs/workflow/CONTRIBUTING.md`
- **Jira/Azure DevOps core guide**: `.specs/integrations/JIRA_AZUREDEVOPS_CORE.md`
- **Per-platform skills**: `skills/{claude,codex,hermes,openclaw,copilot,cursor,windsurf,kiro,zed,cline,continue,aider,cody}/`
- **Templates**: `templates/`

---

## 11. Definition of Done (any change)

- [ ] Code written following patterns above
- [ ] Tests written and pass (`pytest tests/ -v`)
- [ ] Lint clean (`ruff check sendsprint/`)
- [ ] Format applied (`ruff format sendsprint/`)
- [ ] Type-check clean (`mypy sendsprint/`) — best effort
- [ ] Version bumped in 4 places (`__init__.py`, `pyproject.toml`, `README.md`, `CHANGELOG.md`)
- [ ] Commit message in English, imperative
- [ ] Pushed to `origin/main` (or feature branch + PR)
- [ ] If new pattern → ADR added in `.specs/architecture/`

<!-- rtk-cli:start -->
## Shell token-smart (RTK CLI, optional)

If `rtk` (https://github.com/rtk-ai/rtk) is on PATH, prefer it for shell-heavy and exploratory work — compact output, ~40-70% fewer tokens, same signal.

```bash
rtk read AGENTS.md
rtk grep "pattern" sendsprint/
rtk find "*.py" .
rtk git status
rtk git diff
rtk git log -n 10
rtk npm test            # or rtk pytest
```

Rules:
- Use `rtk read|grep|find|git ...` as first choice for textual inspection.
- Use `rtk <command>` on verbose validators where a summary is enough to decide next step.
- **Do not** route through RTK: interactive prompts, streaming, or anything where raw output is the evidence (`curl`, `playwright`, `gh pr view --web`, long verbatim logs).
- If `rtk` is not installed, fall back to plain commands — no hard dependency.

See `.skills/rtk-cli/SKILL.md` for the full skill manifest.
<!-- rtk-cli:end -->

<!-- yool-tuple-hamt:start -->
## yool / tuple / HAMT (capability addressing)

Vendored spec: https://github.com/wesleysimplicio/yool-tuple-hamt (v0.2).

Agent capabilities in this repo are exposed as **yools** — atomic callable opcodes — and indexed in a HAMT (`.catalog/hamt.json`). Build/query via:

```bash
sendsprint catalog build             # write .catalog/hamt.json
sendsprint catalog list               # list every yool
sendsprint catalog show <yool_id>     # one yool with guardrails
sendsprint catalog find <substr>      # search by substring
```

Source of truth for yools is `sendsprint/agent_registry.py`. Adding a new capability there auto-appears in the catalog on next `build`.

### Guardrails (MANDATORY — spec §11)

Every catalog entry **must** carry:

- `cpu_quota_pct` (default 60) — caps CPU per yool. Spec §11.1 maps to `os.nice` via `(100 - quota) / 5.2` on POSIX; cgroups on Linux; `taskpolicy` on macOS. Prevents one yool from frying the host.
- `disk_quota_mb` (default 100) — caps the artifact bytes a single execution may write before being killed and recorded as `status="disk_exceeded"`.
- `timeout_s` (default 300) — wall-clock kill.

### Disk GC (MANDATORY — spec §11.2)

Receipts are immutable (cache-key Merkle chain) and **never deleted**. Artifact **bodies** rotate through three tiers:

| Tier | Age      | Receipt | Artifact body |
|------|----------|---------|---------------|
| hot  | ≤ 30d    | keep    | keep          |
| warm | ≤ 365d   | keep    | purge         |
| cold | > 365d   | keep    | purge         |

`DiskPressure` circuit breaker raises before free space falls below `free_mb_floor=1000`. Reference implementation: `guardrails/disk_gc.py` in the spec repo.

> Victor (Dev Hermes): *"precisa de guardrail pra nao fritar o processador. voce precisa de garbage collector tmb pra nao enxer 100% do disco."* — both are non-optional in this stack.
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
