# GOAL RESULT

## Objective
Save SendSprint web connection context per app user so Azure DevOps does not require reconnecting on each login.

## Result
Completed.

### What changed
- Added a `userProfiles` map to the persisted web session, keyed by normalized user email.
- Stored only non-secret context per user: provider, account, Jira board id, Azure DevOps team path, current sprint, and project setup.
- Restored the matching profile after app login, before the dashboard opens.
- Saved the active user's profile on logout and cleared user-scoped fields from the visible session so another user does not inherit the previous context.
- Added Playwright coverage proving a saved Azure DevOps profile opens the active delivery context directly after login, without showing the Azure connection screen.

## Validation
- `npm --prefix web run typecheck` passed.
- `BASE_URL=http://localhost:19006 npx playwright test --project=chromium` passed: `8 passed`.

---

# Previous Goal Result

## Objective
Correct the SendSprint web layouts so the implemented screens follow the GPT-image-2 storyboard references in `telas/exports/screens/01_web_storyboard`.

## Result
Completed.

### What changed
- Reworked the shared web shell for the storyboard density: wider sidebar, cleaner topbar, in-canvas page headers, and correct padding for both scroll and non-scroll screens.
- Centered the provider-picker experience and preserved the three-card Jira/Azure/GitHub layout from the reference.
- Converted the sprint import view into the horizontal 8-step pipeline with progress bar and live-log panel.
- Tightened the backlog board so all seven storyboard columns remain visible at desktop width.
- Added query-param support for opening the task detail modal directly and rebuilt the modal as a wide two-column operational view with workflow metadata, logs, evidence tiles, and readiness.

## Validation
- `npm --prefix web run typecheck` passed.
- `BASE_URL=http://localhost:19006 npx playwright test --project=chromium` passed: `7 passed`.
- Visual screenshots captured under `.codex-layout-shots/after2/`.

---

# Older Goal Result

## Objective
Close the remaining open SendSprint tuple-runtime issues (`#84`, `#88`, `#76`) with real code, validation, and GitHub issue updates.

## Result
Completed.

### What changed
- `SprintFlow.run()` now delegates to `SprintFlow.bootstrap()` and the real execution path seeds tuple-root worker jobs instead of running the legacy direct delivery chain inline.
- The delivery agents now execute as lane subscribers in the main path: `dev -> lint -> test -> security -> pr`.
- Receipt payloads now materialize cached outputs, enabling cross-run reuse of worker results while preserving report reconstruction.
- CLI/API entrypoints now call the tuple bootstrap path; CLI resume accepts either a run id or a tuple id.
- Added regression coverage for cross-run cache reuse and subprocess kill/resume replay.
- Updated architecture/docs to describe the runtime-first orchestration path.

## Validation
- `python -m pytest tests -q` ? `390 passed, 3 warnings`
- `python -m ruff check sendsprint tests` ?
- `npm run lint` ?
- `npm run test:e2e` ? `6 skipped`

## GitHub Tracker Outcome
- Remaining open issues before this round: `#84`, `#88`, `#76`
- Tracker target after this round: `0` open issues
- Open PRs: `0`

## Notes
- Playwright smoke remains environment-skipped when the local dashboard target is not running; this is expected in the current suite configuration.
