# House Style

Creative direction for compositions when no `design.md` is provided. These are starting points — override anything that doesn't serve the content. When a `design.md` exists, its brand values take precedence; house-style fills gaps.

> Mirror of upstream `skills/hyperframes/house-style.md`.

## Before Writing HTML

1. **Interpret the prompt.** Generate real content. A recipe lists real ingredients. A HUD has real readouts.
2. **Pick a palette.** Light or dark? Declare bg, fg, accent before writing code.
3. **Pick typefaces.** Run the font discovery script in upstream `references/typography.md` — or pick a font you already know that fits the theme. The script broadens your options; it's not the only source.

## Lazy Defaults to Question

These patterns are AI design tells — the first thing every LLM reaches for. If you're about to use one, pause and ask: is this a deliberate choice for THIS content, or am I defaulting?

- Gradient text (`background-clip: text` + gradient)
- Left-edge accent stripes on cards/callouts
- Cyan-on-dark / purple-to-blue gradients / neon accents
- Pure `#000` or `#fff` (tint toward your accent hue instead)
- Identical card grids (same-size cards repeated)
- Everything centered with equal weight (lead the eye somewhere)
- Banned fonts (Roboto, Open Sans, Arial, Helvetica defaults — see upstream `references/typography.md` for the full list)

If the content genuinely calls for one of these — centered layout for a solemn closing, cards for a real product UI mockup, a banned font because it's the perfect thematic match — use it. The goal is intentionality, not avoidance.

## Color

- Match light/dark to content: food, wellness, kids → light. Tech, cinema, finance → dark.
- One accent hue. Same background across all scenes.
- Tint neutrals toward your accent (even subtle warmth/coolness beats dead gray).
- **Contrast:** enforced by `hyperframes validate` (WCAG AA). Text must be readable with decoratives removed.
- Declare palette up front. Don't invent colors per-element.

## Background Layer

Every scene needs visual depth — persistent decorative elements that stay visible while content animates in. Without these, scenes feel empty during entrance staggering.

Ideas (mix and match, 2–5 per scene):

- Radial glows (accent-tinted, low opacity, breathing scale)
- Ghost text (theme words at 3–8% opacity, very large, slow drift)
- Accent lines (hairline rules, subtle pulse)
- Grain/noise overlay, geometric shapes, grid patterns
- Thematic decoratives (orbit rings for space, vinyl grooves for music, grid lines for data)

All decoratives should have slow ambient GSAP animation — breathing, drift, pulse. Static decoratives feel dead.

**Decorative count vs motion count.** The "2–5 per scene" count refers to decorative _elements_. If a project's `design.md` says "single ambient motion per scene", it means one looping motion applied to these decoratives (a shared breath/drift/pulse) — not one element total. A scene with 4 decoratives sharing one breathing motion is correct; a scene with 1 decorative is under-dressed.

## Motion

Quick rules: 0.3–0.6s entrances, vary eases, combine transforms (`y + opacity`, `scale + opacity`, `x + rotation`), overlap entries with stagger. Full philosophy in upstream `references/motion-principles.md`.

## Typography

Quick rules: 700–900 weight headlines, 300–400 weight body, pair serif + sans (not two sans), 60px+ headlines, 20px+ body, 16px+ data labels. Full rules in upstream `references/typography.md`.

## Palettes

Declare one background, one foreground, one accent before writing HTML.

| Category          | Use for                                       |
| ----------------- | --------------------------------------------- |
| Bold / Energetic  | Product launches, social media, announcements |
| Warm / Editorial  | Storytelling, documentaries, case studies     |
| Dark / Premium    | Tech, finance, luxury, cinematic              |
| Clean / Corporate | Explainers, tutorials, presentations          |
| Nature / Earth    | Sustainability, outdoor, organic              |
| Neon / Electric   | Gaming, tech, nightlife                       |
| Pastel / Soft     | Fashion, beauty, lifestyle, wellness          |
| Jewel / Rich      | Luxury, events, sophisticated                 |
| Monochrome        | Dramatic, typography-focused                  |

For exact hex values per palette, read upstream `skills/hyperframes/palettes/<name>.md` (e.g. `bold-energetic.md`, `dark-premium.md`).

Or derive from OKLCH — pick a hue, build bg/fg/accent at different lightnesses, tint everything toward that hue.

## Quick starter palettes

**Dark / Premium** (default for SendSprint delivery-evidence videos):

```css
:root {
  --bg:     #0b0f1a;
  --fg:     #e8ecff;
  --muted:  #8a93b8;
  --ok:     #6ee7b7;
  --fail:   #fca5a5;
  --skip:   #fcd34d;
  --accent: #818cf8;
}
```

**Warm / Editorial:**

```css
:root {
  --bg:     #f6f5f1;
  --fg:     #1a1a1a;
  --muted:  #6b6b6b;
  --accent: #c2410c;
}
```

**Clean / Corporate:**

```css
:root {
  --bg:     #ffffff;
  --fg:     #0f172a;
  --muted:  #64748b;
  --accent: #2563eb;
}
```
