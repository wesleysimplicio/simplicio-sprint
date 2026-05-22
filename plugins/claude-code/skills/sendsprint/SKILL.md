---
name: sendsprint
description: Run the SendSprint 10-step sprint delivery flow against a Jira or Azure DevOps sprint. Triggers on "rode o sendsprint", "executar sprint", "entregar sprint", "run sendsprint", "execute sprint", "deliver sprint", "process Jira sprint", "process ADO sprint", "ejecutar sprint", "procesar sprint".
command: sendsprint
version: 0.3.0
platform: claude-code
---

# SendSprint — Claude Code skill

## Trigger

Invoke when user says (any language):

- pt-BR: "rode o sendsprint", "executar sprint", "entregar sprint", "processar sprint do Jira", "processar sprint do ADO"
- en: "run sendsprint", "execute sprint", "deliver sprint", "process Jira sprint", "process ADO sprint", "ship sprint"
- es: "ejecutar sprint", "procesar sprint", "entregar sprint"

Also auto-invoke when user mentions sprint id + Jira/ADO + repo path together (intent inference).

---

## Steps

1. **Confirm inputs**: sprint id (Jira) OR iteration path (ADO), workspace.yaml path OR single repo path, optional `--scope mine`.
2. **Read sprint** via `JiraOperator` or `AzureDevopsOperator` (transport `auto` resolves `mcp` → `api` → `playwright`).
3. **Import sprint specs** (`SprintImporter`): materializes each `SprintItem` as `.specs/sprints/sprint-<id>/<key>.task.md` (agentic-starter format) + `SPRINT.md` index. Idempotent — preserves user edits.
4. **Architecture mapping**: `ArchitectureMapper.map(repo)`. If score < 0.6 → `build_architecture(repo)` to seed baseline docs.
5. **Dev**: detect tech (`detect_tech`), create worktree (`WorktreeManager`), install + build (`DevAgent`).
6. **Lint**: `LintRunner` per detected stack (eslint / ruff / clippy / golangci-lint / phpcs / rubocop / dart analyze / dotnet format / checkstyle ...).
7. **Tests**: `TestRunner` runs unit + Playwright E2E with screenshot evidence captured to `evidence/`.
8. **Security review**: `SecurityReviewer` — flag-only scan (12 secret patterns, `.env` gitignore check, npm/pip/cargo audit). Halt if findings; do not auto-fix (ADR-005).
9. **Fix loop (Ralph)**: if lint/tests/security failed → dispatch parallel `everything-claude-code` reviewers/resolvers for the detected stack + re-run dev + lint + tests + security. Max 3 rounds (`MAX_FIX_LOOPS`). Each loop emits a `RALPH_STATUS` block in the summary.
10. **Commit + push**: `git add -A && git commit -m "..."` on worktree branch, then `git push -u origin <branch> --force-with-lease`.
11. **PR creation**: `PrCreator` → GitHub (`gh pr create`) or Azure DevOps REST. Body composed by `PrBodyBuilder` (sprint context + step report + evidence table + findings + DoD checklist).
12. **PR review**: `PrReviewer` runs diff static checks (TODO/FIXME, debug statements, merge conflict markers, long lines >200 chars).
13. **Delivered**: print `RunReport.summary` (with `RALPH_STATUS` block) + `RunReport.to_json()` to `report.json`.

---

## Multi-agent dispatch (Ralph loop)

On the fix loop (Step 9) and after every edit, dispatch specialized agents **in parallel** (single message, multiple `Agent` calls):

| Trigger | Agents (parallel) |
|---|---|
| Python edits | `everything-claude-code:python-reviewer` + `security-reviewer` |
| TS/JS edits | `everything-claude-code:typescript-reviewer` + `security-reviewer` |
| Go / Rust / Java / Kotlin / C# / C++ / Flutter | matching `everything-claude-code:<lang>-reviewer` + `security-reviewer` |
| SQL / migration | `everything-claude-code:database-reviewer` |
| Build failed | `everything-claude-code:<lang>-build-resolver` |
| Tests missing | `everything-claude-code:tdd-guide` |
| E2E web suite | `everything-claude-code:e2e-runner` |
| Sprint exploration | `Explore` (quick/medium/thorough) |

Exit gate (Ralph): all DoD checks green **AND** `EXIT_SIGNAL: true` in `RALPH_STATUS` block. Otherwise loop again until `MAX_FIX_LOOPS`.

---

## Stack

- Python ≥ 3.11
- Pydantic v2, Typer, Rich, httpx, playwright (sync), pyyaml
- Build: hatchling. Dev: pytest, pytest-asyncio, pytest-cov, ruff, mypy

---

## Comandos

### CLI
```bash
sendsprint version
sendsprint detect-tech ./repo
sendsprint check-architecture ./repo --build
sendsprint read-jira 42
sendsprint read-ado "Team\\Sprint 12"
sendsprint run jira 42 --workspace workspace.yaml --scope mine -o report.json
sendsprint run azuredevops "Sprint 12" --repo ./repo
```

### Python
```python
from sendsprint.flow import SprintFlow
from sendsprint.operators import JiraOperator
from sendsprint.workspace import load_workspace
from sendsprint.scope import build_scope

ws = load_workspace("workspace.yaml")
scope = build_scope(mode="mine", user_email="dev@example.com")
flow = SprintFlow(operator=JiraOperator(), workspace=ws, scope=scope)
result = flow.run(sprint_id=42)
print(result.run_report.summary)
print(result.to_json())
```

---

## Padrão de código

### Ler sprint isolado
```python
from sendsprint.operators import JiraOperator

op = JiraOperator(base_url="https://org.atlassian.net", transport="auto")
sprint = op.read_sprint(sprint_id=42)
for item in sprint.items:
    print(f"  [{item.type}] {item.key} - {item.title} ({item.status})")
```

### Workspace multi-repo (`workspace.yaml`)
```yaml
name: my-project
root_path: /home/dev/repos
new_projects_dir: Projetos/novos
pr_provider: github
repos:
  - name: backend-api
    path: backend-api
    role: api
    tech: dotnet
    default_branch: main
  - name: frontend-web
    path: frontend-web
    role: front
    tech: angular
```

### Variáveis de ambiente
| Var | Required for |
|---|---|
| `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | Jira API |
| `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT` | Azure DevOps API |
| `PLAYWRIGHT_CDP_URL` | Playwright fallback (default `http://127.0.0.1:9222`) |
| `LLM_PROVIDER`, `LLM_MODEL` | LLM step (optional) |

---

## Pegadinhas

- **Transport order is fixed**: `mcp` → `api` → `playwright`. `auto` picks first available.
- **Worktrees are real**: created via `git worktree add`. Cleanup happens in `WorktreeManager.__exit__`.
- **Fix loop max = 3**. Beyond that: report `failed=true` and stop.
- **Security is flag-only**: never auto-fix secrets. Always halt + report (ADR-005).
- **Step numbers must match flow**: SprintImporter=2, LintRunner=4, TestRunner=5, SecurityReviewer=6, PrCreator=9, PrReviewer=10. Changing flow order = update all `step=N` in agents.
- **PR creation needs push first**: `_push_branch()` runs before `pr_creator`. Skipping = PR fails (commit only local).
- **`--scope mine`**: matches account_id (Jira) OR email OR descriptor (ADO) OR display_name. Falsy = no filter applied.

---

## Definition of Done

- [ ] Sprint read (Step 1) → all expected items present in `Sprint.items`
- [ ] Sprint specs imported (Step 2) → `.specs/sprints/sprint-<id>/*.task.md` + `SPRINT.md` materialized
- [ ] Architecture mapped (Step 3) → score ≥ 0.6 OR baseline built
- [ ] Dev (Step 4) → install + build pass on every repo
- [ ] Lint (Step 5) → no errors, only warnings tolerated
- [ ] Tests (Step 6) → unit pass + E2E pass + screenshots in `evidence/`
- [ ] Security (Step 7) → zero secret findings AND `.env` gitignored
- [ ] Fix loop (Ralph) → if needed, ≤ 3 rounds; otherwise `failed=true`
- [ ] Commit (Step 10) → branch has at least one commit ahead of base
- [ ] PR (Step 11) → URL printed in `RunReport.prs[]`, body via `PrBodyBuilder` with evidence + DoD
- [ ] PR review (Step 12) → diff checks pass (no TODO/debug/merge-conflict in changed lines)
- [ ] `RunReport.failed == false` AND `result.to_json()` exported to `report.json`
- [ ] `RALPH_STATUS` block present in summary with `EXIT_SIGNAL: true`

---

## See also

- [AGENTS.md](../../AGENTS.md) — canonical project instructions
- [CLAUDE.md](../../CLAUDE.md) — Claude Code-specific extension
- [.specs/architecture/DESIGN.md](../../.specs/architecture/DESIGN.md) — architecture diagram
- [.specs/architecture/ADR-002-multi-transport.md](../../.specs/architecture/ADR-002-multi-transport.md) — transport fallback decision
- [.specs/architecture/ADR-005-flag-only-security.md](../../.specs/architecture/ADR-005-flag-only-security.md) — security flag-only decision
