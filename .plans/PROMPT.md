You are continuing work on SendSprint — a multi-agent CLI that delivers Jira/ADO sprints autonomously via Claude Code.

This is a FRESH context window. Read AGENTS.md before doing anything.

@.plans/prd.json @.plans/progress.txt @AGENTS.md

## Rules (hard)

1. Follow AGENTS.md 10-step flow strictly: read sprint -> map architecture -> dev -> lint -> tests -> security -> fix loop -> commit -> PR -> review.
2. Transport priority for operators is fixed: `mcp -> api -> playwright`. Never reorder.
3. Security findings are flag-only. Never auto-fix (per ADR-005).
4. Surgical edits — touch only what the task spec requires.
5. Conventional Commits in English; commit body may be PT-BR.
6. Bump version in `pyproject.toml`, `sendsprint/__init__.py`, `README.md`, `CHANGELOG.md` when shipping a feature/fix.
7. **You can only modify the `passes` field of prd.json.** Change `false` -> `true` only after all acceptance criteria are verified.

## Loop

1. Pick the highest-priority feature in `.plans/prd.json` whose `passes == false`.
2. Read its spec file under `.specs/sprints/sprint-1/*.task.md`.
3. Search the codebase before assuming anything is missing.
4. Implement using TDD when applicable: tests first, then production code.
5. Run verification:
   - `ruff check sendsprint/`
   - `ruff format --check sendsprint/`
   - `pytest tests/ -v --cov=sendsprint --cov-report=term-missing`
   - Coverage of touched files >= threshold defined in the task spec.
6. If all acceptance criteria from the spec are met and DoD is green, set `passes: true` for that feature in `.plans/prd.json`.
7. Append a short learning to `.plans/progress.txt` (one line, imperative, English).
8. Commit with a Conventional Commit message in English: `git commit -m "feat(detector): add bun runtime marker"` etc.

ONE FEATURE PER ITERATION. Do not start a second one in the same loop.

If every feature has `passes: true`, output `<promise>COMPLETE</promise>`.

## Don'ts

- No new dependencies without justification in the task spec.
- No refactor outside the touched modules.
- No skipping the lint or coverage gate to "go faster".
- No auto-fix of security findings.
- No edits to `main` — work on the current branch only.
