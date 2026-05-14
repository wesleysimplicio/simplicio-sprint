# SendSprint

> 🇺🇸 English. Leia em português: [README.pt-BR.md](README.pt-BR.md).


Multi-agent skill that automates end-to-end sprint delivery. Reads Jira / Azure DevOps sprints, maps architecture, installs + builds, runs tests, scans for security issues, creates PRs, reviews diffs, and delivers — all in a single 9-step flow.

## 🎬 Videos

### Skill explainer (56s)

![SendSprint explainer preview](./video/preview/sendsprint-en-preview.gif)

<p align="center">
  <a href="./video/preview/sendsprint-explainer-en.mp4">▶️ Full MP4 (1920×1080, 56s, 20 MB)</a>
  &nbsp;·&nbsp;
  <a href="./video/preview/poster.png">🖼️ Poster</a>
</p>

### Run loop demo (22s) — what `web/RunScreen` shows

![SendSprint run loop](./video/preview/runloop-en-preview.gif)

<p align="center">
  <a href="./video/preview/runloop-en.mp4">▶️ Full MP4 (1920×1080, 22s, 5.5 MB)</a>
  &nbsp;·&nbsp;
  <a href="./video/">🛠️ Source (Remotion)</a>
</p>

> 🇧🇷 Versão em português dos vídeos: ver [README.pt-BR.md](README.pt-BR.md).

Both videos are generated locally by Remotion (`cd video && npm run build`).
The run-loop one shows exactly what happens in the browser when you open
`http://localhost:8081` and start a sprint delivery: round 1 fails with a
visual regression, fix-loop applies patches, round 2 turns green, PR opens.

## 🌐 Run it in your browser (web)

```bash
# 1) backend
pip install -e ".[api]"
python -m sendsprint.api          # http://localhost:8765

# 2) web UI (separate terminal)
cd web && npm install && npm run dev   # http://localhost:8081
```

See [`web/README.md`](./web/README.md) for the full walkthrough and
[`sendsprint/api/README.md`](./sendsprint/api/README.md) for the HTTP/SSE API.


Works across **13 AI coding tools**: Claude Code, Codex CLI, GitHub Copilot, Cursor, Windsurf, Kiro, Zed, Cline, Continue, Aider, Sourcegraph Cody, Hermes, Openclaw.

> **Status:** v0.7.0 — Chat-triggered one-command UX (`sendsprint sprint`). 13 IDE manifests. OS-keyring credential cache. Auto-scaffold `.specs/` plus latest `agentic-starter` sync. Full 10-step flow. PRs target `develop` by default and can be configured per workspace/repo. PyPI publishing is automated on release tags.

---

## 10-Step Flow

| Step | Name | What it does |
|------|------|-------------|
| 1 | **Read sprint** | Fetch stories/tasks/bugs from Jira or Azure DevOps |
| 2 | **Architecture mapping** | Inspect repo docs; auto-generate baseline if score < 0.6 |
| 3 | **Dev** | Detect tech stack, create worktree, install deps + build |
| 4 | **Lint** | Static analysis per tech (eslint, ruff, clippy, etc.) |
| 5 | **Tests** | Unit tests + Playwright E2E with screenshot evidence |
| 6 | **Security review** | Flag-only scan (secrets, env files, npm audit) |
| 7 | **Fix loop** | If lint/tests/security fail: re-build + re-run (max 3 rounds) |
| 8 | **Commit** | `git add -A && git commit` on worktree branch |
| 9 | **Create PR** | GitHub (gh CLI) or Azure DevOps REST API |
| 10 | **PR review + Delivered** | Diff analysis + RunReport with JSON export |

Transport priority: `mcp` -> `api` -> `playwright`.

---

## Requirements

- Python `>=3.11`
- Playwright (`playwright install chromium`)
- Optional: Jira API token / Azure DevOps PAT, or Atlassian / Azure DevOps MCP server

---

## Install

```bash
git clone https://github.com/wesleysimplicio/SendSprint.git
cd SendSprint
pip install -e .
playwright install chromium
cp .env.example .env  # fill in credentials
```

---

## Quick start

### CLI

```bash
# Full 9-step flow against a Jira sprint
sendsprint run jira 42 --workspace workspace.yaml --scope mine -o report.json

# Full flow against Azure DevOps
sendsprint run azuredevops "Team\\Sprint 12" --repo ./repo

# Detect tech stack
sendsprint detect-tech ./repo

# Check architecture mapping (with auto-build if missing)
sendsprint check-architecture ./repo --build

# Sync latest agentic-starter scaffold files into a repo
sendsprint sync-agentic-starter ./repo --ref latest
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
```

### Read a sprint only

```python
from sendsprint.operators import JiraOperator

op = JiraOperator(
    base_url="https://your-org.atlassian.net",
    transport="auto",
)
sprint = op.read_sprint(sprint_id=42)
for item in sprint.items:
    print(f"  [{item.type}] {item.key} - {item.title} ({item.status})")
```

---

## Multi-repo workspace

Define repos in `workspace.yaml`:

```yaml
name: my-project
root_path: /home/dev/repos
new_projects_dir: Projetos/novos
pr_provider: github
default_base_branch: develop
repos:
  - name: backend-api
    path: backend-api
    role: api
    tech: dotnet
    default_branch: main
    pr_target_branch: develop
  - name: frontend-web
    path: frontend-web
    role: front
    tech: angular
  - name: mobile-app
    path: mobile-app
    role: mobile
    tech: flutter
```

---

## Architecture

```
sendsprint/
├── operators/         JiraOperator, AzureDevopsOperator (mcp|api|playwright)
├── models/            Sprint, SprintItem, StepReport, RunReport (Pydantic v2)
├── agents/
│   ├── worktree.py    Git worktree isolation for parallel branches
│   ├── dev.py         Install + build per tech stack (16 package managers)
│   ├── lint_runner.py Static analysis per tech (19 linters)
│   ├── test_runner.py Unit + E2E with screenshot evidence
│   ├── security_reviewer.py  Secret scan, env audit, npm audit
│   ├── pr_creator.py  GitHub (gh) / Azure DevOps (REST) PR creation
│   └── pr_reviewer.py Diff static checks (TODO, debug, long lines)
├── architecture/
│   ├── mapper.py      Weighted architecture scoring
│   └── builder.py     Auto-generate baseline docs
├── tech/
│   └── detector.py    Filesystem marker detection (25+ techs)
├── workspace/
│   └── loader.py      YAML/JSON multi-repo workspace config
├── scope.py           --scope mine filtering (account_id, email, name)
├── flow/
│   └── sprint_flow.py 9-step orchestrator
├── llm/               Provider-agnostic LLM client
└── cli.py             Typer CLI
```

---

## Environment variables

| Variable | Required for |
|----------|-------------|
| `JIRA_BASE_URL` | Jira API |
| `JIRA_EMAIL` | Jira API |
| `JIRA_API_TOKEN` | Jira API |
| `AZURE_DEVOPS_ORG` | Azure DevOps API |
| `AZURE_DEVOPS_PROJECT` | Azure DevOps API |
| `AZURE_DEVOPS_PAT` | Azure DevOps API |
| `PLAYWRIGHT_CDP_URL` | Playwright fallback (default `http://127.0.0.1:9222`) |
| `LLM_PROVIDER` | LLM step (optional) |
| `LLM_MODEL` | LLM step (optional) |

---

## Skills

Per-platform entry points under `skills/`:

| File | Platform |
|------|---------|
| `skills/claude/SKILL.md` | Claude Code |
| `skills/codex/AGENTS.md` | Codex / OpenAI |
| `skills/hermes/hermes.md` | Hermes Agent |
| `skills/openclaw/openclaw.md` | Openclaw |
| `skills/copilot/copilot-instructions.md` | GitHub Copilot |

Each references the same Python core; the skill file teaches the host agent how to invoke it.

---

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

103 tests covering operators, architecture mapper/builder, tech detector, scope filtering, workspace loading, and all agents (lint, security, PR review).

---

## Roadmap

- [x] Step 1 - Sprint reading (Jira + Azure DevOps, MCP / API / Playwright)
- [x] Step 2 - Architecture mapping + auto-build baseline docs
- [x] Step 3 - Dev agent (tech detection, worktree isolation, install + build)
- [x] Step 4 - Test runner (unit + Playwright E2E with screenshot evidence)
- [x] Step 5 - Security reviewer (flag-only: secrets, env, npm audit)
- [x] Step 6 - Fix loop (re-build + re-test, max 3 rounds)
- [x] Step 7 - PR creation (GitHub gh CLI + Azure DevOps REST)
- [x] Step 8 - PR review (diff static checks)
- [x] Step 9 - RunReport with full evidence
- [x] Multi-repo workspace support (workspace.yaml)
- [x] `--scope mine` current-user filtering
- [ ] LLM-powered code generation per sprint item
- [ ] Deploy trigger + status callback to ticket
- [ ] MCP server mode (expose SendSprint as an MCP tool)

---

## License

MIT - see [LICENSE](./LICENSE).
