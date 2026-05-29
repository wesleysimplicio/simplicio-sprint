# Cross-Repo Issues — SendSprint Flow Hardening

This file collects issue bodies to be opened in the **partner repositories** so
the full SendSprint flow lands consistently across the Simplicio ecosystem. The
SendSprint-side companion issues are #271–#278 (this repo).

## How to use this file

For each section below:

1. Open the linked repo on GitHub.
2. **New Issue** → paste the title from the heading.
3. Paste the body as-is.
4. Hand the issue to the local agent (Claude / Codex / etc.) saying:
   > "Implement this issue in **this** repo. Read the codebase first, follow the
   > project's conventions (`AGENTS.md` / `CLAUDE.md` / `CONTRIBUTING.md`), adapt
   > the acceptance criteria to what already exists, open a draft PR, and link
   > back to wesleysimplicio/simplicio-sprint where the parent issue lives."

Each body intentionally describes **what SendSprint expects from the partner**,
not how to implement it inside that repo — the local agent is the one who knows
the codebase.

---

## 📦 `wesleysimplicio/simplicio-mapper`

**Title:** `feat: expose project-map.json bootstrap as idempotent simplicio-mapper index command`

```markdown
> Open this issue inside `simplicio-mapper`. Read the repo (`AGENTS.md`,
> `README.md`, existing CLI subcommands) before implementing. Adapt naming /
> module layout to what's already there.

## Why

`simplicio-sprint` (issue wesleysimplicio/simplicio-sprint#273) needs to invoke
`simplicio-mapper index <repo>` automatically when the target repo lacks
`.simplicio/project-map.json`. The mapper currently has indexing logic — this
issue is about making it a stable, scriptable command that sendsprint can call
on every run without paying full cost.

## What SendSprint expects

- A single entry point — `simplicio-mapper index <path>` (or the equivalent
  subcommand your CLI already exposes).
- **Idempotent**: re-running with a fresh index detects via repo hash /
  mtime / git rev and short-circuits in <200 ms.
- **Quiet by default**: only emit progress when `--verbose`; stay silent on
  successful no-op so it doesn't pollute sendsprint logs.
- **Structured output**: `--json` produces a stable schema sendsprint can
  parse (paths produced, item counts, skipped reason).
- **Clear exit codes**: `0` = wrote/refreshed, `1` = failure, `2` = skipped
  (already fresh).

## Acceptance

- [ ] `simplicio-mapper index .` produces or refreshes
      `.simplicio/project-map.json` (and `precedent-index.json` if you ship it).
- [ ] Re-run on an unchanged repo: exit code 2, <200 ms.
- [ ] `--json` is a stable contract documented in `README.md`.
- [ ] Tests cover the three paths (fresh / refresh / no-op).

## Out of scope

- Changing the JSON schema of `project-map.json` (sendsprint already consumes it).
- The bootstrap *from* sendsprint side — that's wesleysimplicio/simplicio-sprint#273.

Refs: wesleysimplicio/simplicio-sprint#273, #262
```

---

## 📦 `wesleysimplicio/simplicio-prompt`

**Title:** `feat: --batch mode for sendsprint fan-out across sprint items`

```markdown
> Open this issue inside `simplicio-prompt`. Read the kernel layout
> (`examples/python/prompt_fanout.py`, the YOOL/TUPLE/HAMT runtime) before
> implementing. Adapt to whatever batching primitives the kernel already
> exposes.

## Why

`simplicio-sprint` calls `PromptFanout` (with `--subagents 600`) **once per
sprint item** via subprocess. For a sprint with N items that's N kernel
boots, each paying TLS handshake + import + warm-up cost. At N=12 the
overhead is the dominant term.

## What SendSprint expects

A way to run fan-out for many tasks reusing one kernel boot:

- `simplicio-prompt --batch tasks.jsonl --subagents 600 --json > out.ndjson`
- Input JSONL: one task per line, e.g.
  ```json
  {"task_id": "WS-101", "prompt": "...", "system": "..."}
  ```
- Output NDJSON: one result per line, `{task_id, status, ...result}`.
- A failure on one task **does not** drop the batch — emit the error line
  and keep going.
- Honors the existing flags (`--dry-run`, `--provider`, etc.).

## Benefit (measurable)

Expected 60–80 % reduction on pre-execution brainstorm time for multi-item
sprints. Wall-clock target: per-task added cost ≈ kernel step time, not
kernel boot time.

## Acceptance

- [ ] `--batch` flag implemented; documented in `README.md`.
- [ ] One kernel boot per batch (verified by timing the second task vs. the
      first — should be nearly equal).
- [ ] Output schema documented and stable.
- [ ] Test covering: success, partial failure, malformed line.

## Out of scope

- Changing the per-task subagent kernel itself.
- Distribution / parallel kernels — single boot, sequential tasks is enough
  for the SendSprint use case.

Refs: wesleysimplicio/simplicio-sprint#263 (initial integration)
```

---

## 📦 `wesleysimplicio/simplicio-cli`

**Title:** `feat: --dry-run-task, structured JSON output, and --bound-paths for sendsprint orchestration`

```markdown
> Open this issue inside `simplicio-cli` (the executor — the `simplicio task`
> command). Read its CLI surface (`simplicio --help`, the `task` subcommand)
> and stay inside the project's existing flag conventions. Where the
> infrastructure already exists, just expose / harden it.

## Why

`simplicio-sprint` invokes `simplicio task <task-md>` once per sprint item.
Three gaps make orchestration harder than it should be:

1. SendSprint wants to preview impact before applying (`--dry-run-task`).
2. The current text output is hard to parse — sendsprint guesses at success.
3. When the orchestrator already knows the task is front-only or back-only,
   it should be able to constrain the executor's edit surface.

## What SendSprint expects

### `--dry-run-task`

- Plans the edit, returns the would-be diff and cost estimate.
- Does **not** mutate the working tree, does **not** commit.

### `--json`

- Stable schema:
  ```json
  {
    "task_id": "...",
    "applied": true,
    "files_changed": ["src/a.py", "src/b.py"],
    "tokens_used": {"prompt": 12345, "completion": 6789},
    "cost_usd": 0.042,
    "diff_summary": "added Login button to LandingPage",
    "warnings": []
  }
  ```
- Both `--dry-run-task` and the regular run honor `--json`.

### `--bound-paths <glob>`

- Multiple values allowed.
- Executor refuses any edit outside the union of those globs and emits a
  `warnings` entry instead of silently applying.

## Acceptance

- [ ] `simplicio task --dry-run-task --json` returns the schema above, no
      files touched, no commit made.
- [ ] `simplicio task --bound-paths "frontend/**"` cannot edit `backend/**`.
- [ ] Stable JSON contract documented in `README.md`.
- [ ] Tests for: dry-run, bound-paths violation, normal run.

## Out of scope

- Changing the per-task LLM logic.
- Splitting tasks — sendsprint stays the orchestrator.

Refs: wesleysimplicio/simplicio-sprint#275, #278
```

---

## 📦 `wesleysimplicio/hyperframes`

**Title:** `feat: --evidence-mode preset for sendsprint delivery videos`

```markdown
> Open this issue inside `hyperframes`. Read the existing CLI / composition
> templates and stay inside whatever framework the repo uses (Remotion,
> Motion Canvas, etc.).

## Why

`simplicio-sprint` (issue wesleysimplicio/simplicio-sprint#277) wants to render
short "delivery videos" for tasks that ship UI. The
`.skills/hyperframes/SKILL.md` (wesleysimplicio/simplicio-sprint#255) defines
the trigger but expects the local agent to write the HTML composition every
time. That's a lot of ceremony for a generic "before / step / after" video.

## What SendSprint expects

A turnkey preset:

```bash
hyperframes --evidence-mode .sendsprint/evidence/<KEY> -o delivery.mp4
```

- Input: a folder containing `manifest.json` + screenshots + log.
- Output: `delivery.mp4`, ≤30 s, 1080p, with overlays:
  - top-left: task key
  - top-right: timestamp / step name
  - bottom: short caption pulled from `manifest.json.title`
- Default composition templated — caller does **not** need to write HTML.
- If a custom composition is provided (`--composition path.html`), use it
  instead.
- Exit code 0 = success, 2 = skipped (no screenshots found), 1 = failure.
  sendsprint registers exit 2 as "skipped" and keeps going.

## Acceptance

- [ ] `hyperframes --evidence-mode <folder> -o out.mp4` produces a valid mp4.
- [ ] Overlay text is legible at 1080p.
- [ ] No screenshots in folder: exit 2, helpful message.
- [ ] `README.md` documents the manifest.json contract sendsprint will write.

## Out of scope

- Changing the underlying rendering engine.
- Audio narration — that's a follow-up.

Refs: wesleysimplicio/simplicio-sprint#277, #255
```

---

## SendSprint-side context

These four issues are the **partner half** of the flow hardening work tracked
in this repo as issues #271–#278. The pairing:

| Partner repo | SendSprint companion |
| ------------ | -------------------- |
| simplicio-mapper | #273 (auto-bootstrap of `.simplicio/`) |
| simplicio-prompt | #275 (progress table; batch reduces per-item time) |
| simplicio-cli | #275 (progress table), #278 (stack-aware test/lint) |
| hyperframes | #277 (evidence video integration) |

Each partner issue is independent: if any one slips, the SendSprint companion
falls back to the current degraded path (already implemented for missing
mapper, missing hyperframes, etc.).
