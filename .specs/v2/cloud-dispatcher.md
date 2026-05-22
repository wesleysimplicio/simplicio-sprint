# SendSprint v2 — Cloud-First Dispatcher

Source for the v2 epic + sub-issues. This file is the durable home of the spec
because the issues failed to land via the GitHub MCP (token expired during the
create-issues run; no `gh` CLI available in this environment). Once GitHub MCP
re-auth is restored, the operator can split each section below into a real
issue with the labels documented at the end.

## Goal

Move SendSprint from **local serial runtime** (Ralph loop on Mac/VPS) to a
**cloud-first dispatcher**: read normalized tasks from Azure DevOps, fan them
out in parallel to the coding-agent provider clouds, collect tested PRs, and
close the loop with `git pull` locally + work-item status update.

## Before / After

Before (serial, ties up a machine):

```
Azure DevOps -> sync -> .task.md -> Ralph loop (LOCAL/VPS) -> PR
```

After (parallel, machine-free):

```
Azure DevOps -> ingest -> normalized task -> Router (round-robin)
  -> [Claude | Codex | Copilot | Cursor | Windsurf | Kiro] (vendor cloud)
  -> tested PR -> local git pull (review) -> merge -> work item "Done"
```

The Ralph loop stops being the engine; parallelism across cloud containers
replaces serial iteration.

## What survives

- Azure DevOps ingestion -> structured task (the genuine value)
- `.task.md` format (Contexto, AC, Test plan, DoD) becomes the PROMPT carried
  to each cloud provider
- Playwright evidence + DoD gate run INSIDE the provider container

## What changes / breaks

- Serial Ralph loop stops being the engine (becomes a parallel batch instead)
- Azure DevOps MCP calls move OUT of the executor and INTO a GitHub Action on
  merge — the vendor container has no SendSprint MCP installed
- Phone -> Mac dispatch loses purpose; no need to keep the Mac awake

## Per-provider reality

| Provider | External cloud trigger                  | v2 status   |
|----------|-----------------------------------------|-------------|
| Claude   | OK (web routines / managed-agents API)  | first-class |
| Codex    | OK (app/API fire-and-forget)            | first-class |
| Copilot  | OK (assign issue -> @copilot)           | first-class |
| Cursor   | Partial (background agents, limited API)| best-effort |
| Windsurf | Weak (Cascade is IDE-first)             | spike       |
| Kiro     | No clean external cloud trigger (AWS IDE)| spike      |

The adapter interface is first-class for all six. Real implementations only
land where the vendor exposes a trigger. IDE-bound providers stay as spikes
with a documented fallback (route to Claude/Codex).

## Sub-issues (planned)

| Tag       | Title                                                              | Labels                              |
|-----------|--------------------------------------------------------------------|-------------------------------------|
| INGEST    | Ingestion: Azure DevOps -> normalized task                         | cloud-dispatch, ingestion           |
| IFACE     | ProviderAdapter (common interface)                                 | cloud-dispatch, adapter             |
| CLAUDE    | Adapter: Claude                                                    | cloud-dispatch, adapter             |
| CODEX     | Adapter: Codex Cloud                                               | cloud-dispatch, adapter             |
| COPILOT   | Adapter: Copilot                                                   | cloud-dispatch, adapter             |
| CURSOR    | Adapter: Cursor (best-effort)                                      | cloud-dispatch, adapter, spike      |
| WIND      | Adapter: Windsurf (spike)                                          | cloud-dispatch, adapter, spike      |
| KIRO      | Adapter: Kiro (spike)                                              | cloud-dispatch, adapter, spike      |
| ROUTER    | Router round-robin parallel                                        | cloud-dispatch, router              |
| GATE      | PR validation gate (Playwright + DoD inside container)             | cloud-dispatch, feedback-loop       |
| LOOP      | Feedback loop: merge -> work-item update + local git pull          | cloud-dispatch, feedback-loop       |
| INFRA     | Config providers.yml + secrets/env                                 | cloud-dispatch, infra               |
| RMLOCAL   | Remove the local serial execution runtime                          | cloud-dispatch                      |

## DoD (epic)

- [ ] 3 first-class adapters working end-to-end (Claude / Codex / Copilot)
- [ ] 1 real Azure DevOps task turning into a tested PR
- [ ] Local git pull + work-item update on merge automatic
- [ ] Ralph serial retired with no loss of functionality

## Sub-issue detail

### INGEST — Ingestion: Azure DevOps -> normalized task

**Labels:** `cloud-dispatch,ingestion`

**Context:** SendSprint stops being the source of truth. It reads work items
from the current sprint via the Azure DevOps MCP and emits a normalized task
that turns into the PROMPT consumed by the provider cloud.

**Acceptance Criteria:**

- [ ] Reads current-sprint work items via the Azure DevOps MCP
- [ ] Emits a task in the canonical format (Contexto, AC, Out of scope, Test
      plan unit+e2e, DoD, Pegadinhas, Source: link work item)
- [ ] Idempotent: re-running does not duplicate, it updates on change
- [ ] Output is a direct prompt for the adapters (no extra translation)

**Out of scope:** agent execution (separate sub-issue).

**DoD:** Runs against a real sprint, emits at least one valid task carrying
the work-item link.

### IFACE — ProviderAdapter: common interface

**Labels:** `cloud-dispatch,adapter`

**Context:** Single contract every provider implements; plug/unplug without
touching the router.

**Proposed interface:**

```
dispatch(task)  -> run_id          # ship the task to the provider cloud
poll(run_id)    -> status          # queued | running | done | failed
collect(run_id) -> { pr_url, branch, evidence }
capabilities()  -> { cloud, network, mcp }
```

**Acceptance Criteria:**

- [ ] Abstract interface defined (matching the SendSprint stack)
- [ ] `capabilities()` declares whether the provider has a real cloud trigger
- [ ] Adapter without a real cloud returns `cloud:false` -> router skips or
      falls back
- [ ] Standardized errors (timeout, auth, no-cloud, vendor-blocked)

**DoD:** A mock adapter implements the interface and passes a test.

### CLAUDE — Adapter: Claude (web routines / managed-agents API)

**Labels:** `cloud-dispatch,adapter`

**Context:** First-class. Ships work to Anthropic infra via routines
(claude.ai/code) or the managed-agents API.

**Acceptance Criteria:**

- [ ] `dispatch` creates a cloud session/routine from the normalized task
- [ ] Environment: setup script + env vars wired
- [ ] `collect` returns the PR on branch `claude/<id>`
- [ ] Agent network configured per the task
- [ ] capabilities: cloud:true

**Pegadinhas:** sandbox = fresh clone; no dedicated secrets store (do not
commit sensitive keys in visible env).

**DoD:** One task turns into a tested PR end-to-end.

### CODEX — Adapter: Codex Cloud (fire-and-forget)

**Labels:** `cloud-dispatch,adapter`

**Context:** First-class. OpenAI microVM, two-phase (setup with network /
agent offline).

**Acceptance Criteria:**

- [ ] `dispatch` creates a task in the Codex environment
- [ ] Setup script pre-installs deps (network only in the setup phase)
- [ ] Env vars persisted via `~/.bashrc` OR environment settings (export does
      not persist!)
- [ ] AGENTS.md in the repo guides the agent
- [ ] `collect` returns PR/diff

**Pegadinhas:** Internet OFF during the agent phase (no pip/API at runtime);
cache lasts 12 hours.

**DoD:** One task turns into a tested PR end-to-end.

### COPILOT — Adapter: Copilot (assign issue -> @copilot)

**Labels:** `cloud-dispatch,adapter`

**Context:** First-class, more GitHub-native. Runs in GitHub Actions and
naturally closes the issue -> PR loop.

**Acceptance Criteria:**

- [ ] `dispatch` creates/assigns an issue to @copilot from the task
- [ ] `copilot-setup-steps.yml` prepares the environment
- [ ] `collect` reads the PR that Copilot opens
- [ ] Configure Claude as the engine when possible (multi-model)

**Advantage:** Pure issue -> PR fits the Jira/ADO flow; runs in Actions
(makes the feedback loop trivial to wire).

**DoD:** One assigned issue turns into a tested PR.

### CURSOR — Adapter: Cursor background agents (best-effort)

**Labels:** `cloud-dispatch,adapter,spike`

**Context:** Best-effort. Background Agents run on an Ubuntu VM with network
ON; `.cursor/Dockerfile` customizes the env. But programmatic external
triggers are limited (IDE-bound).

**Acceptance Criteria:**

- [ ] Spike: confirm whether any API/CLI can trigger a background agent
      from outside the IDE
- [ ] If YES: implement dispatch/poll/collect
- [ ] If NO: capabilities cloud:false + documented blocker + fallback
      (Claude/Codex)
- [ ] `.cursor/Dockerfile` versioned (advantage: network ON, runtime deps work)

**DoD:** Documented decision (API? yes/no) + chosen path.

### WIND — Adapter: Windsurf Cascade (spike)

**Labels:** `cloud-dispatch,adapter,spike`

**Context:** Spike. Cascade is IDE-first. External cloud triggers are likely
nonexistent / weak.

**Acceptance Criteria:**

- [ ] Spike: investigate external cloud trigger (API/CLI/headless)
- [ ] Document the result
- [ ] If unviable: capabilities cloud:false + declared fallback
- [ ] Do NOT block v2 waiting on vendor

**DoD:** Report — viable? how? or blocked-on-vendor.

### KIRO — Adapter: Kiro (spike)

**Labels:** `cloud-dispatch,adapter,spike`

**Context:** Spike. Kiro (AWS) is spec-driven, IDE-bound. No clean external
cloud trigger known.

**Acceptance Criteria:**

- [ ] Spike: investigate external trigger / headless / API
- [ ] Document
- [ ] If unviable: capabilities cloud:false + fallback
- [ ] Do NOT block v2

**DoD:** Report — viable? or blocked-on-vendor.

### ROUTER — Router: round-robin parallel

**Labels:** `cloud-dispatch,router`

**Context:** Distributes sprint tasks across providers in round-robin and
dispatches in PARALLEL. Respects capabilities (skips `cloud:false` or applies
fallback).

**Acceptance Criteria:**

- [ ] Reads the queue of normalized tasks
- [ ] Round-robin across providers with `cloud:true`
- [ ] Dispatches in parallel (N concurrent), not serial
- [ ] Provider without real cloud -> skip or configurable fallback
- [ ] Collects run_ids, polls until done/failed, aggregates results
- [ ] Config: max parallelism, per-task timeout, retry

**Optional (decide):** "race" mode — same task to 2 providers, keep the
first PR that goes green (more cost, faster / better quality).

**DoD:** 3 tasks across 3 providers in parallel -> 3 PRs.

### GATE — PR validation gate: Playwright + DoD in container

**Labels:** `cloud-dispatch,feedback-loop`

**Context:** Tests run INSIDE the provider container, before the PR. PR only
turns green with evidence.

**Acceptance Criteria:**

- [ ] Each task carries a test plan (unit + Playwright e2e) inside the prompt
- [ ] Provider runs lint + unit + e2e in the container
- [ ] Evidence (test-results/, screenshots) attached/linked to the PR
- [ ] `.github/workflows/dod.yml` validates on PR
- [ ] PR without evidence = not mergeable

**DoD:** One PR arrives with Playwright evidence + green CI.

### LOOP — Feedback loop: merge -> work-item update + local git pull

**Labels:** `cloud-dispatch,feedback-loop`

**Context:** Closes the cycle. Moves the work-item update OUT of the
container (no MCP there) and INTO a GitHub Action on merge. Makes local
`git pull` easy for review before merge.

**Flow:**

```
PR opens -> git pull branch locally -> Wesley reviews -> merge
   merge -> GitHub Action -> Azure DevOps work item "Done"
   PR open -> Action -> work item "In Review"
```

**Acceptance Criteria:**

- [ ] Action on PR open -> work item "In Review"
- [ ] Action on merge -> work item "Done"
- [ ] Update via Azure DevOps REST/MCP running in the Action (NOT in the
      provider container)
- [ ] Doc: `git fetch && git checkout <branch>` recipe for local review
      before merge
- [ ] Merge notification (channel to define)

**DoD:** One PR closes the full cycle (open -> In Review, merge -> Done)
automatically.

### INFRA — Config: providers.yml + secrets/env

**Labels:** `cloud-dispatch,infra`

**Context:** Central config for providers + secrets handling.

**Acceptance Criteria:**

- [ ] `providers.yml`: list of providers, priority, max parallel, timeout,
      fallback
- [ ] Secrets via GitHub Secrets / env (never committed)
- [ ] `.env.example` with placeholders per provider
- [ ] Per-provider setup doc (auth, scope)

**DoD:** Config validated, 3 first-class providers authenticating.

### RMLOCAL — Remove the local serial execution runtime

**Labels:** `cloud-dispatch`

**Context:** Retires the serial Ralph loop as the engine. Keeps only what
migrated to cloud/Action.

**Acceptance Criteria:**

- [ ] Map what the serial Ralph used to do
- [ ] Ensure each piece has a migrated equivalent (cloud dispatch + gate +
      loop)
- [ ] Remove/archive `.ralph/loop.sh` serial without losing functionality
- [ ] Update README: new cloud-first flow
- [ ] Do not touch main until v2 is validated

**Out of scope:** removing ingestion (ingestion stays).

**DoD:** Serial Ralph removed, cloud-first flow documented, nothing broken.

## Labels

| name           | color  | description                                       |
|----------------|--------|---------------------------------------------------|
| epic           | 6f42c1 | Epic / umbrella initiative                        |
| cloud-dispatch | 1d76db | SendSprint cloud-first dispatcher                 |
| adapter        | 0e8a16 | Provider adapter                                  |
| router         | fbca04 | Task -> provider routing                          |
| ingestion      | 5319e7 | Azure DevOps ingestion -> task                    |
| feedback-loop  | d93f0b | PR -> local git pull -> update work item          |
| spike          | c2e0c6 | Investigation / best-effort (vendor may block)    |
| infra          | bfdadc | Config, secrets, CI                               |
