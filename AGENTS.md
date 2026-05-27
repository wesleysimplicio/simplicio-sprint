# AGENTS.md — SendSprint

Canonical instruction file for AI agents in this repo. Read this FIRST.

## 1. What this is

**SendSprint is the agent** that finishes the cards assigned to you. It reads a
sprint (Jira / Azure DevOps / GitHub Issues), delegates each task's code edit to
**simplicio-cli**, captures evidence, and opens a **draft PR** for your review.

- **SendSprint = the brain.** Owns the flow end to end.
- **simplicio-cli = the executor.** Stateless: one task → applied diff. Nothing else.

Flow: read → organize → `simplicio task` → evidence (tests + screenshot) →
commit + push → draft PR → attach evidence → update ticket → watch PR → revise
loop → you approve.

## 2. Stack

- Python ≥ 3.11, Pydantic v2, Typer + Rich, httpx, pytest + ruff.
- Optional: `keyring` (creds), `playwright` (screen evidence), `simplicio-cli` (executor).

## 3. Layout

```
sendsprint/
├── operators/   JiraOperator, AzureDevopsOperator, GitHubIssuesOperator (transport mcp|api)
│   └── _mcp_bridge.py  host-injected MCP seam (register_provider → fetch)
├── executor/    SimplicioExecutor — the ONLY boundary to simplicio-cli
├── mapper/      MapperAdapter — render a Sprint into simplicio-mapper .specs/ tasks
├── prompt/      PromptFanout — simplicio-prompt subagent fan-out (--subagents 600)
├── delivery/    worktree, git_ops, evidence, pr
├── models/      Sprint, SprintItem, StepReport, RunReport, ScopeConfig
├── github_integration.py  ReviewReader + evidence comment + CI monitor
├── scope.py     --scope mine
├── flow.py      orchestrator (SprintFlow)
├── watch.py     unattended trigger (Watcher)
└── cli.py       run | watch | login | logout | version
```

**MCP transport.** The Python operators can't call MCP servers directly, so the
host (Claude) registers a provider per source via `_mcp_bridge.register_provider`
that returns the raw payload shape the REST path already maps. No provider → the
operator falls back to REST. **mapper** writes `.specs/` task files per card before
simplicio runs; **prompt** is an opt-in pre-execution brainstorm (`run --fanout`).

## 4. Commands

```bash
pip install -e ".[dev]"
pytest tests/ -q
ruff check sendsprint/ && ruff format sendsprint/

sendsprint run   <jira|azuredevops|github> <sprint> --repo . --repo-slug owner/repo --scope mine
sendsprint watch <jira|azuredevops|github> <sprint> --repo . --repo-slug owner/repo --once
```

## 5. Hard rules

- **simplicio-cli only executes.** Never make it branch/commit/PR — that's SendSprint.
  All invocation goes through `SimplicioExecutor` (`sendsprint/executor/simplicio.py`).
- **Transport is mcp → api.** No playwright scraping. `auto` tries MCP then REST.
- **PRs open as drafts.** The human approval gate is the user's only touchpoint.
- **Evidence is re-collected on every revise.** Never attach stale evidence to a PR.
- **Push uses bounded backoff** (2s,4s,8s,16s) — see `delivery/git_ops.py`.
- **Failures never abort the batch.** One bad item becomes a failed StepReport.

## 6. Adding a task source

1. New `operators/<name>_operator.py` subclassing `BaseOperator`.
2. Implement `_api_available`, `_read_via_api`, `_read_via_mcp`, optional `current_user`, `update_status`.
3. Map source items to `SprintItem`; return a `Sprint`.
4. Wire into `cli._build_operator` + `_read_kwargs`. Add a test.

## 7. Definition of Done

- [ ] Tests pass (`pytest tests/ -q`)
- [ ] Lint clean (`ruff check sendsprint/`) + formatted (`ruff format sendsprint/`)
- [ ] Version bumped in `sendsprint/__init__.py` + `pyproject.toml`
- [ ] Commit in English, imperative mood
