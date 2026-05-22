---
name: sendsprint-doctor
description: Run `sendsprint doctor` and interpret the readiness output.
---

```bash
sendsprint doctor {{ARGS}}
```

Output rules:

- Green → ready.
- Yellow → degraded; propose the recovery action (install / set env var / `sendsprint login`).
- Red → blocker; do not run `/sendsprint` until fixed.

Answer briefly: `<green> green / <yellow> yellow / <red> red`. If any red, the first blocker.
