# ADR-009: Keep Python as the control plane and gate optional runtime accelerators

| Field | Value |
|-------|-------|
| Status | Accepted |
| Date | 2026-05-20 |
| Deciders | wesleysimplicio |
| Supersedes | ADR-001 alternatives for Go/Node/Rust as primary stacks |

---

## Context

Issue #105 collects the runtime split needed for SendSprint to stay responsive
while supporting heavier autonomous loops, multiple conversational adapters, and
Windows/GitHub Copilot usage. The risk is letting each stack grow its own
orchestrator, which would duplicate state, block the Python CLI/API, or make
Codex `/goal` and Claude Ralph Wiggum mandatory.

The current implementation already landed the child contracts:

- Python control-plane contracts and worker wire models (#106).
- Go worker boundary and Python fallback (#107).
- Rust accelerator boundary and Python fallback (#108).
- Node dashboard and Playwright isolation specs (#109).
- Windows and GitHub Copilot instructions (#110).
- Tri-agent status relay and deterministic status answers (#111, #116).
- Event persistence and audited control commands (#114, #115).
- Resource fan-out receipts and runtime baseline evidence (#118, #119).

## Decision

SendSprint keeps Python as the canonical control plane. Go, Rust, Node, Codex
`/goal`, and Claude Ralph Wiggum are optional acceleration or presentation
layers that must communicate through explicit contracts and must have a Python
fallback or read-only mode.

| Stack/profile | Owns | Does not own | Contract | Rollback |
|---|---|---|---|---|
| Python | CLI/API, planning, quality gates, memory, evidence, PR publishing | UI rendering only, browser execution, hot-path native acceleration | `RunCommand`, `RunEvent`, `ControlPlaneContract` | Disable optional workers; Python remains canonical |
| Go | Fan-out queues, watchdogs, heartbeat/status/log tail execution | Planning, quality gates, credentials, PR/issue publishing | `GoWorkerSpec` NDJSON request/response protocol | Missing binary or `prefer_go=False` uses `PythonWorker` |
| Rust | Scan, diff, dedupe, receipt/hash hot paths | Orchestration, worker lifecycle, user interaction | Accelerator resolver plus runtime baseline gate | `RustBridge(None)` delegates to Python implementations |
| Node | Dashboard rendering, operator chat UI, Playwright evidence capture | Scheduler, worker lifecycle, quality decisions, memory writes | `NodeDashboardSpec`, `DashboardEventProtocol`, `PlaywrightLaneSpec` | Python API/evidence bundle remains usable without dashboard |
| Copilot | Standard CLI-guided workflow on Windows | Codex `/goal`, Claude Ralph loops, direct worker management | `.github/copilot-instructions.md` and validation recipes | Follow normal `sendsprint` CLI commands |

## Runtime rules

- Python owns run state. Other stacks consume snapshots or emit typed events.
- Mutating operator actions go through authenticated Python API endpoints and
  audited control-command queues.
- Non-blocking operator conversation uses snapshots, SSE, and status renderers;
  it never waits on the active worker loop.
- Go and Rust are benchmark-gated. Add native implementations only when
  `sendsprint runtime-baseline` proves the Python path is the bottleneck.
- Node/Playwright can render or capture evidence, but cannot import Python
  internals or mutate `.sendsprint/runs/` files.
- Copilot users must have a complete Windows happy path without `/goal`,
  Ralph, or other agent-specific commands.

## Validation matrix

| Criterion | Validation |
|---|---|
| Python contract stability | `tests/test_contracts.py` and runtime readiness report |
| Go worker non-blocking boundary | `tests/test_workers.py`; `resolve_worker(prefer_go=False)` fallback |
| Rust optional accelerator | `tests/test_accelerators.py`; `sendsprint runtime-baseline ...` evidence |
| Node dashboard live status/chat | `tests/test_dashboard_spec.py`, `tests/test_dashboard_api.py` |
| Tri-agent answers | `tests/test_status_relay.py`, `tests/test_status_renderer.py`, `tests/test_status_answer.py` |
| Windows and Copilot path | `.github/copilot-instructions.md`, `tests/test_validation_recipes.py` |
| Epic closeout | `sendsprint runtime-readiness .` and `tests/test_runtime_readiness.py` |

## Consequences

### Positive

- SendSprint can add faster runtimes without splitting product ownership.
- Daily delivery remains possible on a plain Python install.
- Operators can ask Claude/Codex/Hermes for status while loops continue.
- Windows/Copilot users have the same supported workflow without hidden
  dependency on Codex or Claude-only accelerators.

### Negative

- Some high-performance work waits for benchmark evidence before implementation.
- Go/Rust/Node must maintain wire compatibility with Python-owned contracts.
- The control plane carries more contract tests because it is the integration
  authority.

## Review criteria

Revisit this ADR when:

- Runtime baseline evidence shows Python hot paths exceed the local
  responsiveness budget for repeated runs.
- A Go worker becomes long-lived and needs streaming protocol changes.
- Rust acceleration becomes mandatory rather than optional.
- Node needs to own more than UI/evidence presentation.

## Links

- Issue: https://github.com/wesleysimplicio/SendSprint/issues/105
- Roadmap: [ROADMAP.md](ROADMAP.md)
- Dashboard boundary: [DASHBOARD.md](DASHBOARD.md)
- Stack baseline: [ADR-001-stack.md](ADR-001-stack.md)
