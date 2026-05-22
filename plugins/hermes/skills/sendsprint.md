---
name: sendsprint
description: SendSprint 10-step sprint delivery flow (Jira/ADO → PR). Hermes-compatible skill manifest.
version: 0.2.2
platform: hermes
---

# SendSprint — Hermes agent skill

> Canonical project instructions: [/AGENTS.md](../../AGENTS.md). This file = Hermes-specific manifest.

---

## Trigger

- pt-BR: "rode o sendsprint", "executar sprint", "entregar sprint", "processar sprint do Jira", "processar sprint do ADO"
- en: "run sendsprint", "execute sprint", "deliver sprint", "process Jira sprint", "process ADO sprint", "ship sprint"
- es: "ejecutar sprint", "procesar sprint", "entregar sprint"

---

## Steps

| Step | Name | Module | Notes |
|------|------|--------|-------|
| 1 | Read sprint | `JiraOperator` / `AzureDevopsOperator` | Transport `mcp` → `api` → `playwright` |
| 2 | Architecture mapping | `ArchitectureMapper` + `build_architecture()` | Auto-baseline if score < 0.6 |
| 3 | Dev (install + build) | `DevAgent` + `WorktreeManager` + `detect_tech` | Per repo, parallel-safe |
| 4 | Lint | `LintRunner` | 19 stacks (eslint/ruff/clippy/etc.) |
| 5 | Tests | `TestRunner.run_unit() + run_e2e()` | Screenshot evidence in `evidence/` |
| 6 | Security review | `SecurityReviewer.scan()` | Flag-only (ADR-005) |
| 7 | Fix loop | re-run dev/lint/tests/security | Max 3 rounds (`MAX_FIX_LOOPS`) |
| 8 | Commit + push | `git add` → `commit` → `push --force-with-lease` | Per worktree branch |
| 9 | Create PR | `PrCreator.create()` | GitHub `gh` / ADO REST |
| 10 | PR review + Delivered | `PrReviewer.review_diff()` + `RunReport.to_json()` | Diff static checks |

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
| `LLM_PROVIDER`, `LLM_MODEL`, provider key (`ANTHROPIC_API_KEY` etc.) | LLM step (optional) |

---

## Pegadinhas

- Transport order fixed: `mcp` → `api` → `playwright`.
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
