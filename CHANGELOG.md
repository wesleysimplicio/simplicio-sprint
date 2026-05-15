# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

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
