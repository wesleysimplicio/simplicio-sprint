# SendSprint Project Map

This map is the implementation entry point before working GitHub issues. It
summarizes where each feature should land and which tests usually guard it.

## Repository Mode

- Mode: single project at repo root by default, with portfolio/project workspace
  metadata available through `workspace.yaml`.
- Product package: `sendsprint/`.
- API package: `sendsprint/api/`.
- Dashboard app: `web/`.
- Video/demo assets: `video/`.
- Product contract: `.specs/`, `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`.
- C4 maps: `docs/c4/system-context.md`, `docs/c4/containers.md`,
  `docs/c4/components.md`.

## Feature Entry Points

| Need | Primary files | Tests |
|---|---|---|
| Add CLI command | `sendsprint/cli.py` | `tests/test_cli.py` |
| Add tracker/source | `sendsprint/operators/`, `sendsprint/models/sprint.py` | `tests/test_*operator.py` |
| Add task understanding | `sendsprint/task_understanding.py` | `tests/test_task_understanding.py` |
| Add routing or portfolio behavior | `sendsprint/routing.py`, `sendsprint/planning.py`, `sendsprint/models/workspace.py`, `sendsprint/workspace/loader.py` | `tests/test_routing.py`, `tests/test_workspace.py`, `tests/test_sprint_flow.py` |
| Add planning/dry-run behavior | `sendsprint/planning.py`, `sendsprint/flow/sprint_flow.py` | `tests/test_sprint_flow.py` |
| Add route preview API | `sendsprint/api/schemas.py`, `sendsprint/api/routes/runs.py`, `sendsprint/api/routes/control_plane.py` | `tests/test_api.py`, `tests/test_api_control_plane.py` |
| Add stack support | `sendsprint/tech/detector.py`, `agents/dev.py`, `lint_runner.py`, `test_runner.py` | `tests/test_tech_detector.py`, `tests/test_agents.py` |
| Add safety/preflight check | `sendsprint/preflight.py` | `tests/test_preflight.py` |
| Add evidence/report behavior | `sendsprint/models/reports.py`, `agents/pr_body_builder.py`, API run bridge | `tests/test_pr_body_builder.py`, `tests/test_api.py` |
| Add dashboard or Web setup data | `sendsprint/api/schemas.py`, `sendsprint/api/routes/`, `web/src/`, `web/src/components/setup/` | `tests/test_api.py`, `tests/e2e/dashboard.smoke.spec.ts` |
| Add tuple/DAG execution behavior | `sendsprint/yool/`, `sendsprint/flow/sprint_flow.py`, `sendsprint/agent_registry.py` | `tests/test_yool_runtime.py`, `tests/test_yool_receipts_dispatcher.py`, `tests/test_sprint_flow.py` |
| Add release automation | `.github/workflows/`, `scripts/` | workflow syntax + focused script tests |

## Data Model Map

- `Sprint` and `SprintItem` represent tracker work from Jira/Azure DevOps.
- `WorkspaceConfig`, `PortfolioConfig`, `ProjectConfig`, and `RepoConfig`
  describe target repositories, project grouping, branches, reviewers, codegen,
  deploy, routing metadata, and stack commands. Project-owned repos are
  flattened into `WorkspaceConfig.repos` for existing flow consumers.
- `TaskUnderstandingReport` is the deterministic per-item normalization used
  before routing.
- `RouteDecision` records item/repo match status, confidence, reason, and route
  signals.
- `DeliveryPlan` is the shared CLI dry-run and API route-preview artifact.
- `RoutePreviewResponse` is the read-only Web/control-plane projection of a
  `DeliveryPlan`.
- Tuple logs and receipts represent the mutable execution DAG after route
  preview/plan approval.
- `RunState` persists resumable progress under `.sendsprint/runs/`.
- `RunReport`, `StepReport`, `TestEvidence`, `SecurityFinding`, and `PrInfo`
  are the common reporting surface for CLI, API, dashboard, PRs, and evidence.

## Issue Implementation Map

| Issue | Recommended implementation surface |
|---|---|
| `#27` PyPI trusted publishing | `.github/workflows/pypi-publish.yml`, `.specs/workflow/RELEASE.md`, release docs |
| `#28` doctor | New readiness module plus `sendsprint doctor` in `cli.py` |
| `#29` dry-run plan | Extend `DeliveryPlan` and `SprintFlow.run(dry_run=True)` artifact output |
| `#30` per-task worktree | Harden `agents/worktree.py`, flow state, report metadata |
| `#31` evidence bundle | New evidence bundler fed by `RunReport`, logs, traces, PR/issue metadata |
| `#32` GitHub Issues tracker | New GitHub issue tracker boundary using `gh` safely and mockable tests |
| `#33` autonomy policy | New central policy model checked before side effects |
| `#34` Ralph/Goal loop | New loop contract model and report integration |
| `#35` stack templates | New validation template catalog used by doctor and dry-run |
| `#36` dashboard | API schema/route fed by run report/evidence bundle, then web rendering |
| `#37` demo | Repeatable fixture/docs under `docs/demo/` or `examples/` |
| `#38` executive report | Markdown report generator from run report/evidence bundle |
| `#39` control plane | Worker assignment/status model tied to worktree ownership and policy |
| `#40` transcript ingest | Parser/deduper/redactor plus review/apply modes behind policy |
| `#135` task understanding/routing docs | `README.md`, `SENDSPRINT_FLOW_MAP.md`, `docs/architecture/overview.md`, `docs/PLUGIN_ADAPTERS.md` |

## Regression Strategy

- Prefer unit tests around new pure modules first.
- Add CLI tests for each new command/option.
- Add `SprintFlow` tests when behavior changes orchestration or reporting.
- Add API tests before dashboard UI changes.
- Run focused tests first, then full `pytest`, `ruff`, `mypy`, root `npm` checks,
  and `taskflow run`.
