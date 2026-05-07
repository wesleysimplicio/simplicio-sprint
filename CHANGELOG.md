# Changelog

All notable changes to this project will be documented in this file.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/).

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
