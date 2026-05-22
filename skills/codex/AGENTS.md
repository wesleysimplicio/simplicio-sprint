---
name: sendsprint
description: SendSprint 10-step sprint delivery flow (Jira/ADO → PR). Codex auto-loads this when present in repo root or skills/codex/.
version: 0.2.2
platform: codex
---

# SendSprint — Codex agent manifest

> **Read [/AGENTS.md](../../AGENTS.md) FIRST** for canonical project instructions (stack, layout, commands, patterns, gotchas, DoD). This file = Codex-specific skill manifest.

---

## Trigger

Auto-load when user prompt mentions:

- pt-BR: "rode o sendsprint", "executar sprint", "entregar sprint", "processar sprint do Jira", "processar sprint do ADO"
- en: "run sendsprint", "execute sprint", "deliver sprint", "process Jira sprint", "process ADO sprint", "ship sprint"
- es: "ejecutar sprint", "procesar sprint", "entregar sprint"

Also infer: prompt contains sprint id + Jira/ADO mention + repo path.

---

## Steps

1. **Read sprint** → `JiraOperator(sprint_id)` or `AzureDevopsOperator(iteration_path)`. Transport `auto` resolves `mcp` → `api` → `playwright`.
2. **Architecture mapping** → `ArchitectureMapper.map(repo)`. If score < 0.6 → `build_architecture(repo)` to seed baseline docs.
3. **Dev** → `detect_tech(repo)` + `WorktreeManager(repo, branch)` + `DevAgent.install_and_build()`.
4. **Lint** → `LintRunner.run()` per detected stack.
5. **Tests** → `TestRunner.run_unit() + run_e2e()` with screenshot evidence to `evidence/`.
6. **Security review** → `SecurityReviewer.scan()` (flag-only, ADR-005).
7. **Fix loop** → max 3 rounds re-running dev/lint/tests/security. Report which checks triggered retry.
8. **Commit + push** → `git add -A && git commit -m "..."` then `git push -u origin <branch> --force-with-lease`.
9. **PR creation** → `PrCreator.create()` via GitHub (`gh`) or Azure DevOps REST.
10. **PR review + Delivered** → `PrReviewer.review_diff()` + `RunReport.to_json()` to `report.json`.

---

## Stack

Python ≥ 3.11 · Pydantic v2 · Typer · Rich · httpx · playwright (sync) · pyyaml · hatchling.

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

## First-run prompts (one-time, persisted)

The first interactive `sendsprint sprint` or `sendsprint run` without a
workspace.yaml that pins the values asks for:

- **branch name template** (default `feature/{number}-{title}`),
  tokens `{number}`, `{key}`, `{id}`, `{title}`, `{repo}`;
- **base branch** for new feature PRs (default `main`).

Stored at `~/.config/sendsprint/profile.yaml` under `branch:`. The
`branch.prompted: true` flag guarantees no re-prompt on later runs.
Non-interactive override:

```bash
sendsprint configure-defaults --branch-template "<template>" --base-branch <branch>
```

If a workspace.yaml provides the values, the prompt is silently
skipped and the profile is still marked prompted.

---

## Padrão de código

### Minimal Python invocation
```python
from sendsprint.flow import SprintFlow
from sendsprint.operators import JiraOperator

result = SprintFlow(operator=JiraOperator()).run(sprint_id=42)
print(result.to_json())
```

### Com workspace + scope
```python
from sendsprint.flow import SprintFlow
from sendsprint.operators import AzureDevopsOperator
from sendsprint.workspace import load_workspace
from sendsprint.scope import build_scope

ws = load_workspace("workspace.yaml")
scope = build_scope(mode="mine", user_email="dev@example.com")
flow = SprintFlow(operator=AzureDevopsOperator(), workspace=ws, scope=scope)
result = flow.run(iteration_path="Team\\Sprint 12")
```

---

## Env

| Var | Required for |
|---|---|
| `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | Jira API |
| `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT` | Azure DevOps API |
| `PLAYWRIGHT_CDP_URL` | Playwright fallback (default `http://127.0.0.1:9222`) |
| `LLM_PROVIDER`, `LLM_MODEL` | LLM step (optional) |

---

## Pegadinhas

- Transport order = fixed (`mcp` → `api` → `playwright`).
- Worktrees are real — cleanup in `WorktreeManager.__exit__`.
- Fix loop max 3 — beyond that = `failed=true`.
- Security flag-only — never auto-fix (ADR-005).
- Step numbers must match flow position (TestRunner=5, SecurityReviewer=6, LintRunner=4, PrCreator=9, PrReviewer=10).
- Push must precede PR creation (`_push_branch()` in flow).

---

## Definition of Done

- [ ] All 10 steps reported in `RunReport.steps[]`
- [ ] `RunReport.failed == false`
- [ ] At least one PR URL in `RunReport.prs[]` per repo with changes
- [ ] `report.json` written via `result.to_json()`
- [ ] Worktree cleaned up
- [ ] No secrets flagged in Step 6
