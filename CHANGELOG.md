# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

## [0.21.0] - 2026-05-20

### Added

- Frontend route inventory in `sendsprint/frontend_flows.py` with deterministic
  discovery for Next.js app/pages routes, common router declarations, and
  static HTML links, plus focused tests for the discovery contract.
- Generated Playwright route smoke support for frontend repos, including
  workspace/repo `playwright_auto_flows` configuration, generated specs inside
  `sendsprint-evidence/`, and dashboard coverage for the new Settings update
  state and degraded version-check state.

### Changed

- The web Settings screen now exposes SendSprint version checks through the
  local API, handles unavailable PyPI checks as a degraded state, clears stale
  version results on retry, and degrades more safely when backend auth status
  cannot be loaded.
- Workspace loading now resolves explicit relative `root_path` values relative
  to the workspace file, which makes portable `workspace.yaml` setups behave
  consistently across different process working directories.
- Web export metadata was cleaned up so the Console + Web local build no longer
  references a missing favicon asset during `expo export`.

### Fixed

- Frontend auto-flow execution now honors repo metadata (`role: front`) in
  addition to tech detection, treats workspace auto-flow settings as defaults
  instead of hard caps, and passes repo config through both the main test path
  and fix-loop retest path.
- Test runner behavior is more robust for generated Playwright flows: invalid
  dev-server commands return structured failures, readiness failures stop before
  Playwright runs, timeout paths keep newly created screenshot evidence, and
  stale screenshots from previous runs are no longer attached to new reports.
- Frontend discovery now avoids false negatives when a repo lives under an
  ancestor folder such as `dist/`, reduces false positives for asset/document
  paths, and avoids title bleed from a later route object into a previous one.

## [0.20.0] - 2026-05-20

### Added

- Deterministic task-understanding reports in `sendsprint/task_understanding.py`
  derive sprint item surfaces, capabilities, likely repositories, validation
  needs, confidence, and confirmation requirements from titles, labels,
  descriptions, acceptance criteria, comments, and attachments (#136).
- Portfolio/project workspace metadata supports nested projects, repo
  capabilities/components/owners/routing hints, branch and commit patterns,
  validation commands, and backwards-compatible flattening into existing
  `WorkspaceConfig.repos` consumers (#136).
- Portfolio-aware task routing in `sendsprint/routing.py` matches explicit
  repo/project/role/surface/capability rules, task-understanding signals,
  operational-memory routing facts, and single-repo fallbacks while surfacing
  high/medium/low confidence decisions (#136).
- Read-only route preview APIs at `/runs/preview` and `/api/runs/preview`
  expose task understanding, selected repositories, route confidence,
  validation commands, warnings, and recommended low-confidence actions before
  execution (#136).
- Web project setup UX for single-project versus portfolio mode, repository
  registration, branch/commit patterns, validation commands, local session
  persistence, run preparation, route previews, and Azure DevOps auth feedback
  (#136).
- Plugin installer profiles and templates for Windsurf, Kiro, and Antigravity
  extend SendSprint's AI-tool manifest coverage beyond the existing profiles
  (#136).
- Cross-stack runtime readiness closeout for epic #105 with ADR-009, a
  `sendsprint runtime-readiness` CLI command, and tests tying Python/Go/Rust/
  Node/Copilot boundaries to validation and rollback evidence.
- Deterministic read-only `/runs/{run_id}/status-answer` endpoint for
  Claude/Codex/Hermes status responses backed by existing run snapshots (#116).
- Resource-aware fan-out decision receipts with CPU idle/memory/capacity
  telemetry for safe `/goal`/Ralph worker sizing (#118).
- Runtime profiling baseline module and `sendsprint runtime-baseline` CLI for
  repeatable hot-path timing evidence (#119).
- Action catalog/playbook templates with built-in software PR delivery and
  marketing launch examples, plus `sendsprint actions ...` CLI commands (#124).
- Live dashboard API endpoints under `/api/dashboard/` with yool stats
  (cache hits/misses, retries, cost, duration per yool), agent provider
  status, validation lane status (dev, lint, test, security, pr), and
  tuple/run status with drill-down to individual yool and tuple detail.
  SSE stream endpoint at `GET /runs/{run_id}/events/stream` with typed
  event frames (hello, step, log, evidence, done, error) and 30 s
  keepalive for live dashboard updates. 16 tests in
  `tests/test_dashboard_api.py` (#103).

### Added

- Operator action endpoints at `/api/runs/{run_id}/actions/{action}` for
  pause, resume, cancel, rerun failed step, and approve publish, with
  autonomy-level gating, confirmation requirement for destructive actions
  (cancel), and control command relay integration (#104).
- Audit trail module `sendsprint/audit.py` with `AuditEntry` (frozen Pydantic
  model: operator, action, run_id, timestamp, result, detail) and `AuditLog`
  class (thread-safe append-only storage with query-by-run/operator/action
  and JSON export). Module-level singleton `audit_log` shared by API routes.
- Audit query endpoint `GET /api/runs/{run_id}/audit` returning recorded
  operator actions with timestamps (#104).
- 38 tests in `tests/test_operator_actions.py` covering all five action
  endpoints, autonomy blocking (observe/plan/execute/pr levels), confirmation
  gate for destructive cancel, state validation (409 on invalid transitions),
  audit recording and query, control command relay integration, and AuditEntry/
  AuditLog unit tests (#104).

- Node dashboard and Playwright lane boundary specifications in
  `sendsprint/dashboard_spec.py` (#109):
  `NodeDashboardSpec` (dashboard scope, consumed APIs, forbidden actions),
  `PlaywrightLaneSpec` (evidence capture isolation, flow, allowed/forbidden),
  `DashboardEventProtocol` (SSE event types, payload schemas, delivery
  guarantees), `SSEEventType` / `SSEEventPayload` (canonical event wire
  format), `NodeDashboardScope` and `PlaywrightEvidenceKind` enums.
  Node is UI-only — it consumes run/event APIs and never owns orchestration.
  Playwright evidence stays isolated from Python worker internals.
- Architecture doc `.specs/architecture/DASHBOARD.md` documenting Node
  dashboard scope (UI only, no orchestration), API consumption pattern,
  SSE event protocol, Playwright evidence isolation, and evidence flow (#109).
- 44 tests in `tests/test_dashboard_spec.py` covering SSE event type
  completeness, payload validation, protocol invariants, dashboard scope
  contracts, Playwright isolation rules, serialization roundtrips, and
  cross-spec consistency (#109).

- Durable per-run event store `sendsprint/event_store.py` with NDJSON-backed
  append-only log at `.sendsprint/runs/<run_id>/events.ndjson`, compact
  `RunSnapshotData` model persisted to `snapshot.json`, cursor-based replay
  (by sequence number or timestamp), `RetentionPolicy` model with configurable
  `max_events`/`max_age_days`/`compact_after_days`, compaction that rewrites
  the NDJSON file, automatic periodic snapshots, and disk-based cold-start
  recovery so events survive API restarts. Thread-safe for concurrent
  append and replay (#114).
- 41 tests in `tests/test_event_store.py` covering model validation,
  serialization roundtrips, append/seq tracking, NDJSON file content,
  path-traversal safety, restart-like reload with replay verification,
  cursor replay (by seq, by timestamp, precedence), snapshot lifecycle
  (empty/populated/write/load/auto-interval), compaction (age cutoff,
  max_events cap, NDJSON rewrite, seq update, noop, default policy),
  and concurrent thread safety (parallel appends, append+replay) (#114).

- Audited control-command queue module `sendsprint/command_queue.py` with
  `CommandStatus` enum (queued, accepted, rejected, applied, failed),
  `RunControlCommand` Pydantic model (command_id, command_type, run_id,
  params, issued_by, status, reason, created_at/accepted_at/applied_at/
  resolved_at timestamps), `CommandQueue` class (enqueue, poll, accept,
  apply, reject, fail, get, history), `COMMAND_AUTONOMY_REQUIREMENTS`
  mapping control actions to minimum autonomy levels, and four typed
  exceptions (CommandPolicyError, DuplicateCommandError,
  CommandNotFoundError, InvalidCommandTransition). Autonomy policy is
  enforced at enqueue time; workers poll at safe checkpoints without
  blocking status reads; command IDs provide idempotency protection (#115).
- 40 tests in `tests/test_command_queue.py` covering model validation,
  serialization, allowed/denied policy checks across autonomy levels,
  duplicate command rejection, full lifecycle transitions (queued ->
  accepted -> applied, queued -> rejected, accepted -> failed), invalid
  transition guards, poll filtering by run and status, history ordering,
  autonomy requirements mapping, default policy behavior, concurrent
  enqueue thread safety, and fake worker consumption simulation (#115).

- Non-code domain quality gates module `sendsprint/domain_quality.py` with
  `DomainCheckType` enum (checklist, review, source, risk),
  `DomainQualityCheck` model, `ChecklistItem`, `ReviewGateInput`,
  `SourceEvidence`, `RiskAssessment` input models, `ApprovalPolicy` model
  (required_approvals, auto_approve_threshold, escalation_path,
  require_explicit_approval_for_external), and `DomainQualityGate` class
  with `register_checks()`, `run_domain_checks()`, `evaluate()`, and
  individual gate runners for each check type. Produces `GateReport` verdicts
  compatible with existing `DeliveryQualityGate`. Missing evidence blocks
  readiness with actionable reasons; external-facing work requires explicit
  approval by default. Software quality gates unchanged (#123).
- 53 tests in `tests/test_domain_quality.py` covering model validation,
  serialization, all four gate types (checklist, review, source, risk),
  aggregate runner, verdict logic, approval policies, marketing-style
  end-to-end validation, software gate compatibility, and error message
  snapshots (#123).

- Worker runtime package `sendsprint/workers/` with Python fallback and
  optional Go accelerator for fan-out, watchdogs, and non-blocking
  execution (#107, epic #105):
  `PythonWorker` — always-available asyncio-based worker implementing the
  `WorkerCapability` contract with bounded queue, start/stop lifecycle,
  cancel, heartbeat, status snapshot, log tail, CPU nice, memory soft-limit,
  and fan-out concurrency cap.
  `GoWorkerSpec` — informational Pydantic model documenting the Go worker
  JSON protocol (NDJSON over stdio/localhost/named pipe) with request and
  response JSON schemas.
  `GoWorkerProxy` — subprocess wrapper that speaks the Go protocol when the
  `sendsprint-worker` binary is on PATH.
  `detect_go_worker()` — checks binary availability.
  `resolve_worker()` — returns `GoWorkerProxy` if available, else
  `PythonWorker` (Python fallback always works).
- 38 tests in `tests/test_workers.py` covering worker lifecycle,
  queue/complete, cancel (running/unknown/terminal), heartbeat, status
  (all/single/unknown), log tail, capability descriptor, task timeout,
  executor error, Go spec defaults/schema/frozen/roundtrip, detection
  mock, proxy capability/availability/send variants (ok/error/nonzero
  exit/invalid JSON), proxy queue/cancel, resolver fallback/preference/
  concurrency, and package public API imports (#107).

- Localhost web control plane API at `/api/runs` with enriched run listing
  (status, autonomy level, task, branch, readiness score), run detail with
  quality gate reports, evidence bundles, and logs (#102).
  New route module `sendsprint/api/routes/control_plane.py` with five endpoints:
  `GET /api/runs`, `POST /api/runs`, `GET /api/runs/{run_id}`,
  `GET /api/runs/{run_id}/evidence`, `GET /api/runs/{run_id}/quality`.
- CLI command `sendsprint web --port 5173` to start the web control plane
  locally via uvicorn (#102).
- 13 tests in `tests/test_api_control_plane.py` covering all control-plane
  endpoints, readiness score integration, 404 handling, and CLI command
  registration (#102).

- Optional Rust accelerator boundary `sendsprint/accelerators/` with Python
  fallback for hot-path operations: `fast_scan()`, `fast_diff()`,
  `fast_dedupe()`, `fast_receipt_hash()` (#108).
  - `python_impl.py` — pure-Python implementations, always available.
  - `rust_bridge.py` — `RustBridge` class wrapping `sendsprint-accel` CLI
    binary via subprocess; falls back to Python on missing binary, timeout,
    or parse error.
  - `resolver.py` — `resolve_accelerator()` picks the best backend at
    runtime; includes `benchmark()` helper comparing Python vs Rust timing.
  - `fast_receipt_hash` verified identical to `yool.receipts.sha256_canonical`.
- 40 tests in `tests/test_accelerators.py` covering all four hot paths,
  RustBridge fallback/mock scenarios, detection, resolver, and benchmark.

- Tri-agent status relay module `sendsprint/status_relay.py` with
  `RunEventEmitter` (thread-safe structured event emitter),
  `RunSnapshot` (read-only point-in-time run state model),
  `ControlCommand` (queued operator mutations: pause/resume/cancel/etc.),
  and `StatusRelay` orchestrator exposing `get_snapshot()`,
  `format_for_claude()` (Markdown), `format_for_codex()` (structured JSON),
  `format_for_hermes()` (concise plain text). All operations are thread-safe
  and non-blocking so the worker loop remains responsive under repeated
  status queries (#111).
- 34 tests in `tests/test_status_relay.py` covering event emission,
  snapshot CRUD, command queue, all three agent formatters (Claude Markdown,
  Codex JSON, Hermes concise), evidence truncation, thread safety, and
  concurrent read/write integration (#111).

- Deeper GitHub integration module `sendsprint/github_integration.py` with four
  classes for the full issue/PR/CI/review lifecycle (#100):
  `DuplicateDetector` (search for duplicate issues, PRs, and concurrent work),
  `ProgressReporter` (post progress comments with structured evidence summaries),
  `CIMonitor` (check combined CI status, poll until completion with timeout),
  `ReviewReader` (read reviews + inline comments, extract actionable feedback).
  All classes accept an injectable `httpx.Client` for zero-network testing.
- 31 tests in `tests/test_github_integration.py` covering all four classes,
  dataclass properties, URL construction, polling/timeout behavior, and
  actionable feedback extraction with mocked httpx transport.

- Cross-platform `sendsprint/platform.py` module with `PlatformInfo` model,
  `detect_platform()`, `is_windows()`, `is_unix()`, `normalize_path()`,
  `vendor_bin()`, `shell_command()`, and `venv_activate_cmd()` helpers for
  Windows/macOS/Linux compatibility. Includes `SENDSPRINT_FORCE_WIN` env var
  for testing Windows paths on Unix (#110).
- 18 tests in `tests/test_platform.py` covering detection, path normalization,
  vendor-bin resolution, shell-command wrapping (cmd/pwsh), and venv activation
  on both platforms (#110).
- Enhanced `.github/copilot-instructions.md` with SendSprint flow overview,
  quality gate docs, Windows PowerShell install path, cross-platform guidance,
  validation recipes for all stacks (Python/Node/Go/Rust) on Windows, and
  documentation that `/goal` and `/ralph-loop` are optional Codex/Claude-only
  accelerators (#110).

- Automatic rework loop module `sendsprint/rework.py` with `FailureClass` enum
  (correctable, environmental, human_required), `ReworkAttempt` model,
  `ReworkOutcome` enum, `ReworkResult` model, `ReworkLoop` class
  (run with max_retries/timeout_s limits), `classify_failure()` and `diagnose()`
  heuristics, and evidence bundle integration via `persist_to_bundle()`.
  Integrates with `DeliveryQualityGate` for validation and `BundleManager` for
  persisting attempt history (#95).
- 35 tests in `tests/test_rework.py` covering failure classification (lint,
  tests, coverage, diff-hygiene as correctable; timeout/connection-refused as
  environmental; security/unknown as human-required), diagnosis output, loop
  outcomes (fixed, max_retries_exceeded, timeout_exceeded, environmental_failure,
  human_required), evidence persistence and disk reloadability (#95).

- Pre-publish diff verifier module `sendsprint/diff_verifier.py` with
  `DiffVerdict` enum (pass, warn, block), `FindingType` / `FindingSeverity`
  enums, `DiffFinding` (frozen Pydantic model), `DiffReport`, and
  `DiffVerifier` class providing `verify(diff_text, plan)`,
  `check_unexpected_files()`, `check_large_changes()`,
  `check_missing_tests()`, and `check_generated_artifacts()`. Returns a
  structured verdict for `DeliveryQualityGate` consumption. Includes diff
  parsing helpers for file extraction and added-line counting (#99).
- 37 tests in `tests/test_diff_verifier.py` covering model validation,
  serialization, parsing helpers, all four check methods (unexpected files,
  large changes, missing tests, generated artifacts), full verify with plan
  matching, verdict precedence (block > warn > pass), empty diff, and summary
  formatting (#99).

- Delivery readiness score module `sendsprint/readiness_score.py` with
  `ScoreComponent` model (name, weight, raw_score 0-100, details),
  `ReadinessVerdict` enum (auto_publish, needs_human_approval, blocked),
  `DeliveryReadinessScore` calculator class (calculate, get_verdict,
  format_summary, evaluate), default six-component weights (quality_gate,
  diff_verifier, validations, evidence_completeness, ci_status, review_status),
  configurable thresholds (auto-publish >= 80, human approval >= 50, blocked
  below 50), and `build_default_components` factory helper. Calculation is
  deterministic: no randomness, no timestamps (#101).
- 34 tests in `tests/test_readiness_score.py` covering model validation,
  bounds enforcement, frozen immutability, weighted score math, determinism
  (100-iteration stability), all three verdict paths, custom thresholds,
  invalid threshold rejection, summary formatting, evaluate convenience
  method, factory helper, and default weights constant (#101).

- Marketing domain adapter in `sendsprint/actions/marketing_adapter.py` as the
  first non-code pilot for the generic action lifecycle (#120, #122):
  `MARKETING_DOMAIN` descriptor, `MarketingDomainAdapter` implementing
  `DomainAdapter`, and 7 action templates (`campaign_brief`, `landing_page_copy`,
  `email_sequence`, `social_posts`, `competitor_scan`, `content_calendar`,
  `launch_checklist`) with typed inputs, validation checklists (brand review,
  claims/risk review, link checks, UTM verification), and evidence requirements.
  External publishing disabled by default; requires explicit opt-in.
- 83 tests in `tests/test_marketing_actions.py` covering templates, adapter
  metadata, all lifecycle phases, publish opt-in/opt-out, rework, learning,
  full lifecycle integration, no-PR-assumption checks, and JSON serialization
  snapshots (#122).

- Central `DeliveryQualityGate` in `sendsprint/quality_gate.py` consolidating
  lint, tests, security, coverage, Playwright, and diff-hygiene checks into a
  single `pass` / `needs_rework` / `needs_human_approval` verdict before publish
  and closeout. Integrates with `AutonomyPolicy` for human-review gating and
  `BundleManager` for persisting decisions to evidence bundles (#93).
- 32 tests in `tests/test_quality_gate.py` covering all three verdict paths,
  individual check pass/fail, diff-hygiene scanning, evidence persistence, and
  bundle reloadability (#93).

- Verifiable planning phase module `sendsprint/plan_verifier.py` with
  `VerifiablePlan` Pydantic model (task_summary, target_files, expected_tests,
  risks, done_criteria, approved_by, approved_at), `PlanVerifier` class
  (create_plan, persist_to_evidence, persist_to_run_state, check_duplicate_work,
  requires_approval, approve, assert_approved), `DuplicateWorkError` and
  `PlanNotApprovedError` exceptions. Integrates with autonomy policy for
  approval gating at execute+ levels and with `BundleManager` for evidence
  persistence (#97).
- 31 tests in `tests/test_plan_verifier.py` covering model validation,
  serialization, plan creation, approval gating across autonomy levels,
  duplicate work detection, run state persistence, evidence persistence,
  and full lifecycle integration (#97).
- Stack-specific validation recipes in `sendsprint/validation_recipes.py`:
  `ValidationRecipe` Pydantic model, built-in recipes for Python (pytest, ruff),
  Go (go test, go vet), Rust (cargo test, cargo clippy), Node (npm test, npm
  run build, Playwright), and Copilot (instructions file reference) (#112).
- `RecipeSelector` auto-detects applicable recipes from a `TechFingerprint`,
  with de-duplication and copilot instructions file detection.
- `format_for_pr_body()` renders selected recipes as Markdown for PR body
  inclusion without leaking internal process details.
- Each recipe includes Windows-specific shell and toolchain notes.
- 31 tests in `tests/test_validation_recipes.py` covering model basics,
  built-in recipe constants, recipe selection by detected tech (including
  framework-to-stack mapping and de-duplication), copilot file detection,
  `from_path` factory, PR body snapshot tests, and internal process leak
  guard (#112).
- Control-plane contracts module `sendsprint/contracts.py` for the runtime
  split (#106, epic #105): `RunCommand` / `RunEvent` Pydantic wire models,
  `WorkerCapability` descriptor, `CommandType` / `EventType` / `WorkerStack`
  enums, `ControlPlaneContract` class documenting Python-owned APIs (CLI,
  API server, workspace loader, planning, quality gates, operational memory,
  PR publishing), and `to_json` / `from_json` serialization helpers with
  backwards-compatible defaults.
- 24 tests in `tests/test_contracts.py` covering serialization roundtrips,
  backwards compatibility with missing fields, extra-field preservation,
  enum completeness, and error cases (#106).

### Changed

- Delivery planning now routes through deterministic task understanding and
  confidence-gated route decisions, warning in plan-only mode and blocking
  low-confidence side effects when autonomy allows writes (#136).
- Release metadata now aligns `pyproject.toml`, `sendsprint.__version__`, and
  the English/Portuguese README status lines at `0.20.0` for GitHub release
  and PyPI publishing preparation (#136).

### Validation

- Focused coverage added for task understanding, deterministic routing,
  project/portfolio workspace flattening, plugin installation profiles,
  route preview API/control-plane endpoints, and dashboard Azure auth feedback
  (#136).

## [0.19.0] - 2026-05-20

### Added

- Yool runtime hardening module `sendsprint/yool/contracts.py` with Pydantic
  models: `YoolContract` (input/output schema + budget constraints),
  `BudgetEnforcer` (multi-dimension enforcement for tokens, cost, time, CPU,
  disk), `RetryPolicy` (selective retry by error type with exponential backoff),
  `InputCache` (hash-based in-memory cache with TTL and eviction),
  `InspectReport` (enriched inspect with cost, cache hits, retry info, budget
  remaining), `ContractRegistry` (in-memory contract lookup with validation),
  and `validate_payload` (minimal JSON-Schema validator) (#98).
- 50 tests in `tests/test_yool_hardening.py` covering contract validation,
  budget enforcement, retry selection, cache hit/miss/TTL/eviction, inspect
  report construction, and contract registry operations (#98).

## [0.18.0] - 2026-05-20

### Added

- Generic action lifecycle models in `sendsprint/actions/lifecycle.py`:
  `ActionPhase` enum (plan, execute, validate, evidence, publish, monitor,
  rework, learn), `Action`, `Objective`, `ExecutionStep`, `ValidationResult`,
  `EvidenceRecord`, `PublicationRecord`, `MonitorEntry`, `LearningRecord`,
  `ApprovalPolicy`, `DomainDescriptor` (#121).
- `DomainAdapter` abstract base class in `sendsprint/actions/adapter.py`
  defining the contract every domain adapter must implement (#121).
- `CodeDomainAdapter` in `sendsprint/actions/code_adapter.py` mapping the
  existing 10-step sprint-to-PR flow onto the generic lifecycle with full
  backwards compatibility (#121).
- 39 tests in `tests/test_action_lifecycle.py` covering schema serialization,
  backwards-compatible defaults, non-software domain support, adapter contract
  enforcement, and full lifecycle walkthrough (#121).

## [0.17.3] - 2026-05-20

### Added

- Autonomy level field on `RunState` and `RunReport` models, persisted in run
  state JSON and surfaced in the executive sprint summary (#94).
- `RunStateStore.load_or_create` accepts `autonomy_level` parameter, forwarded
  from `SprintFlow` autonomy policy.
- 29 tests in `tests/test_autonomy.py` covering policy allow/deny per level,
  `AutonomyDenied` raise, `side_effects` matrix, `parse_autonomy_level` edge
  cases, run state persistence, report serialization, and executive report
  rendering.

## [0.17.2] - 2026-05-20

### Added

- Active roadmap and dependency map at `.specs/architecture/ROADMAP.md` covering
  issues #92 through #124, grouped into P0/P1/P2 phases with Mermaid dependency
  graph (#113).
- `.specs/README.md` navigation index updated to reference ROADMAP.md.

## [0.17.1] - 2026-05-20

### Added

- First-class evidence bundles with `EvidenceItemType`, `EvidenceItem`,
  `EvidenceBundle`, and `BundleManager` classes for structured run evidence
  capture and persistence to `.sendsprint/evidence/<run_id>/` (#96).
- Evidence items support types: command, log, screenshot, coverage, risk,
  decision, with arbitrary metadata and timestamps.
- `BundleManager` provides create/add/finalize/export/summarize lifecycle,
  plus `load_bundle`, `list_bundles` queries.
- Bundle links to tuple, receipt, and yool IDs for catalog traceability.
- `summarize_for_pr` generates Markdown ready for PR body consumption.

## [0.17.0] - 2026-05-20

### Added

- Open-source contribution mode for SendSprint, including OSS candidate gates,
  duplicate-risk checks, validation/publish/monitor/rework plans, and compact
  learning records.
- Repository operational memory for OSS contribution learning, dedupe markers,
  monitor refs, and gate history.
- `.skills/open-source-contribution/SKILL.md` plus public PR, internal decision,
  and learning templates under `templates/opensource/`.

## [0.16.2] - 2026-05-19

### Added

- `## Shell token-smart (RTK CLI, optional)` section in AGENTS.md, CLAUDE.md
  and `.github/copilot-instructions.md` — agents prefer
  https://github.com/rtk-ai/rtk for `read|grep|find|git|pytest` when on PATH,
  no hard dependency.
- `.skills/rtk-cli/SKILL.md` skill manifest with steps, do-not list, trigger
  examples and DoD. Indexed in `.skills/README.md`.

### Notes

- Closes #90 (RTK CLI integration). #89 (vendor `docs/YOOL_TUPLE_HAMT.md`)
  is deferred — spec stays at the upstream repo; AGENTS.md links there.
  Re-evaluate when offline access becomes a blocker.

## [0.16.1] - 2026-05-19

### Added

- HAMT-backed agent capability catalog (`sendsprint/catalog.py`) wrapping the
  agent registry as yools per the yool/tuple/HAMT spec
  (https://github.com/wesleysimplicio/yool-tuple-hamt v0.2). 30-bit blake2b
  hash, branching factor 32, 6 levels, persisted as canonical JSON at
  `.catalog/hamt.json`.
- `sprint catalog build|list|find|show` CLI commands for inspecting and
  persisting the catalog.
- Every catalog entry carries the mandatory guardrails from spec §11
  (`cpu_quota_pct`, `disk_quota_mb`, `timeout_s`) — Victor Genaro's
  observation that the runtime needs a CPU guardrail and disk garbage
  collector is now structurally enforced at the catalog edge.
- AGENTS.md / CLAUDE.md document the yool/tuple/HAMT block, guardrails, and
  three-tier disk GC policy (hot/warm/cold, receipts immutable).
- Tests for catalog (`tests/test_catalog.py`, 10 cases: HAMT constants,
  hashing, build, lookup, guardrails, find, JSON roundtrip, overwrite, CLI
  build/list/show/find).

### Added (prior)

- `sendsprint watch` polling autopilot for assigned Jira/Azure DevOps tasks, with
  conservative default autonomy (`plan`), dry-run listing, local watch-state
  deduplication, evidence/report writing, and workspace `watch` configuration.
- expose agent-grade sprint run status
- finish autonomy tracker foundations
- rollback and safe-exit plan generator (closes #58)
- add agent registry foundations

### Docs

- reposition SendSprint as a personal utility (closes #64)
- add C4 architecture maps
- changelog: promote 0.14.0

### CI

- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- add PyPI token fallback

## [0.14.0] - 2026-05-18
### Added

- add sprint autopilot foundation

### Fixed

- types: satisfy sprint flow mypy checks

### Docs

- ingest: add transcript task extraction
- templates: require frontend stack recipes
- roadmap: link sprint autopilot issues
- roadmap: define sprint autopilot backlog
- changelog: promote 0.13.0

### CI

- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- node: fix root lockfile setup
- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- release: refresh coverage badge and changelog
- publish: use PyPI token secret

## [0.13.0] - 2026-05-18

### Added

- `WorkspaceConfig.code_generation` and `WorkspaceConfig.deploy` for opt-in LLM code generation and deploy callbacks.
- CLI overrides `--llm-codegen`, `--llm-provider`, `--llm-model`, `--llm-max-usd`, `--llm-max-tokens`, `--deploy`, `--deploy-url`, and `--deploy-final-status`.
- Jira and Azure DevOps `update_status(...)` callbacks for deploy-trigger ticket synchronization.
- ADR-006 and ADR-007 covering codegen budgeting/provider policy and deploy idempotency semantics.
- Flow and CLI orchestration tests for codegen/deploy integration.

### Changed

- `SprintFlow` now runs optional code generation after build and optional deploy callbacks after PR creation.
- `README.md`, `README.pt-BR.md`, `examples/workspace.yaml`, and `.specs/architecture/DESIGN.md` now document the shipped codegen/deploy hooks.
- `docs/validation/ralph-llm-project-mapper.md` now records the concrete external-pilot blocker evidence used to close Sprint 1 validation honestly.
- Source distribution packaging now excludes heavy local artifacts and generated media so the `0.13.0` release builds a publishable PyPI sdist and wheel.
- Bumped package metadata to `0.13.0` for the Sprint 2 epic closeout.

### CI

- PyPI publishing now uses the repository `PYPI_API_TOKEN` secret after trusted publishing rejected the `v0.13.0` release claims.

## [0.12.2] - 2026-05-18

### Added

- `scripts/generate_coverage_badge.py` to render a local SVG coverage badge from `coverage.xml`.
- `.github/workflows/release-hygiene.yml` to refresh `docs/assets/coverage-badge.svg` on `main` and promote `CHANGELOG.md` entries on `v*.*.*` tag pushes.
- `tests/test_coverage_badge.py` plus new `tests/test_build_changelog.py` coverage for `[Unreleased]` write-back automation.

### Changed

- `README.md` now embeds the generated coverage badge at the top and documents release hygiene as part of the shipped status line.
- `scripts/build_changelog.py` can now rewrite the `[Unreleased]` block in place before promoting tagged releases.
- Bumped package metadata to `0.12.2` for the Sprint 4 release-hygiene automation pass.

## [0.12.1] - 2026-05-18

### Changed

- Synchronized `.specs/sprints/BACKLOG.md` and `.specs/sprints/sprint-1/SPRINT.md` with the work already delivered on `main`, marking Sprint 1 pipeline adoption as done and keeping the Ralph validation item explicit as the remaining open sprint-1 task.
- Marked `.specs/sprints/sprint-1/01-add-bun-detector.task.md` and `.specs/sprints/sprint-1/02-add-cargo-audit-tests.task.md` as `done` so the task specs match the GitHub issue state for #4, #5, and #6.
- Bumped package metadata to `0.12.1` after the roadmap/documentation synchronization pass.

## [0.12.0] - 2026-05-18

### Added

- **Bun runtime detection** (`bun.lockb` or `bunfig.toml`) in `sendsprint/tech/detector.py`. Coexistence with `package.json` keeps Bun as the primary runtime; frameworks (React/Vue/etc.) layered on top are still detected.
- **Deno runtime detection** via `deno.json`, `deno.jsonc`, or `deno.lock`.
- Bun + Deno install/build/lint/test commands in `agents/dev.py`, `agents/lint_runner.py`, `agents/test_runner.py` (`bun install`, `bun run build`, `bun x eslint .`, `bun test`, `deno cache .`, `deno task build`, `deno lint`, `deno test --quiet`).
- `DevAgent.install_and_build()` orchestrator; skips Bun build when no `scripts.build` is declared in `package.json`.
- Missing Bun/Deno binaries now produce `StepReport.status="skipped"` with `message="<tool> not installed"` (mock-fallback contract from `AGENTS.md` §5), rather than `failed`.
- `SecurityReviewer.tool_results` diagnostic surface — per-tool `{status, findings, truncated, reason, error}` populated for `cargo-audit` and `pip-audit`, summarized in `StepReport.message`.
- `cargo-audit` findings now carry the advisory id (e.g. `RUSTSEC-2024-0001`) and the upstream severity when available.
- `tests/fixtures/cargo-audit-output.json` and `tests/fixtures/pip-audit-output.json` for deterministic security parser tests.
- `tests/test_security_reviewer.py` (15 new tests) and `tests/test_tech_detector.py` / `tests/test_agents.py` Bun + Deno coverage (21 new tests). Total: 198 passing.

### Changed

- `detect_tech` no longer adds the generic `node` tech when a Bun or Deno runtime is detected (more-specific runtime wins).

## [0.11.0] - 2026-05-15

### Added

- Added `required_pr_reviewers` at workspace and repo level so Azure DevOps PRs can enforce mandatory reviewers with `isRequired: true`.
- Documented delivery rules for dirty checkout isolation, validated-only repos, required reviewers, linked work items, auth-blocked visual evidence, and unrelated regression failures.

## [0.10.3] - 2026-05-15

### Changed

- Refreshed README visuals to present SendSprint as a sprint-to-PR delivery platform.
- Updated README, package metadata, and video documentation to use product/platform language and the current 10-step flow.
- Regenerated before/after Remotion MP4s, posters, and bilingual presentation exports with the new product visuals.

## [0.10.2] - 2026-05-15

### Added

- Generated Remotion music bed and workflow sound effects for explainer, before/after, and run-loop MP4s.
- Re-rendered all preview MP4s with audio tracks and documented the audio build flow.

## [0.10.1] - 2026-05-15

### Added

- Bilingual SendSprint implementation presentation decks in PPTX and PDF formats, with generated PNG previews and contact sheets.
- README links for the English and Portuguese implementation decks.

## [0.10.0] - 2026-05-15

### Added

- GPT-image-generated productivity visuals comparing teams before and after adopting SendSprint.
- Remotion before/after explainer video in English and Portuguese, with pain, empathy, solution, outcome, and CTA scenes.
- Render scripts for before/after MP4s and posters.

## [0.9.0] - 2026-05-15

### Added

- `sendsprint preflight` command to validate transport, credentials, repository health, sprint reads, planning, and Azure work-item link safety before delivery.
- `--dry-run` for `run` and `sprint`, producing a delivery plan with item, repo, branch, target branch, confidence, and routing reason without writing files or opening PRs.
- Resumable run state under `.sendsprint/runs/<run-id>.json`, with `--run-id` and `--resume/--no-resume` to avoid duplicate delivery on retries.
- Post-PR validation step to ensure PR metadata is usable before marking a delivery complete.
- Confidence-based routing helpers that infer front/back scope from item text when explicit `scope:*` labels are missing.
- Web API run requests now accept `dry_run`, `resume`, and `run_id`.

## [0.8.2] - 2026-05-15

### Added

- Bundled Jira/Azure DevOps core guide for stable agent rules, transport choices, hierarchy safety, generated task behavior, and official vendor documentation links.

## [0.8.1] - 2026-05-15

### Fixed

- Azure DevOps sprint planning now normalizes invalid backlog hierarchy links, converting Task/Subtask parents that point to non-delivery backlog types such as Issue into Related links before delivery planning.

## [0.8.0] - 2026-05-15

### Added

- Azure DevOps MCP installer command: `sendsprint install-ado-mcp`. It configures Codex to run the official `@azure-devops/mcp` server through `npx -y`.
- User Story decomposition: stories without child tasks are expanded into generated front/back tasks with `parent_key` and `scope:front` / `scope:back` labels.

### Changed

- Branch generation now defaults to `feature/{number}-{title}`, producing names like `feature/179500-email-cnpj-filter`.
- Added configurable `branch_name_template` at workspace and repo level. Supported placeholders: `{number}`, `{key}`, `{id}`, `{title}`, `{repo}`.
- Sprint delivery skips parent stories that have task children and routes generated tasks only to matching front/back repos.

## [0.7.1] - 2026-05-14

### Changed

- Codex CLI config: switch default model to `gpt-5.4` via top-level `model` key (replaces deprecated `[model]` table).

## [0.7.0] - 2026-05-14

### Added

- `sendsprint sync-agentic-starter` command to sync the latest `agentic-starter` scaffold from a local path, GitHub URL, or `owner/repo`. Existing files are preserved unless `--force` is used, and `.agentic-starter.json` records the synced source/ref.
- `sendsprint init` now performs a best-effort `agentic-starter` sync by default after generating `.specs/`; use `--no-sync-agentic-starter` to disable network sync.
- GitHub Actions workflow to sync `agentic-starter` on a schedule and open a PR with any scaffold changes.
- GitHub Actions workflow to build and publish the Python package to PyPI from release tags using trusted publishing.
- Tests for scaffold sync copy, skip, force, dry-run, and missing-path behavior.

### Changed

- Workspace PR target defaults to `develop` while remaining configurable through `default_base_branch` or per-repo `pr_target_branch`.
- `ArchitectureMapper` treats `.agentic-starter.json` as an `agentic-starter` marker.

## [0.6.0] - 2026-05-12

### Added

- **Agentic-starter detection** — `ArchitectureMapper` now checks for `AGENTS.md`, `.specs/architecture/DESIGN.md`, `.specs/product/VISION.md` markers. When found, `ArchitectureReport.has_agentic_starter=True` and `is_mapped` short-circuits true; SprintFlow skips re-generation and reuses existing specs.
- **Status whitelist** — `ScopeConfig.allowed_statuses` filters items by case-insensitive status. Defaults to developable set: `new, active, to do, todo, open, in progress, doing, selected for development, backlog, ready`. Empty list = pass-through.
- **Task-code selector** — `ScopeConfig.task_keys` (CLI: `--task PROJ-42 --task PROJ-7` or `--tasks PROJ-1,PROJ-2`) bypasses both mode and status filters; matches by `key` or `id`, case-insensitive.
- **Branch-per-task delivery** — `SprintFlow.run()` now iterates `(item, repo)` pairs, generating one branch + worktree + commit + PR per task via `_branch_for_task(item, fp) -> sendsprint/<slug-key>-<slug-title>`. Commit message: `feat({key}): {title} [SendSprint {sprint}]`; PR title: `[{key}] {title} — {repo}`.
- **Interactive picker** — `sendsprint sprint --pick` prompts `[a]ll / [m]ine / [c]ode` (chat-trigger UX); on `c` collects comma-separated task codes.
- Tests: `tests/test_sprint_flow.py` (branch naming, 4 tests), `tests/test_scope.py` extended (status filter, task_keys precedence, build_scope defaults — 8 new tests), `tests/test_architecture_mapper.py` extended (agentic-starter detection — 3 new tests). Suite: 145 passing.

### Changed

- `apply_scope` precedence is now explicit: (1) `task_keys` override mode + status, (2) `mode='mine'` filters by assignee then status whitelist, (3) `mode='all'` applies status whitelist only. Always returns a new `Sprint` (Pydantic `model_copy`).
- `build_scope(...)` accepts `allowed_statuses` and `task_keys` kwargs; trims and drops empties.
- `SprintFlow._step8_commit` and `_step9_create_pr` accept an `item: SprintItem | None` kwarg, formatting per-task commit and PR titles when supplied.
- `SprintFlow.run()` adds an empty-sprint guard: if scope/status filter leaves zero items, steps 2–10 are skipped with a `no-tasks` StepReport entry.

## [0.5.0] - 2026-05-12

### Added

- `sendsprint/agents/sprint_importer.py` — materializes sprint items as agentic-starter task specs under `.specs/sprints/sprint-<id>/<key>.task.md` with YAML frontmatter (id, title, sprint, owner, status, source, type, parent, labels, imported_at), plus `SPRINT.md` index. Idempotent: preserves user edits.
- `sendsprint/agents/pr_body_builder.py` — composes rich PR markdown body with sprint context, items block, step-report table, evidence list (✓/✗ per `TestEvidence`), security findings (severity + file:line), and DoD checklist linking to imported spec.
- `SprintFlow` runs **Step 1.5** (import sprint specs) right after scope filter, and uses `PrBodyBuilder` for Step 9 PR body.
- `RunReport.summary` appends a `RALPH_STATUS` block (`STATUS`, `TASKS_COMPLETED_THIS_LOOP`, `FILES_MODIFIED`, `TESTS_STATUS`, `EXIT_SIGNAL`, `RECOMMENDATION`) for Ralph-loop exit-gate detection.
- `tests/test_sprint_importer.py` (7 tests) + `tests/test_pr_body_builder.py` (6 tests). Total suite: 130 passing.
- Agentic-starter scaffold imported non-clobber: `.agents/`, `.codex/`, `.skills/` (caveman, ralph-loop, conventional-commits, everything-claude-code), `.claude/hooks/`, `.github/workflows/scaffold-self-check.yml`, ADR-template, PERSONAS, RELEASE, task-template.
- `skills/claude/SKILL.md` v0.3.0 — documents multi-agent dispatch table (parallel `everything-claude-code` reviewers/resolvers per stack) and Ralph exit gate.

### Changed

- SKILL.md step numbering updated to include SprintImporter at Step 2 (downstream steps shifted by +1 in docs only — code `step=N` markers in `StepReport` unchanged).

## [0.4.1] - 2026-05-07

### Added

- `sendsprint init --offline` flag — writes deterministic templates (facts block + `_TODO:_` placeholders) without an LLM call. Useful for CI, demos, and code review.
- Rich `Status` spinner during `init`: `scanning repo...` while signals are gathered, then `asking LLM: vision.md / domain.md / design.md / patterns.md` (or `templating: …` in offline mode) so the user sees per-spec progress.
- `Scaffolder.generate(..., on_step=callback)` — invoked before each spec is generated; CLI uses it to update the spinner. Same callback fires in offline and LLM paths.
- `tests/test_scaffolder.py` — 14 tests covering `discover`, offline + LLM `generate` paths, `write` (create/skip/force), `run` end-to-end, and module-level helpers (`_offline_body`, `_build_prompt`, `_add_header`, section constants).

### Fixed

- `Scaffolder.discover()` now reads `TechFingerprint.techs` instead of the non-existent `languages` attribute, so `signals.primary_languages` is correctly populated and shows up in the CLI summary line.

## [0.4.0] - 2026-05-07

### Added

- `sendsprint/credentials.py` — OS keyring wrapper (Keychain on macOS, Secret Service on Linux, Credential Manager on Windows). One-time prompt then persistent.
- `sendsprint/profile.py` — non-secret prefs at `~/.config/sendsprint/profile.yaml` (chmod 600). Stores org/project/default sprint/scope, jira.base_url + jira.email, azuredevops.organization + project + team. Pydantic v2 model with dotted-key updates.
- `sendsprint/scaffolder.py` — auto-discovery on first run: scans repo with `tech_detector`, LLM-fills `.specs/product/{VISION,DOMAIN}.md` and `.specs/architecture/{DESIGN,PATTERNS}.md` (each marked `> auto-generated, review me`).
- CLI commands: `init` (scaffolder), `login <provider>` (prompts + persists creds), `logout <provider>` (deletes keyring entry), `sprint` (zero-arg chat-trigger entrypoint that loads profile + keyring + runs full 10-step flow with `--scope mine` default).
- IDE manifests for **8 additional editors** so the chat-trigger UX works across the market: `skills/cursor/sendsprint.mdc`, `skills/windsurf/sendsprint.md`, `skills/kiro/sendsprint.md`, `skills/zed/sendsprint.md`, `skills/cline/.clinerules`, `skills/continue/config.json`, `skills/aider/CONVENTIONS.md`, `skills/cody/sendsprint.md`. All recognise the same trigger phrases (pt-BR / en / es / `/sendsprint`).
- Trigger phrases (any IDE): `rode o sendsprint`, `executar sprint`, `Faça todas as minhas tarefas da sprint`, `entregar sprint`, `run sendsprint`, `ship my sprint`, `deliver my sprint`, `process my Jira sprint`, `process my ADO sprint`, `ejecutar sprint`, `procesar sprint`, `/sendsprint`.

### Changed

- `JiraOperator.__init__` and `AzureDevopsOperator.__init__` now resolve credentials in this order: constructor arg → env var → profile YAML → OS keyring. Lazy imports keep `keyring`/`yaml` optional at import time.
- AGENTS.md §3/§4/§10 updated with new modules, chat-trigger UX section, and IDE manifest map.

### Dependencies

- `keyring>=25.0.0` added to `pyproject.toml` and `requirements.txt` (was implicit before).

## [0.3.0] - 2026-05-07

### Added

- `.specs/product/` — `VISION.md` (north star, non-goals, success metrics) and `DOMAIN.md` (vocabulary, invariants, lifecycles).
- `.specs/architecture/` — `DESIGN.md` (bird's-eye + layers + data flow + concurrency + failure model + extension points), `PATTERNS.md` (file headers, Pydantic v2, subprocess, httpx, pathlib, exceptions, typing — with DON'Ts table).
- `.specs/architecture/ADR-001-stack.md` — Python 3.11+ + Pydantic v2 + Typer + Rich + httpx + playwright + pyyaml.
- `.specs/architecture/ADR-002-multi-transport.md` — fixed `TRANSPORT_ORDER = ("mcp", "api", "playwright")`.
- `.specs/architecture/ADR-003-mock-fallback.md` — three-tier test strategy: unit / integration (VCR) / canary.
- `.specs/architecture/ADR-004-worktree-isolation.md` — `WorktreeManager` per-branch isolation pattern.
- `.specs/architecture/ADR-005-flag-only-security.md` — `SecurityReviewer` halts run on findings, never auto-fixes.
- `.specs/workflow/WORKFLOW.md` — daily loop, Conventional Commits, test discipline, lint+format, branch naming, release process.
- `.specs/workflow/CONTRIBUTING.md` — what reviewers expect, PR requirements, code review SLA, ADR/skill manifest contribution flow.
- `.claude/hooks/post-edit.sh` — PostToolUse hook auto-formats `.py` files via `ruff format` + lint check.
- `.claude/hooks/pre-commit.sh` — PreToolUse hook blocks `git commit` on `ruff check` or unit-tier `pytest` failure.
- `templates/task-template.md` — task spec scaffold (Goal/Why/Scope/Acceptance/Plan/Files/Risks/ADRs/Effort/Owner).
- `templates/ADR-template.md` — ADR scaffold (Status/Date/Deciders/Supersedes/Context/Decision/Consequences/Alternatives/Implementation notes/See also).

### Changed

- Repo structure now AI-friendly per the canonical layout: `.specs/` (product/architecture/workflow), `.claude/hooks/`, `templates/`, `skills/` (5 platforms), root master files (`AGENTS.md`, `CHANGELOG.md`, `README.md`).

## [0.2.2] - 2026-05-07

### Fixed

- Step numbers corrected across all agents to match 10-step flow (TestRunner→5, SecurityReviewer→6, LintRunner→4, PrCreator→9, PrReviewer→10).
- Added `git push --force-with-lease` before PR creation — previously commit existed only locally, causing PR creation to fail.

### Added

- PrReviewer expanded: merge conflict markers, `debugger`, `binding.pry`, `import pdb`, `breakpoint()`, `System.out.println`, `dd()`, `dump()` detection.
- SecurityReviewer: 5 new secret patterns (Slack webhook, JWT, Slack token, MongoDB/Postgres connection strings).
- SecurityReviewer: `pip-audit` integration for Python dependency vulnerabilities.
- SecurityReviewer: `cargo-audit` integration for Rust dependency vulnerabilities.
- 6 new tests (103 total): merge conflict detection, debugger/pdb/logger patterns, Slack webhook, JWT detection.

## [0.2.1] - 2026-05-07

### Added

- Step 4: `LintRunner` with lint commands for 19 tech stacks (eslint, ruff, clippy, golangci-lint, phpcs, rubocop, dart analyze, dotnet format, checkstyle).
- Step 8: Commit step — `git add -A && git commit` on worktree branch before PR creation. Skips if no changes.
- Empty-repos guard: explicit "no-repos" step report when no repos resolved.
- `SprintFlowResult.to_json()` for structured JSON output.

### Changed

- Flow expanded from 9 to 10 steps (lint + commit inserted, PR review merged with delivered).
- Fix loop (step 7) now re-runs lint in addition to tests/security, and reports which checks triggered retry.
- All 5 skill manifests updated to reflect 10-step flow.

## [0.2.0] - 2026-05-07

### Added

- Full 9-step sprint delivery flow: read sprint, architecture mapping, dev, tests, security review, fix loop, create PR, PR review, delivered.
- `DevAgent` with install + build commands for 16 package managers and 11 build tools.
- `TestRunner` with unit test + Playwright E2E commands for 19 tech stacks, screenshot evidence capture.
- `SecurityReviewer` flag-only scanner: 7 secret regex patterns, `.env` gitignore check, `npm audit` integration.
- `PrCreator` supporting GitHub (gh CLI) and Azure DevOps (REST API) PR creation with reviewers.
- `PrReviewer` diff static analysis: TODO/FIXME markers, debug statements, long lines (>200 chars).
- `WorktreeManager` for git worktree isolation enabling parallel agent branches.
- `TechFingerprint` / `detect_tech()` filesystem marker detection for 25+ technologies.
- `ArchitectureBuildResult` / `build_architecture()` auto-generates baseline docs (README, ARCHITECTURE.md, ADRs, dependencies, deploy) when score < 0.6.
- Multi-repo workspace support via `workspace.yaml` / `workspace.json` (`WorkspaceConfig`, `RepoConfig`).
- `--scope mine` current-user filtering: matches by account_id, email, descriptor, or display_name.
- Current-user resolution: Jira via `/rest/api/3/myself`, Azure DevOps via `/_apis/connectionData`.
- Pydantic v2 report models: `StepReport`, `RunReport`, `TestEvidence`, `SecurityFinding`, `PrInfo`.
- CLI commands: `detect-tech`, `check-architecture --build`, `run` with `--workspace`, `--scope`, `--repo`, `-o`.
- `examples/workspace.yaml` multi-repo workspace example.
- `.github/workflows/sendsprint.yml` CI: Python 3.11/3.12 matrix, ruff, mypy, pytest.
- 94 tests covering operators, architecture, tech detector, scope, workspace, and all agents.

### Changed

- `SprintFlow` rewritten for 9-step orchestration (was 2-step).
- `cli.py` rewritten with Typer subcommands and Rich output.
- `SprintItem` extended with `assignee_email`, `assignee_account_id`, `assignee_descriptor` fields.
- All 5 skill manifests updated to reflect v0.2 9-step flow.

## [0.1.0] - 2026-05-07

### Added

- Initial scaffold: Python package, CLI (`sendsprint`), pyproject, requirements, MIT license.
- `BaseOperator` abstract class with `transport` resolver (mcp / api / playwright / auto).
- `JiraOperator` reads Stories, Tasks, Subtasks, Bugs, Epics, Features, Issues from a sprint via API or Playwright fallback.
- `AzureDevopsOperator` reads Work Items (Story/Task/Bug/Feature/Epic) from an iteration path via API or Playwright fallback.
- `ArchitectureMapper` verifies presence of `ARCHITECTURE.md`, `docs/architecture/*`, `C4`, ADRs, dependency graph, deploy topology in target repos.
- Pydantic models: `Sprint`, `SprintItem`, `Link`, `Comment`, `Attachment`, `ArchitectureReport`.
- Provider-agnostic `LlmClient` (Anthropic / OpenAI / Google / Groq / Ollama).
- `SprintFlow` orchestrator wiring Step 1 (read) -> Step 2 (architecture check).
- Multi-platform skill manifests under `skills/` for Claude, Codex, Hermes, Openclaw, GitHub Copilot.
- Pytest scaffolding with operator unit tests using monkeypatched HTTP layer.
