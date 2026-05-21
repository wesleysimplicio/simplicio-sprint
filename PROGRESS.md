# Progress Log

## Current Status

In progress. After `git pull --ff-only` on `main`, a large upstream yool/tuple/HAMT batch landed. This round closed 10 GitHub issues with implementation + tests (`#77`, `#78`, `#79`, `#80`, `#81`, `#82`, `#83`, `#85`, `#86`, `#87`). Remaining open issues are `#76` (epic), `#84` (full worker-port of legacy agents), and `#88` (remove the legacy linear `SprintFlow.run()` pipeline).

## Checkpoints

### Checkpoint 1

Status: completed

Task: Pull latest `main` before touching the repo and re-check the live issue state.

Result: `git pull --ff-only` advanced the checkout from `260cfb8` to `11f914a`, bringing the first upstream yool/tuple/HAMT implementation wave (`catalog`, `watch`, `yool/*`, tests, docs).

Validation: `git pull --ff-only`; `gh issue list --state open`; `gh pr list --state open`.

Next: Audit the delta against the still-open issues with 5 parallel agents.

### Checkpoint 2

Status: completed

Task: Use 5 parallel agents to triage the remaining gaps by issue group.

Result: Agents split across catalog/CLI, receipts/cache, tuple-log/resume, bus/workers, and MCP/dispatch/budgets. The returned audits showed that upstream already solved large parts of the backlog but still lacked: spec-shaped sprint catalog surface, inspect/resume CLI, shared CLI+MCP dispatch path, budget rollup surface, and a few runtime correctness tests.

Validation: 5 subagents executed in parallel and returned scoped findings; local repo inspection cross-checked each slice.

Next: Land the missing runtime surfaces and close the issues that become objectively satisfied.

### Checkpoint 3

Status: completed

Task: Implement the missing yool runtime surfaces and strengthen the correctness tests.

Result: Added shared helpers in `sendsprint/yool/runtime.py`; converted `sprint` into a namespace with `catalog`, `dispatch`, `inspect`, `resume`, and `snapshot` surfaces; wired MCP `snapshot`/`dispatch`/`inspect`; hardened `TupleBus` drain/close semantics; strengthened `ReceiptStore` latest-success indexing; committed `.catalog/agents.json`; and added focused tests for catalog drift/collision, CLI/MCP parity, tuple runtime, cache, resume, and budget overrun.

Validation: focused `pytest` slices on `test_catalog.py`, `test_cli.py`, `test_mcp_server.py`, `test_yool_runtime.py`, `test_yool_receipts_dispatcher.py`, `test_build_agent_catalog_script.py`; `python -m ruff check sendsprint tests`.

Next: Run the full suites, close the validated GitHub issues, and publish this progress snapshot.

### Checkpoint 4

Status: completed

Task: Re-run the full validation matrix and close the issues whose DoD is now covered by code + tests.

Result: Python test suite, Ruff, web typecheck, Playwright smoke command, and catalog drift check all passed. Closed issues `#77`, `#78`, `#79`, `#80`, `#81`, `#82`, `#83`, `#85`, `#86`, and `#87` on GitHub with evidence comments.

Validation: full commands listed below.

Next: continue on the structural refactor issues `#84` and `#88`, then close the epic `#76`.

## Blockers

- Remaining work is architectural, not environmental: `#84` still requires porting the legacy delivery agents (`dev/lint/test/security/pr`) onto the lane-subscriber runtime in the actual execution path, and `#88` still requires replacing/removing the legacy linear `SprintFlow.run()` orchestration rather than only adding tuple runtime surfaces alongside it.

## Validation History

| Command | Result | Notes |
|---|---|---|
| `git pull --ff-only` | pass | Fast-forward from `260cfb8` to `11f914a` |
| `python scripts/build_agent_catalog.py` | pass | generated `.catalog/agents.json` |
| `python scripts/build_agent_catalog.py --check` | pass | drift gate green |
| `python -m pytest tests -q` | pass | `377 passed, 1 skipped` |
| `python -m ruff check sendsprint tests` | pass | full lint green |
| `npm run lint` | pass | `web` typecheck green |
| `npm run test:e2e` | pass | `6 skipped` smoke suite as configured |


### Checkpoint 5

Status: completed

Task: Finish the structural tuple-runtime migration, prove cache/resume behavior, and close the remaining GitHub issues.

Result: Rewired `SprintFlow` so the main execution path now bootstraps worker-root tuples and runs `dev -> lint -> test -> security -> pr` through `WorkerPool` lanes. Added cached receipt payload materialization for cross-run reuse, tuple-id aware resume CLI resolution, a kill-and-resume harness, cross-run cache regression coverage, and updated `README.md` / `ARCHITECTURE.md` to document the new runtime-first path.

Validation: `python -m pytest tests -q`; `python -m ruff check sendsprint tests`; `npm run lint`; `npm run test:e2e`.

Next: close `#84`, `#88`, and `#76`, then commit and push.

### Checkpoint 6

Status: completed

Task: Correct the web layout to match the GPT-image-2 storyboard exports under `telas/exports/screens/01_web_storyboard`.

Result: Reworked the desktop shell density, restored in-canvas headers for app screens, centered the provider picker, converted the sprint import pipeline to the horizontal 8-step storyboard treatment, tightened the 7-column backlog board, and rebuilt the task-detail modal as a wide two-column operational modal with logs, evidence tiles, and readiness.

Validation: `npm --prefix web run typecheck`; `BASE_URL=http://localhost:19006 npx playwright test --project=chromium` (`7 passed`).

Next: use the captured screenshots in `.codex-layout-shots/after2/` for any remaining pixel-level review.

### Checkpoint 7

Status: completed

Task: Save SendSprint web connection context per app user so Azure DevOps does not require reconnecting on each login.

Result: Added a per-email `userProfiles` cache to the web session store. The profile stores non-secret delivery context only: provider, account, Jira board id, Azure DevOps team path, current sprint, and project setup. Login now restores the matching profile after app authentication, while logout saves the active user's profile and clears user-scoped fields from the visible session.

Validation: `npm --prefix web run typecheck`; `BASE_URL=http://localhost:19006 npx playwright test --project=chromium` (`8 passed`).

Next: review the persisted profile behavior in a real Azure DevOps login session.
