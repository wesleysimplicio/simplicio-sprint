# SendSprint

<p align="center">
  <img src="./docs/assets/sendsprint-hero.png" alt="SendSprint turns sprint work into validated pull requests" />
</p>

> 🇺🇸 English. Leia em português: [README.pt-BR.md](README.pt-BR.md).

**SendSprint is an autonomous agent that finishes the cards assigned to you.**
It reads your sprint from **Jira**, **Azure DevOps** or **GitHub Issues**, hands
each task to **[simplicio-cli](https://github.com/wesleysimplicio/simplicio-cli)**
for the actual code edit, captures test + screen evidence, commits on an
isolated branch, and opens a **draft pull request** with the evidence attached.
Then it watches the PR and feeds your review comments back to simplicio until
you approve.

You don't sit at the keyboard invoking it. A scheduled trigger runs it; your
only job is to **review the draft PR**.

## The split that makes it work

- **SendSprint = the agent (the brain).** It owns the flow start to finish:
  read → organize → execute → evidence → commit → PR → update ticket → review loop.
- **simplicio-cli = the executor (the hands).** Stateless. It runs *one task →
  applied diff*. It knows nothing about sprints, branches or PRs.

```
trigger (cron / GitHub Action / Claude web)   ← removes you from the loop
  └─ SendSprint (agent)
       1. read sprint        Jira / Azure DevOps / GitHub Issues   (--scope mine)
       2. organize tasks
       3. simplicio task ...  ← the only thing simplicio-cli does
       3b. collect evidence   tests + Playwright screenshot
       4. commit + push
       5. open DRAFT PR       ← your only review surface
       6. attach evidence     test results + embedded screenshots
       7. update the ticket   "In Review" + PR link
       8. watch the PR        review comment? → simplicio revises → re-evidence
            ✓ you approve → merge → next card
```

## Productivity

### Without vs. with SendSprint

![Without vs. with SendSprint](./docs/assets/sendsprint-productivity-before-after.png)

### SendSprint as the delivery engine

![SendSprint productivity engine](./docs/assets/sendsprint-productivity-engine.png)

## 🎬 Videos

![SendSprint before and after poster](./video/preview/sendsprint-before-after-poster-en.png)

<p align="center">
  <a href="./video/preview/sendsprint-before-after-en.mp4">▶️ English MP4</a>
  &nbsp;·&nbsp;
  <a href="./video/preview/sendsprint-before-after-pt.mp4">🇧🇷 Portuguese MP4</a>
  &nbsp;·&nbsp;
  <a href="./video/preview/sendsprint-en-preview.gif">Product explainer</a>
</p>

---

## Install

```bash
pip install -e .
pip install simplicio-cli            # the executor
pip install -e ".[screenshot]"       # optional: Playwright screen evidence
playwright install chromium          # optional
```

## Quick start

```bash
# one-time credential storage (OS keyring)
sendsprint login jira
sendsprint login azuredevops
# GitHub uses the GITHUB_TOKEN env var

# deliver a sprint — each card → simplicio → evidence → draft PR
sendsprint run jira 42 --repo . --repo-slug owner/repo --scope mine
sendsprint run azuredevops "Team\\Sprint 12" --repo . --repo-slug repoId
sendsprint run github 7 --repo . --repo-slug owner/repo   # milestone #7

# unattended: finish my cards without me at the keyboard
sendsprint watch jira 42 --repo . --repo-slug owner/repo --once   # one pass (cron/CI)
sendsprint watch jira 42 --repo . --repo-slug owner/repo          # loop forever
```

`simplicio-cli` reads its model/provider config from the environment
(`SIMPLICIO_MODEL`, `SIMPLICIO_BASE_URL`, `SIMPLICIO_TEST_CMD`).

## Unattended trigger

The point is to not invoke it manually. Run `sendsprint watch ... --once` from:

- a **GitHub Action** on a schedule — see
  [`.github/workflows/sendsprint.yml`](./.github/workflows/sendsprint.yml);
- a **cron job**;
- a **Claude Code on the web** scheduled trigger
  ([docs](https://code.claude.com/docs/en/claude-code-on-the-web)).

It scopes to your cards (`--scope mine`), delivers the ones it hasn't delivered
yet (state in `.sendsprint/runs/watch-state.json`), and stops at the draft PR.

## How Claude / Codex invoke it

The host assistant never reimplements the flow — it shells out to the
`sendsprint` CLI. A trigger phrase (`/sendsprint`, "rode o sendsprint") makes
Claude/Codex run `sendsprint run ... --scope mine`. Manifests live under
[`skills/claude`](./skills/claude) and [`skills/codex`](./skills/codex).

## Architecture

```
sendsprint/
├── operators/      task readers: JiraOperator, AzureDevopsOperator, GitHubIssuesOperator (mcp|api)
├── executor/       SimplicioExecutor — the boundary to simplicio-cli (task → applied diff)
├── delivery/       worktree, git_ops (commit+push), evidence (tests+screens), pr (create+review)
├── models/         Sprint, SprintItem, StepReport, RunReport, ScopeConfig (Pydantic v2)
├── github_integration.py  ReviewReader (PR feedback) + evidence comment posting + CI
├── scope.py        --scope mine filtering
├── flow.py         the orchestrator (read → simplicio → evidence → PR → review loop)
├── watch.py        the unattended trigger
└── cli.py          Typer CLI: run, watch, login, logout, version
```

## Environment variables

| Variable | For |
|---|---|
| `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | Jira |
| `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT` | Azure DevOps |
| `GITHUB_TOKEN`, `GITHUB_REPO` | GitHub Issues + PRs |
| `SIMPLICIO_MODEL`, `SIMPLICIO_BASE_URL`, `SIMPLICIO_TEST_CMD` | simplicio-cli |

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -q
ruff check sendsprint/
```

## License

MIT — see [LICENSE](./LICENSE).
