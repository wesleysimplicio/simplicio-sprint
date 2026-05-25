---
name: hyperframes-cli
description: Drive the HyperFrames CLI — init, lint, inspect, validate, preview, render, browser, doctor, info, upgrade, compositions, benchmark, docs. Use when scaffolding a HyperFrames project, running render commands, or diagnosing toolchain problems. Requires Node ≥ 22 and FFmpeg.
---

# HyperFrames CLI

Everything runs through `npx hyperframes`. Requires Node.js ≥ 22 and FFmpeg.

> Mirror of upstream `skills/hyperframes-cli/SKILL.md`. Source: https://github.com/wesleysimplicio/hyperframes.

## Workflow

1. **Scaffold** — `npx hyperframes init my-video`
2. **Write** — author HTML composition (see the `hyperframes` skill)
3. **Lint** — `npx hyperframes lint`
4. **Visual inspect** — `npx hyperframes inspect`
5. **Preview** — `npx hyperframes preview`
6. **Render** — `npx hyperframes render`

Lint and inspect before preview. `lint` catches missing `data-composition-id`, overlapping tracks, and unregistered timelines. `inspect` opens the rendered composition in headless Chrome, seeks through the timeline, and reports text spilling out of bubbles/containers or off the canvas.

## Scaffolding

```bash
npx hyperframes init my-video                          # interactive wizard
npx hyperframes init my-video --example warm-grain     # pick an example
npx hyperframes init my-video --video clip.mp4         # with video file
npx hyperframes init my-video --audio track.mp3        # with audio file
npx hyperframes init my-video --example blank --tailwind # with Tailwind v4 browser runtime
npx hyperframes init my-video --non-interactive        # skip prompts (CI/agents)
```

Templates: `blank`, `warm-grain`, `play-mode`, `swiss-grid`, `vignelli`, `decision-tree`, `kinetic-type`, `product-promo`, `nyt-graph`.

`init` creates the right file structure, copies media, transcribes audio with Whisper, and installs AI coding skills. Use it instead of creating files by hand.

When using `--tailwind`, invoke the `tailwind` skill before editing classes or theme tokens. The scaffold uses Tailwind v4.2 via the browser runtime, not Studio's Tailwind v3 setup.

## Linting

```bash
npx hyperframes lint                  # current directory
npx hyperframes lint ./my-project     # specific project
npx hyperframes lint --verbose        # info-level findings
npx hyperframes lint --json           # machine-readable
```

Lints `index.html` and all files in `compositions/`. Reports errors (must fix), warnings (should fix), and info (with `--verbose`).

## Visual Inspect

```bash
npx hyperframes inspect                 # inspect rendered layout over the timeline
npx hyperframes inspect ./my-project    # specific project
npx hyperframes inspect --json          # agent-readable findings
npx hyperframes inspect --samples 15    # denser timeline sweep
npx hyperframes inspect --at 1.5,4,7.25 # explicit hero-frame timestamps
```

Use this after `lint` and `validate`. It reports:

- Text extending outside the nearest visual container or bubble
- Text clipped by its own fixed-width/fixed-height box
- Text extending outside the composition canvas
- Children escaping clipping containers

Errors should be fixed before rendering. Warnings are surfaced for agent review; add `--strict` to fail on warnings too. Repeated static issues are collapsed by default so JSON output stays compact for LLM context windows. Mark intentional overflow with `data-layout-allow-overflow`; skip decoratives with `data-layout-ignore`.

`npx hyperframes layout` remains available as a compatibility alias.

## Previewing

```bash
npx hyperframes preview                   # serve current directory
npx hyperframes preview --port 4567       # custom port (default 3002)
```

Hot-reloads on file changes. Opens the studio in your browser automatically.

When handing a project back to the user, use the Studio project URL, not the source `index.html` path:

```
http://localhost:<port>/#project/<project-name>
```

Use the actual port from the preview output and the project directory name. Treat `index.html` as source-code context only.

## Rendering

```bash
npx hyperframes render                                # standard MP4
npx hyperframes render --output final.mp4             # named output
npx hyperframes render --quality draft                # fast iteration
npx hyperframes render --fps 60 --quality high        # final delivery
npx hyperframes render --format webm                  # transparent WebM
npx hyperframes render --docker                       # byte-identical
```

| Flag                 | Options               | Default                      | Notes                                                              |
| -------------------- | --------------------- | ---------------------------- | ------------------------------------------------------------------ |
| `--output`           | path                  | `renders/name_timestamp.mp4` | Output path                                                        |
| `--fps`              | 24, 30, 60            | 30                           | 60fps doubles render time                                          |
| `--quality`          | draft, standard, high | standard                     | draft for iterating                                                |
| `--format`           | mp4, webm             | mp4                          | WebM supports transparency                                         |
| `--workers`          | 1-8 or auto           | auto                         | Each spawns Chrome                                                 |
| `--docker`           | flag                  | off                          | Reproducible output                                                |
| `--gpu`              | flag                  | off                          | GPU-accelerated encoding                                           |
| `--strict`           | flag                  | off                          | Fail on lint errors                                                |
| `--strict-all`       | flag                  | off                          | Fail on errors AND warnings                                        |
| `--variables`        | JSON object           | —                            | Override variable values declared in `data-composition-variables`  |
| `--variables-file`   | path                  | —                            | JSON file with variable values                                     |
| `--strict-variables` | flag                  | off                          | Fail render on undeclared keys or type mismatches in `--variables` |

**Quality guidance:** `draft` while iterating, `standard` for review, `high` for final delivery.

**Parametrized renders:** composition declares its variables on the `<html>` root with `data-composition-variables` (JSON **array** of declarations: `{id, type, label, default}` per entry). Scripts inside read the resolved values via `window.__hyperframes.getVariables()`. The CLI `--variables '{"title":"Q4 Report"}'` is a JSON **object keyed by id** that overrides declared defaults for one render; missing keys fall through. Sub-comp hosts override per-instance with `data-variable-values` (same object shape, scoped to one mount).

## Asset Preprocessing

`npx hyperframes tts`, `transcribe`, and `remove-background` produce assets that drop into a composition. Each downloads its own model on first run. For voice selection, whisper-model rules (the `.en`-translates-non-English gotcha), output format choice (VP9 alpha WebM vs ProRes), and the TTS → transcribe → captions chain, invoke the `hyperframes-media` skill.

## Troubleshooting

```bash
npx hyperframes doctor       # check environment (Chrome, FFmpeg, Node, memory)
npx hyperframes browser      # manage bundled Chrome
npx hyperframes info         # version and environment details
npx hyperframes upgrade      # check for updates
```

Run `doctor` first if rendering fails. Common issues: missing FFmpeg, missing Chrome, low memory.

## Other

```bash
npx hyperframes compositions   # list compositions in project
npx hyperframes docs           # open documentation
npx hyperframes benchmark .    # benchmark render performance
```
