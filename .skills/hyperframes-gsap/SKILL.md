---
name: hyperframes-gsap
description: GSAP usage rules and patterns inside HyperFrames compositions. Use whenever animating any element in a composition. Covers the paused-timeline contract, `window.__timelines` registration, allowed/banned properties, easing palette, stagger, position parameters, transform aliases, and conflict avoidance. The non-negotiable rules from the main hyperframes skill apply.
---

# GSAP for HyperFrames

HyperFrames manages GSAP timelines through a runtime adapter. The contract:

1. Create a **paused timeline synchronously**.
2. Register it on `window.__timelines` using the composition's `data-composition-id` as the key.
3. Let HyperFrames control playback and seeking.

> Mirror of upstream `skills/gsap/SKILL.md` (with hyperframes-specific guardrails called out).

## Core contract

```html
<script src="https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"></script>
<script>
  window.__timelines = window.__timelines || {};
  const tl = gsap.timeline({ paused: true });
  // tweens...
  window.__timelines["my-composition-id"] = tl;
</script>
```

Key restrictions:

- **Never call `.play()`** on render-critical motion — the framework owns playback.
- **Build synchronously** — no `async`/`await`, no `setTimeout`, no Promises, no event handlers.
- **Finite loops only** — `repeat: -1` breaks the capture engine. Calculate exact counts: `repeat: Math.ceil(duration / cycleDuration) - 1`.
- **Timeline key must match `data-composition-id`** exactly.

## Essential tween methods

| Method          | Purpose                                                     |
| --------------- | ----------------------------------------------------------- |
| `gsap.to()`     | Animate to target values (most common, exits, ambient)      |
| `gsap.from()`   | Animate from values (entrances — CSS position is end state) |
| `gsap.fromTo()` | Explicit start and end (use inside sub-compositions)        |
| `gsap.set()`    | Apply changes immediately (duration 0)                      |

Always use **camelCase** properties (`backgroundColor`, not `background-color`).

## Allowed vs banned properties

**Animate freely:** `opacity`, `x`, `y`, `z`, `scale`, `scaleX`, `scaleY`, `rotation`, `rotationX`, `rotationY`, `skewX`, `skewY`, `color`, `backgroundColor`, `borderRadius`, transforms.

**Never animate:**

- `visibility`, `display` — these don't interpolate.
- `width`/`height` on video elements — animate a wrapper div.
- Anything that triggers layout (`width`, `height`, `top`, `left`) when a transform achieves the same look.

**Never call:** `video.play()`, `audio.play()`, `pause()`, `seek()`. The framework owns media playback.

## Transform aliases

Prefer GSAP transform aliases over raw `transform` strings:

| GSAP property                          | Result                  |
| -------------------------------------- | ----------------------- |
| `x`, `y`, `z`                          | Translation in pixels   |
| `scale`, `scaleX`, `scaleY`            | Scaling                 |
| `rotation`, `rotationX`, `rotationY`   | 2D/3D rotation          |
| `skewX`, `skewY`                       | Skew                    |
| `autoAlpha`                            | Opacity + visibility    |

## Easing palette

Vary eases across entrances. Use at least 3 different eases per scene.

| Family       | Examples                                                              |
| ------------ | --------------------------------------------------------------------- |
| Power        | `"power1.out"`, `"power2.out"`, `"power3.out"`, `"power4.out"`        |
| Back         | `"back.out(1.7)"`, `"back.out(2.5)"`                                  |
| Expo         | `"expo.out"`, `"expo.inOut"`                                          |
| Elastic      | `"elastic.out(1, 0.3)"`                                               |
| Bounce       | `"bounce.out"`                                                        |
| Circ         | `"circ.out"`                                                          |
| Sine         | `"sine.out"` (gentle ambient motion)                                  |
| Linear       | `"none"` (only for crossfades / pixel-precise scrubs)                 |

Defaults: entrances ~0.3–0.6s, exits ~0.3–0.4s, ambient breathing 4–8s.

## Stagger

```js
tl.from(".card", {
  y: 40,
  opacity: 0,
  duration: 0.5,
  stagger: 0.08,                    // 80ms between each
  ease: "power3.out",
}, 0.3);

// Object form for fine control:
tl.from(".item", {
  opacity: 0,
  stagger: { amount: 0.6, from: "center" },
  ease: "power2.out",
}, 0);
```

## Position parameters

The third argument to `.to()`/`.from()` controls timeline placement:

- **Absolute**: `0`, `1`, `2.5` (seconds from timeline start)
- **Relative**: `"+=0.5"` (0.5s after previous tween ends), `"-=0.2"` (overlap)
- **Label-based**: `tl.addLabel("scene2", 6.2)` then `"scene2+=0.3"`
- **Alignment**: `"<"` (same start as previous), `"<0.2"` (0.2s after previous starts), `">"` (after previous ends)

## Variables and timeline construction

```js
const tl = gsap.timeline({
  paused: true,
  defaults: { duration: 0.5, ease: "power2.out" },
});
```

`defaults` reduces repetition. Override per-tween when needed.

## Conflict rules

- Never animate the same property on the same element from multiple timelines simultaneously.
- Use `overwrite: "auto"` or `"none"` only when you understand the tradeoff — default is to let GSAP decide.
- For `gsap.set()` on clip elements from later scenes: those elements don't exist in the DOM at page load. Use `tl.set(selector, vars, timePosition)` inside the timeline at or after the clip's `data-start` time instead.

## Repeats

Always finite. To loop ambient motion for the composition's duration:

```js
const cycleDuration = 4;          // seconds per loop
const compDuration = 12;           // total composition duration
tl.to(".glow", {
  scale: 1.1,
  duration: cycleDuration / 2,
  yoyo: true,
  repeat: Math.ceil(compDuration / cycleDuration) * 2 - 1,
  ease: "sine.inOut",
}, 0);
```

Never `repeat: -1`.

## Performance tips

- Animate transforms and opacity — these stay on the compositor.
- Use `gsap.quickTo()` for frequent DOM updates (rare in capture pipelines but useful in studio previews).
- Apply `will-change: transform` only to elements with continuous motion.
- Use stagger instead of many manual delays.

## Determinism

- No `Math.random()` — use a seeded PRNG (`mulberry32(seed)`).
- No `Date.now()` — read variables or constants instead.
- No `await`/`setTimeout`/`Promise` around the timeline build — the capture engine reads `window.__timelines` synchronously after page load.

## Common patterns

**Entrance + ambient + (transition handles exit):**

```js
// Entrance
tl.from("#title",    { y: 50, opacity: 0, duration: 0.7, ease: "power3.out" }, 0.3);
tl.from("#subtitle", { y: 30, opacity: 0, duration: 0.5, ease: "power2.out" }, 0.6);

// Ambient breathing on a decorative glow (finite repeat)
tl.to(".glow", {
  scale: 1.08,
  duration: 2.5,
  yoyo: true,
  repeat: 3,                       // 4 cycles total within the scene
  ease: "sine.inOut",
}, 1.0);

// NO exit tweens — the transition at t=7s handles scene 1's exit
```

**Sub-composition (use fromTo, not from):**

```js
// Inside compositions/card.html — fromTo is load-bearing here
tl.fromTo("#card-title",
  { y: 40, opacity: 0 },
  { y: 0, opacity: 1, duration: 0.6, ease: "power3.out" },
  0.2
);
```

The reason: `gsap.from()` reads the current DOM state as the target. Inside sub-comps loaded asynchronously via `data-composition-src`, the read can race the mount. `fromTo` makes both states explicit.

---

For the broader animation philosophy (rhythm, beat direction, motion principles, layout-before-animation), see the main `hyperframes` skill.
