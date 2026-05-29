# Changelog

## 1.2.3

Dependency-alignment release for the Simplicio ecosystem.

- `simplicio-sprint` now declares the current package graph directly:
  `simplicio-cli>=0.4.3`, `simplicio-mapper>=0.6.1`, and
  `simplicio-prompt>=1.12.0`.
- A fresh `pip install -U simplicio-sprint` now pulls the updated executor,
  mapper, and prompt packages from PyPI.

## 1.2.2

Packaging release for the SendSprint cross-repo hardening plan.

- Ships the partner repository issue contract in the source distribution:
  `docs/cross-repo-issues.md`.
- Keeps the runtime code from 1.2.1 unchanged; this release makes the merged
  ecosystem coordination document available as the published package source.

## 1.2.1

Performance release that bundles the work from issues #265 and #267.

- **LLM client pooling + completion cache** (`sendsprint/llm/client.py`).
  `LlmClient` now owns an `httpx.Client` with configurable connection
  limits and reuses it across calls; identical completions are memoized
  via an LRU+TTL cache controlled by `SENDSPRINT_LLM_CACHE`,
  `SENDSPRINT_LLM_CACHE_SIZE`, and `SENDSPRINT_LLM_CACHE_TTL_S`.
- **Shared utility modules** (`sendsprint/utils/`). `LruTtlCache`,
  `TemplateRenderer`, and `orjson`-backed JSON helpers (`dumps_json`,
  `loads_json`) with a stdlib `json` fallback.
- **Cached sprint/backlog/retrospective templates** rendered once per
  identical input; `RETROSPECTIVE.md` is now materialized alongside
  sprint specs.
- **Optional Rust kernel** at `crates/sendsprint-core/` (PyO3 0.22,
  abi3-py311, maturin). `sendsprint.core.validate_sprint_plan` runs a
  full sprint-plan validator (cycle detection, duplicate keys, orphan
  parents, story-points, status, links, labels, acceptance criteria)
  and dispatches between the Rust extension and a pure-Python fallback
  via `SENDSPRINT_USE_RUST_CORE`. Empirical benchmark in
  `bench/results/` shows the Rust path is on par with Python at the
  current scale; see `docs/perf/rust-pyo3-evaluation.md` for the
  measured table and recommendation to keep Python as the default.

## 1.2.0

Reliability and ecosystem-integration release for the richer mapper/prompt flow.

- **Mapper artifacts are consumed directly.** `MapperAdapter` now reads
  `.simplicio/project-map.json` and `.simplicio/precedent-index.json`, ranks
  relevant files and precedent candidates per sprint item, embeds them in the
  task spec, and passes the same compact context to `simplicio-cli`.
- **YOOL/TUPLE/HAMT fan-out adapter.** `PromptFanout` can load the
  `simplicio-prompt` `examples/python/prompt_fanout.py` adapter via
  `SIMPLICIO_PROMPT_REPO`, use lazy `batch_spawn` semantics, track token/cost
  usage, and keep the legacy `SIMPLICIO_PROMPT_KERNEL` subprocess path as a
  graceful fallback.
- **Review and evidence loop hardening.** Evidence collection now writes a
  stable `.sendsprint/evidence/<key>/manifest.json`, PR comments deduplicate
  repeated artifacts, review feedback is deduplicated before revise, and
  revision comments are posted together with fresh evidence and feedback context.

## 1.0.0

First public release on PyPI as `simplicio-sprint` (clean reboot from the
previous `sendsprint` distribution — see entries below for historical context).
Bundles the simplicio-mapper + MCP integration, the simplicio-prompt subagent
fan-out, `sendsprint update`, the multi-agent `sendsprint install`, central
logging, the didactic EN/PT README and the end-to-end frontend demonstration.
Published via GitHub Actions Trusted Publishing
(`.github/workflows/publish.yml`); the source distribution ships only the
package (no videos / slide decks).

## 1.1.0

simplicio-mapper + MCP integration, plus the simplicio-prompt subagent fan-out.

- **MCP transport now works.** A host-injected seam
  (`operators/_mcp_bridge.py`) lets the agent feed MCP tool results to the Jira /
  Azure DevOps / GitHub operators, which reuse their REST→`Sprint` mappers. With
  no provider registered, `auto` transport falls back to REST as before.
- **simplicio-mapper adapter** (`mapper/`): renders a `Sprint` into the
  `.specs/sprints/sprint-XX/` format (`SPRINT.md`, `BACKLOG.md`, and one
  `NN-slug.task.md` per card with frontmatter + Acceptance Criteria, Test plan,
  Definition of Done). The flow writes each card's spec into the worktree so
  simplicio-cli has structured context.
- **simplicio-prompt fan-out** (`prompt/`): `PromptFanout` shells out to the
  Tuple-Space + Yool kernel (`--subagents 600`) to brainstorm edge cases and a
  plan per card, folding the result into the simplicio task. Opt-in via
  `sendsprint run --fanout`; degrades gracefully when the kernel is absent.
- **`sendsprint update`** (`bootstrap.py`): pulls the latest simplicio-cli (pip),
  simplicio-prompt kernel (git) and simplicio-mapper (git), and wires the
  previously-inert `verify_dependencies_on_start` / `update_*_on_start` profile
  flags so `run`/`watch` refresh tools at start (`--no-update` /
  `SENDSPRINT_NO_UPDATE=1` to skip). The fan-out auto-discovers the cached kernel.
- **`sendsprint install`** (`installer.py`): writes the SendSprint skill into each
  agent's convention — Cursor, Claude, Kiro (dedicated files) and Codex /
  OpenCode / Antigravity / Gemini / Hermes / openclaw (idempotent managed block in
  `AGENTS.md` / `GEMINI.md`, never clobbering existing content). `--target` or
  `--all`.
- **Central logging** (`logging_setup.py`): every command configures the
  `sendsprint` logger to a rotating file (DEBUG) plus console; `--log-level`,
  `--log-file`, `--log-json` are global options. The flow logs each delivery step,
  and `run` archives the `RunReport` JSON next to the logs.

## 1.0.0

Full rewrite around the simplicio-cli executor model.

- **SendSprint is the agent; simplicio-cli is the executor.** Each task is sent
  to `simplicio task` (one task → applied diff); SendSprint owns branching,
  evidence, commits, PRs and the review loop.
- Task sources: Jira, Azure DevOps, and **GitHub Issues** (new), transport mcp → api.
- Delivery layer: worktree isolation, commit + push with backoff, evidence
  (tests + Playwright screenshots), draft PR creation with embedded evidence.
- PR review loop: `revise_pr` feeds reviewer feedback back to simplicio and
  re-collects evidence.
- Unattended trigger: `sendsprint watch ... --once` (cron / GitHub Action /
  Claude Code on the web scheduled trigger), scoped with `--scope mine`.
- Removed the previous web/dashboard/API surfaces, the v2 cloud provider
  adapters, the yool/tuple/HAMT runtime, and the multi-IDE plugin packages —
  the repo is now just the agent flow.
