# Recipe: SendSprint delivery-evidence video

SendSprint-specific recipe for turning a `RunReport` (or `EvidenceBundle`) into a HyperFrames composition + MP4. Apply the rules from the main `hyperframes` skill in this folder; this file is the SendSprint-specific glue.

## Trigger

Activate when the user asks any of:

- pt-BR: "vídeo da entrega", "evidência em vídeo", "renderizar evidências", "gerar clipe da sprint"
- en: "render evidence video", "delivery video", "evidence clip", "video proof of delivery"
- es: "vídeo de entrega", "evidencia en vídeo"

Or implicitly when a `RunReport` JSON or `evidence-bundles/evidence-<run_id>/` directory is present in the working tree and the user requests "prova visual", "demo da última sprint", etc.

## Inputs

One of:

- `report.json` — `sendsprint.models.reports.RunReport` (preferred; has steps, evidence, PRs)
- `bundle.json` — `sendsprint.evidence.EvidenceBundle` (v2.0)
- `evidence-bundles/evidence-<run_id>/manifest.json` — `EvidenceBundleManifest` (v1.0)

## Steps

1. **Read the input.** Parse via `RunReport.model_validate_json(...)` or `EvidenceBundle.model_validate_json(...)`. Honor `run_id` / `sprint_id` for naming.

2. **Toolchain check.** `node --version` ≥ 22, `ffmpeg -version` present, `npx hyperframes --version` reachable. Missing → return `status="skipped"`. Never fake success.

3. **Pick palette.** Default to the Dark / Premium palette from `house-style.md` (matches the existing SendSprint Remotion brand at `video/src/theme.ts`). Override if the project repo has a `design.md`.

4. **Plan the timeline.** Use this rhythm (each value in seconds):

   | # | Scene        | Duration | Content                                                                                    |
   |---|--------------|----------|--------------------------------------------------------------------------------------------|
   | 1 | `intro`      | 4.0      | Pill "SendSprint" • Title "SendSprint Delivery" • Subtitle "Sprint {id} — {workspace}"     |
   | 2 | `summary`    | 4.0      | Status headline (color-coded) • bullet list: Steps OK / PRs / Scope                        |
   | 3..N | `step`     | 4.0 each | One per `StepReport`: pill (repo or "global") • headline "Step N: name" • message          |
   |   | `screenshot`| 2.5 each | One per `TestEvidence(kind="screenshot", path=…)` inside the step                          |
   | Last | `outro`   | 3.0      | Pill "delivered" • headline sprint id • list of PR URLs                                    |

   Compute scene `data-start` cumulatively — no overlap. Layout-before-animation applies: write static CSS at the hero frame, then add entrance tweens.

5. **Emit composition HTML.** Output to `hyperframes-out/composition.html`. Use the structure from the main skill (`data-composition-id`, `data-width=1920`, `data-height=1080`, `data-fps=30`). Every scene gets entrance animations; only the outro fades out (per the non-negotiable transition rules in the main skill).

6. **Escape user content.** All strings from the report (`sprint_id`, `workspace`, `step.name`, `step.message`, `pr.url`) pass through `html.escape` (Python) before injection. Test case: `sprint_id="<script>alert(1)</script>"` must NOT execute in the browser.

7. **Lint + inspect.** Run `npx hyperframes lint hyperframes-out/` and `npx hyperframes inspect hyperframes-out/` before rendering. Fix layout overflow if reported.

8. **Render MP4.**

   ```bash
   npx hyperframes render hyperframes-out/composition.html \
     --output hyperframes-out/evidence-<run_id>.mp4 \
     --fps 30 --quality standard
   ```

   Timeout 600s. Capture stderr on non-zero exit.

9. **Attach to bundle.** If `EvidenceBundle` exists for this `run_id`, append the MP4 as an evidence item:

   ```python
   from sendsprint.evidence import BundleManager, EvidenceItemType
   mgr = BundleManager()
   bundle = mgr.load_bundle(run_id)
   if bundle:
       mgr.add_item(
           bundle,
           EvidenceItemType.screenshot,  # closest existing type for video
           f"hyperframes-out/evidence-{run_id}.mp4",
           metadata={"title": "delivery video", "kind": "video/mp4"},
       )
       mgr.finalize(bundle)
   ```

10. **Report.** Console output via Rich, colored by status (green=ok, yellow=skipped, red=failed). Match the conventions in `sendsprint/cli.py`.

## Composition skeleton

Adapt this skeleton — do NOT copy verbatim without filling all `{placeholder}` slots:

```html
<!doctype html>
<html
  lang="en"
  data-composition-variables='[
    {"id":"sprint_id","type":"string","label":"Sprint ID","default":"unknown"},
    {"id":"workspace","type":"string","label":"Workspace","default":"workspace"}
  ]'
>
<head>
<meta charset="utf-8" />
<title>SendSprint evidence — {sprint_id}</title>
<style>
  :root { --bg:#0b0f1a; --fg:#e8ecff; --muted:#8a93b8;
          --ok:#6ee7b7; --fail:#fca5a5; --skip:#fcd34d; --accent:#818cf8; }
  body { margin:0; background:var(--bg); color:var(--fg);
         font-family: ui-sans-serif, system-ui, sans-serif; }
  .scene-content { width:100%; height:100%; padding:120px 160px;
                   display:flex; flex-direction:column; justify-content:center; gap:24px;
                   box-sizing:border-box; }
  h1 { font-size:120px; margin:0; letter-spacing:-0.02em; }
  h2 { font-size:64px;  margin:0; color:var(--accent); }
  p  { font-size:32px;  margin:0; color:var(--muted); }
  ul { font-size:28px;  margin:0; padding:0; list-style:none; }
  .pill { display:inline-block; padding:6px 14px; border-radius:999px;
          background:rgba(129,140,248,0.15); font-size:24px; color:var(--accent); width:max-content; }
  .status-ok { color:var(--ok); }
  .status-failed { color:var(--fail); }
  .status-skipped { color:var(--skip); }
  img { max-width:100%; max-height:720px; border-radius:16px; object-fit:contain;
        box-shadow: 0 16px 48px rgba(0,0,0,0.5); }
</style>
</head>
<body>
<div data-composition-id="sendsprint-evidence" data-width="1920" data-height="1080">

  <div id="intro" data-start="0" data-duration="4" data-track-index="0">
    <div class="scene-content">
      <span class="pill">SendSprint</span>
      <h1>SendSprint Delivery</h1>
      <p>Sprint {sprint_id} — {workspace}</p>
    </div>
  </div>

  <div id="summary" data-start="4" data-duration="4" data-track-index="0">
    <div class="scene-content">
      <h2 class="status-ok">{summary}</h2>
      <ul>
        <li>Steps OK: <strong>{steps_ok}/{steps_total}</strong></li>
        <li>PRs opened: <strong>{pr_count}</strong></li>
        <li>Scope: <strong>{scope_mode}</strong></li>
      </ul>
    </div>
  </div>

  <!-- Step cards: one per StepReport, 4s each -->
  <!-- Screenshot cards: one per TestEvidence(kind=screenshot), 2.5s each -->

  <div id="outro" data-start="{cursor}" data-duration="3" data-track-index="0">
    <div class="scene-content">
      <span class="pill">delivered</span>
      <h1>Sprint {sprint_id}</h1>
      <ul>{pr_list}</ul>
    </div>
  </div>

  <script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
  <script>
    window.__timelines = window.__timelines || {};
    const tl = gsap.timeline({ paused: true, defaults: { ease: "power3.out" } });

    // INTRO entrance
    tl.from("#intro .pill", { y: 30, opacity: 0, duration: 0.5 }, 0.2);
    tl.from("#intro h1",    { y: 60, opacity: 0, duration: 0.7 }, 0.4);
    tl.from("#intro p",     { y: 30, opacity: 0, duration: 0.5, ease: "power2.out" }, 0.7);
    // NO exit tween on intro — transition handles it

    // SUMMARY entrance
    tl.from("#summary h2", { x: -40, opacity: 0, duration: 0.6, ease: "expo.out" }, 4.2);
    tl.from("#summary li", { y: 20,  opacity: 0, duration: 0.4, stagger: 0.08 }, 4.5);

    // ... step / screenshot scenes ...

    // OUTRO entrance + final fade (last scene only)
    tl.from("#outro .pill", { scale: 0.9, opacity: 0, duration: 0.4 }, "outro+=0.1");
    tl.from("#outro h1",    { y: 40, opacity: 0, duration: 0.6 }, "outro+=0.3");
    tl.from("#outro li",    { y: 20, opacity: 0, duration: 0.4, stagger: 0.1 }, "outro+=0.6");
    tl.to("#outro",         { opacity: 0, duration: 0.5, ease: "power2.in" }, "outro+=2.5");

    window.__timelines["sendsprint-evidence"] = tl;
  </script>
</div>
</body>
</html>
```

## Definition of Done

- [ ] `composition.html` exists, opens in a browser without console errors.
- [ ] All scenes have entrance animations; only the outro has an exit tween.
- [ ] No `data-start` overlap on the same `data-track-index`.
- [ ] All user-provided strings HTML-escaped (test `sprint_id="<script>"`).
- [ ] `npx hyperframes lint` and `npx hyperframes validate` both pass.
- [ ] `npx hyperframes inspect` reports zero text-overflow / out-of-canvas issues (or every reported issue is marked with `data-layout-allow-overflow`).
- [ ] WCAG contrast warnings cleared (`hyperframes validate` exits clean).
- [ ] If toolchain missing → returned `status="skipped"` with a clear message (no fake MP4).
- [ ] If MP4 rendered → file exists, `> 0 bytes`, `ffprobe` confirms `duration > 0`.
- [ ] MP4 attached to `EvidenceBundle` for the same `run_id` (when a bundle exists), with `metadata.kind="video/mp4"`.
- [ ] Console output uses Rich color conventions consistent with the rest of the SendSprint CLI.

## Notes

- The SendSprint Remotion pipeline lives at `video/` and renders marketing/explainer videos — do NOT mix the two. HyperFrames is per-delivery evidence; Remotion is product marketing.
- Hyperframes lib is opt-in: never add it to `pyproject.toml`. The agent invokes `npx` only when the user explicitly requests a video; otherwise the bundle is shipped as JSON + screenshots as today.
- For ADO/Jira tickets attached to the run, you can include the ticket URL in the outro list alongside PR URLs.
- For long sprints (>15 steps), consider rendering a single combined `step` scene that summarizes by status (e.g. "9 ok, 2 failed, 0 skipped") instead of one card per step — the render gets long and noisy otherwise.
