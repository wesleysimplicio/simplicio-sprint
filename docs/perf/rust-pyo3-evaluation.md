# Rust + PyO3 Hybrid Evaluation for SendSprint

**Issue:** [#267 — Explorar abordagem híbrida Python + Rust (PyO3) para performance](https://github.com/wesleysimplicio/simplicio-sprint/issues/267)

**Status:** Evaluation only — no Rust code is added to the project by this
document. It defines the decision criteria, identifies candidate modules,
proposes a minimal pilot, and lists rollout gates.

## TL;DR

SendSprint is an I/O-bound CLI: most wall-clock time is spent on LLM HTTP
calls, GitHub/Jira/Azure API requests, and subprocess fan-outs to
`simplicio-cli`. The hot paths optimized in #265 (HTTP pooling, template
cache, `orjson`) are the right first lever.

A Rust/PyO3 layer is **not recommended as a general migration**. It pays off
only for narrow, CPU-bound kernels that run many times per sprint. The
realistic candidates are: sprint-plan validation, fan-out task batching, and
the precedent-index lookup. Anything LLM- or network-bound stays in Python.

Recommended next step: a small pilot crate (`sendsprint-core`) implementing
**only** the sprint-plan validator (Pydantic → Rust struct round-trip), gated
by a feature flag and a benchmark suite. Decide go/no-go after the
benchmarks.

## What we actually spend time on today

Wall-clock breakdown for a representative `sendsprint run` (estimates from
profiling work that fed #265; refine in the pilot):

| Phase                                                   | Share  | Bound by         |
| ------------------------------------------------------- | ------ | ---------------- |
| LLM completions (mapper, planner, retro)                | ~55%   | network + remote |
| Operator I/O (Jira/AzDO/GitHub list + comments)         | ~20%   | network          |
| `simplicio-cli` subprocess fan-out                      | ~15%   | subprocess + IO  |
| Repo scan / tech detector / mapper rendering            | ~5%    | disk + CPU       |
| Sprint model build, validation, template rendering      | ~3%    | CPU              |
| Everything else (git ops, evidence collection)          | ~2%    | mixed            |

Implication: even a 10× speedup on the CPU-bound 3% only buys ~2.7% off the
total. A Rust port is justified **only when** a specific kernel becomes
non-trivial — N grows large, or the kernel runs many times per sprint.

## Candidate modules (from the issue)

The issue lists three opportunities. Each is rated by `effort` (Rust+PyO3
work) vs. `payoff` (impact on a real sprint), with the path to the current
Python implementation.

### 1. Geração estruturada de tarefas — `sendsprint/prompt/fanout.py`

- Current: `PromptFanout` shells out to the kernel runtime via `subprocess`,
  parses JSON, aggregates a `FanoutResult` (`sendsprint/prompt/fanout.py:67`).
- Bottleneck: the kernel itself + subprocess startup, not the aggregation.
- Effort: low — aggregator is ~200 LOC of dataclass logic.
- Payoff: **low**. Moving aggregation to Rust saves microseconds; the
  subprocess and provider latency dominate.
- Verdict: **skip**. Optimize the subprocess boundary (batch invocation,
  long-lived runner) before reaching for Rust.

### 2. Validação de planos de sprint — `sendsprint/models/sprint.py` + `sendsprint/mapper/adapter.py`

- Current: Pydantic v2 models (`Sprint`, `SprintItem`) + adapter rendering
  (`sendsprint/models/sprint.py:32`, `sendsprint/mapper/adapter.py:53`).
- Bottleneck: at N≈10–50 items per sprint, Pydantic v2 is already fast
  (it's Rust internally via `pydantic-core`). For typical sprints, parsing
  is <5ms.
- Effort: medium — would need to mirror the model surface, plus PyO3
  bindings, plus keep Pydantic for the JSON contract.
- Payoff: **low to medium**. Only meaningful if sprint sizes grow into the
  thousands of items (epics with deep sub-tree) or if validation runs in a
  tight loop (e.g. watch mode polling).
- Verdict: **pilot candidate** — but only the *cross-item* validation
  (cycle detection in parent/child links, dependency closure, status
  consistency), not the per-field parse. Pydantic already wins the
  per-field race.

### 3. Lógica de estado complexa — `sendsprint/flow.py` + `sendsprint/watch.py`

- Current: `SprintFlow` orchestrates the per-item pipeline; `watch` runs a
  polling loop.
- Bottleneck: every step is I/O (git, simplicio-cli, GitHub API). The state
  machine itself is trivial.
- Effort: high — porting the orchestration to Rust means re-binding every
  side-effect (git, subprocess, HTTP).
- Payoff: **negligible**. The Python orchestration overhead is sub-millisecond
  per item; the I/O is seconds to minutes per item.
- Verdict: **skip**. Wrong layer.

## Other candidates worth a benchmark

Not in the issue's list, but more likely to actually benefit from Rust:

- **`sendsprint/tech/detector.py`** — walks a repo tree, reads `package.json`,
  `pyproject.toml`, etc. CPU work is small per repo but scales with file
  count. A Rust walker (`ignore` crate) would beat `pathlib.Path.rglob` on
  large monorepos. Pilot-worthy if users run SendSprint against repos with
  10⁵+ files.
- **`.simplicio/precedent-index.json` lookup** — referenced by the mapper
  adapter (`sendsprint/mapper/adapter.py:40`). If this grows into a large
  similarity index, a Rust BK-tree / Levenshtein crate is the natural fit.
  Not relevant at current scale.

## Decision criteria

Add a Rust crate **only when** a benchmark shows:

1. The kernel takes ≥100ms wall-clock on a realistic input *and* runs at
   least 5× per `sendsprint run`, OR
2. The kernel is on the watch-mode hot path and CPU shows up in profiling.

Reject Rust for:

- One-shot CPU work under 50ms.
- Anything that has to call back into Python for I/O on every iteration —
  the GIL re-acquire cost will undo most of the win.
- Glue / orchestration code.

## Proposed pilot: `sendsprint-core` validator crate

If the team wants to learn PyO3 with low risk, the smallest useful crate is:

- Crate name: `sendsprint-core`
- Layout: Cargo workspace inside `crates/sendsprint-core/`
- Build: `maturin` (`pyproject.toml` extension), wheel published with the
  Python package.
- Single export: `validate_sprint_plan(plan_json: bytes) -> ValidationReport`
  - Input: JSON bytes (already what `orjson` produces).
  - Work: parse to Rust structs (`serde_json`), run cross-item validation
    (cycle detection in parent/child, status consistency, label dedupe,
    acceptance-criteria heuristics), return a structured report.
  - Output: dict (PyO3 `pyo3::types::PyDict`) consumable by the Python
    caller, or `bytes` re-encoded by `orjson` on the Python side.
- No mutation of the Python `Sprint`/`SprintItem` model — Rust returns a
  diagnostic report; Python remains the source of truth.

Why this shape:
- It crosses the FFI boundary exactly twice (bytes in, dict out).
- It has zero callbacks to Python — no GIL juggling.
- It's the smallest unit where Rust's cycle detection + iteration cost is
  meaningfully different from Python at scale.

## Rollout gates

Before merging any Rust code:

1. **Benchmark harness lands first** — `bench/validate_sprint_plan.py`
   with N=10, 100, 1 000, 10 000 synthetic items. Records Python baseline
   numbers under `bench/results/`.
2. **Feature flag** — `SENDSPRINT_USE_RUST_CORE=1` to opt in. Default off.
   The Python validator stays as the reference; Rust is a *parallel* path
   for at least one release.
3. **Build matrix** — wheels for CPython 3.11/3.12/3.13 on Linux x86_64,
   macOS arm64, and Windows x86_64. If maturin/CI cost outweighs the
   payoff, abandon the pilot.
4. **Acceptance threshold** — ≥3× speedup at N=1 000 in the benchmark, OR
   the validator becomes the hot path in `flow.py` profiling. Otherwise
   delete the crate.

## What we are NOT doing

- No PyO3 wrapper around HTTP, git, subprocess, or filesystem I/O.
  `httpx` + `subprocess` are the right tools.
- No replacement for Pydantic. `pydantic-core` is already Rust.
- No rewrite of `simplicio-cli` or the kernel — those are owned elsewhere.
- No "Rust-first" build target. Python remains the only required toolchain
  for contributors; Rust would be opt-in for maintainers building wheels.

## Open questions

- Are there real users running SendSprint against sprints with thousands of
  items? If not, the pilot is academic.
- Does the team want to take on a Rust toolchain dependency for the release
  pipeline? Maturin + cibuildwheel is well-trodden but non-zero cost.
- Would a NumPy-style C-extension (e.g. `cython`) be enough for the same
  validators? It's a faster on-ramp than PyO3 for pure-CPU kernels.

## Recommendation

Defer the Rust port. Land the #265 optimizations first, instrument
`flow.py` with timing, and revisit this evaluation once we have real
profiling numbers for a sprint with ≥100 items. If those numbers show CPU
on the sprint-plan validator, run the pilot in this doc.
