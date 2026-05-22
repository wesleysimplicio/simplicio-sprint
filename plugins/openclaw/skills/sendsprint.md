---
name: sendsprint
description: SendSprint 10-step sprint delivery flow (Jira/ADO → PR). Openclaw skill manifest.
version: 0.2.2
platform: openclaw
---

# SendSprint — Openclaw skill

> Canonical project instructions: [/AGENTS.md](../../AGENTS.md). This file = Openclaw-specific manifest.

---

## Trigger

- pt-BR: "rode o sendsprint", "executar sprint", "entregar sprint", "processar sprint do Jira", "processar sprint do ADO"
- en: "run sendsprint", "execute sprint", "deliver sprint", "process Jira sprint", "process ADO sprint", "ship sprint"
- es: "ejecutar sprint", "procesar sprint", "entregar sprint"

---

## Steps

1. **Read sprint** → `JiraOperator(sprint_id)` or `AzureDevopsOperator(iteration_path)`. Transport `auto` resolves `mcp` → `api` → `playwright`. Supports `--scope mine`.
2. **Architecture mapping** → `ArchitectureMapper.map(repo)`. Auto-build baseline (`build_architecture(repo)`) if score < 0.6.
3. **Dev** → `detect_tech(repo)` + `WorktreeManager(repo, branch)` + `DevAgent.install_and_build()`.
4. **Lint** → `LintRunner.run()` per detected stack.
5. **Tests** → `TestRunner.run_unit() + run_e2e()` with screenshot evidence to `evidence/`.
6. **Security review** → `SecurityReviewer.scan()` (flag-only per ADR-005).
7. **Fix loop** → max 3 rounds re-running dev/lint/tests/security. Report which checks triggered retry.
8. **Commit + push** → `git add -A && git commit` then `git push -u origin <branch> --force-with-lease`.
9. **PR creation** → `PrCreator.create()` via GitHub `gh` CLI or Azure DevOps REST.
10. **PR review + Delivered** → `PrReviewer.review_diff()` + `RunReport.to_json()` to `report.json`.

---

## Stack

Python ≥ 3.11 · Pydantic v2 · Typer · Rich · httpx · playwright (sync) · pyyaml.

---

## Comandos

```bash
sendsprint version
sendsprint detect-tech ./repo
sendsprint check-architecture ./repo --build
sendsprint read-jira 42
sendsprint read-ado "Team\\Sprint 12"
sendsprint run jira 42 --workspace workspace.yaml --scope mine -o report.json
sendsprint run azuredevops "Sprint 12" --repo ./repo
```

---

## Padrão de código

```python
from sendsprint.flow import SprintFlow
from sendsprint.operators import JiraOperator
from sendsprint.workspace import load_workspace
from sendsprint.scope import build_scope

ws = load_workspace("workspace.yaml")
scope = build_scope(mode="mine", user_email="dev@example.com")
flow = SprintFlow(operator=JiraOperator(), workspace=ws, scope=scope)
result = flow.run(sprint_id=42)
print(result.to_json())
```

---

## Env

| Var | Required for |
|---|---|
| `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | Jira API |
| `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT` | Azure DevOps API |
| `PLAYWRIGHT_CDP_URL` | Playwright fallback (default `http://127.0.0.1:9222`) |
| `LLM_PROVIDER`, `LLM_MODEL`, provider key | LLM step (optional) |

---

## Pegadinhas

- Transport order = fixed (`mcp` → `api` → `playwright`).
- Worktrees real — auto-cleanup in `__exit__`.
- Fix loop max 3 → fail.
- Security flag-only (ADR-005).
- Step numbers must match flow order.
- Push must precede PR.

---

## Definition of Done

- [ ] All 10 steps reported
- [ ] `RunReport.failed == false`
- [ ] PR URL per repo with changes
- [ ] `report.json` exported
- [ ] Worktrees cleaned up
- [ ] Zero security findings
