# SendSprint

![Coverage](./docs/assets/coverage-badge.svg)

<p align="center">
  <img src="./docs/assets/sendsprint-hero.png" alt="SendSprint turns sprint work into validated pull requests" />
</p>

> 🇺🇸 English. Leia em português: [README.pt-BR.md](README.pt-BR.md).


SendSprint is a sprint-to-pull-request delivery platform for engineering teams. It reads Jira or Azure DevOps sprint work, maps the target architecture, creates isolated branches/worktrees, builds, tests, checks security, captures evidence, commits, opens pull requests, reviews the diff, and reports delivery state in one controlled flow with opt-in LLM code generation and deploy callbacks.

The proposal is simple: remove the manual coordination tax between backlog, code, tests, evidence, and PRs. SendSprint gives teams a repeatable execution lane from sprint planning to `develop`, with preflight validation, dry-run planning, resumable runs, branch-per-task delivery, and auditable output.

## Productivity Visuals

### Team without vs. with SendSprint

![Team without vs. with SendSprint](./docs/assets/sendsprint-productivity-before-after.png)

### SendSprint as the delivery engine

![SendSprint productivity engine](./docs/assets/sendsprint-productivity-engine.png)

## 🎬 Videos

### Productivity before/after (47s)

![SendSprint before and after poster](./video/preview/sendsprint-before-after-poster-en.png)

<p align="center">
  <a href="./video/preview/sendsprint-before-after-en.mp4">▶️ English MP4 (1920×1080, 47s, 7.1 MB)</a>
  &nbsp;·&nbsp;
  <a href="./video/preview/sendsprint-before-after-pt.mp4">🇧🇷 Portuguese MP4 (1920×1080, 47s, 7.1 MB)</a>
</p>

### Product explainer (56s)

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

## Presentations

Stakeholder-ready implementation decks are available in editable and PDF formats:

- [English PPTX](./docs/presentations/sendsprint-implementation-en.pptx) · [English PDF](./docs/presentations/sendsprint-implementation-en.pdf)
- [Portuguese PPTX](./docs/presentations/sendsprint-implementation-pt-BR.pptx) · [Portuguese PDF](./docs/presentations/sendsprint-implementation-pt-BR.pdf)
- [Slide preview sheets](./docs/presentations/README.md)

The MP4 videos are generated locally by Remotion and include a generated music bed plus workflow sound effects (`cd video && npm run build:preview`).
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

> **Status:** v0.14.0 — Sprint Autopilot foundation. `sendsprint doctor`, stack validation templates (Angular, React, Vue.js, Node.js, Python, PHP, .NET, mobile, monorepo), autonomy policy, fuller dry-run plans, deterministic task worktrees, evidence bundles, GitHub Issues tracker helpers, Ralph Wiggum / Codex Goal loop contracts, transcript-to-task ingestion, local dashboard snapshots, demo docs, executive reports, and PyPI Trusted Publishing workflow support are built in. Core delivery still includes chat-triggered `sendsprint sprint`, Jira/Azure DevOps reads, opt-in LLM code generation/deploy callbacks, resumable run state, PR creation, post-PR validation, coverage badge automation, and changelog promotion.

---

## Flow

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

Optional hooks:

- **Step 3.5 — LLM code generation** applies an opt-in unified diff between build and lint.
- **Step 11 — Deploy trigger** posts an opt-in webhook after PR creation and attempts a ticket status update.

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
# Full 10-step flow against a Jira sprint
sendsprint run jira 42 --workspace workspace.yaml --scope mine -o report.json

# Same flow with opt-in LLM patch generation and deploy callback
sendsprint run jira 42 --workspace workspace.yaml --scope mine --llm-codegen --deploy

# Full flow against Azure DevOps
sendsprint run azuredevops "Team\\Sprint 12" --repo ./repo

# Validate environment/sprint safety before delivery
sendsprint preflight azuredevops "Team\\Sprint 12" --workspace workspace.yaml

# Plan branches/repos/PR targets without writing files or opening PRs
sendsprint run azuredevops "Team\\Sprint 12" --workspace workspace.yaml --dry-run

# Resume a previous run idempotently
sendsprint run azuredevops "Team\\Sprint 12" --workspace workspace.yaml --run-id sprint-12

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
branch_name_template: feature/{number}-{title}
pr_reviewers:
  - reviewer@example.com
required_pr_reviewers:
  - lead@example.com
code_generation:
  enabled: false
  provider: anthropic
  model: claude-opus-4-7
  max_usd: 1.0
  max_tokens: 8000
deploy:
  enabled: false
  provider: webhook
  url: https://deploy.example.com/hooks/sendsprint
  final_status: Deployed
repos:
  - name: backend-api
    path: backend-api
    role: api
    tech: dotnet
    default_branch: main
    pr_target_branch: develop
    # Optional per-repo reviewer rules:
    # required_pr_reviewers:
    #   - daniel.ribeiro_ext@interplayers.com.br
    # Optional per-repo override:
    # branch_name_template: hotfix/{number}-{title}
  - name: frontend-web
    path: frontend-web
    role: front
    tech: angular
  - name: mobile-app
    path: mobile-app
    role: mobile
    tech: flutter
```

Azure DevOps MCP can be configured for Codex with:

```bash
sendsprint install-ado-mcp --organization my-org --project "Projetos Ágeis" --team "Squad Yankee"
```

SendSprint can also expose its own deterministic tooling as an MCP stdio
server:

```bash
sendsprint mcp-serve
```

Current default MCP tools:

- `sendsprint_detect_tech`
- `sendsprint_check_architecture`
- `sendsprint_version`

The transport uses JSON-RPC 2.0 with `Content-Length` framing so Claude Code
and similar hosts can launch it directly.

When a User Story has no child tasks, SendSprint creates in-memory front/back
tasks before delivery. Generated tasks keep `parent_key` pointing to the story
and labels `scope:front` / `scope:back`, so each task runs only against matching
workspace repos.

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
│   └── sprint_flow.py orchestrator + opt-in codegen/deploy hooks
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

## Assistant Integrations

Per-platform integration manifests under `skills/`:

| File | Platform |
|------|---------|
| `skills/claude/SKILL.md` | Claude Code |
| `skills/codex/AGENTS.md` | Codex / OpenAI |
| `skills/hermes/hermes.md` | Hermes Agent |
| `skills/openclaw/openclaw.md` | Openclaw |
| `skills/copilot/copilot-instructions.md` | GitHub Copilot |

Each references the same Python core; the manifest teaches the host assistant how to invoke SendSprint consistently.

---

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

The suite covers operators, architecture mapper/builder, tech detector, scope filtering, workspace loading, CLI overrides, and all delivery agents including codegen/deploy orchestration.

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
- [x] LLM-powered code generation per sprint item
- [x] Deploy trigger + status callback to ticket
- [x] MCP server mode (expose SendSprint as an MCP tool)

---

## License

MIT - see [LICENSE](./LICENSE).
