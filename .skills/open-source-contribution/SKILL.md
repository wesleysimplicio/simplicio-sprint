---
name: open-source-contribution
description: Use when SendSprint must run open-source contribution cycles: scout issues and PRs, avoid duplicates, choose review/salvage/new-PR candidates, validate focused changes, publish clean PR descriptions, monitor feedback, rework, and persist learning.
---

## Trigger

- Use this skill when contributing to an external or public open-source repo.
- Use it when the user asks for issue scouting, PR review, duplicate avoidance, contribution volume, maintainer feedback handling, or reusable contribution learning.

## Steps

1. Snapshot the target repo: branch, fork/upstream state, contribution files, active paths, open issues, open PRs, recently closed PRs, and local operational memory.
2. Run the dedupe gate before coding: compare title, issue, exact error text, changed files, traceback/function names, closed PR lineage, salvage PRs, forks, and remembered blockers.
3. Select one small candidate: prefer review or consolidation when an active PR already covers the area; open a new PR only for a narrow, low-risk, testable slice with no overlap and no smaller correct fix already active.
4. Implement defensively: avoid unrelated refactors, keep the diff reversible, and preserve maintainer style.
5. Validate locally with the smallest focused command that proves the touched behavior; add or update nearby tests when the repo already has a clear test pattern.
6. Prepare public output: PR text must use `What does this PR do?`, `Problem` or `Root cause`, `What this changes` or `Fix`, `Why this shape`, and `Tests`; never include internal scoring, volume strategy, duplicate-gate notes, local paths, tool failures, or private procedure.
7. Monitor and rework: watch CI, review comments, conflicts, and upstream duplicates; patch minimally and rerun focused validation, or close/defer if upstream solved it.
8. Learn: persist only reusable signals, duplicate markers, validation commands, maintainer preferences, and next safe targets in SendSprint operational memory.

## Patterns

- Batch work is a queue of individually gated candidates, not permission to bypass dedupe.
- Duplicate risk blocks new PRs and redirects to review, salvage, consolidation, or a different slice.
- A maintainer response like "competing with #PR for the same fix" becomes a no-go rule for new broader PRs in that cluster.
- Good candidates are tiny, boring, defensible, and easy for maintainers to merge.
- Public PRs show evidence, not internal process.
- A learning becomes a skill rule only after it helps across repeated cycles.

## Definition of Done

- [ ] Snapshot and dedupe evidence are recorded.
- [ ] Candidate decision is proceed, review, salvage, or defer with a clear reason.
- [ ] Focused validation command or manual check is recorded with result.
- [ ] Public PR/review text excludes internal process details.
- [ ] Follow-up status and reusable learning are saved.
