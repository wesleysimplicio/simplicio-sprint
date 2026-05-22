---
name: security-review
description: Independent flag-only security re-scan over the delivered changes.
---

OpenClaw security pass. **Flag-only** (ADR-005). Never auto-fix.

## Procedure

1. Re-run the SendSprint security scanner on the changed paths:
   ```bash
   sendsprint preflight --security-only {{ARGS}}
   ```
2. Independently check:
   - `.env` is gitignored.
   - No new secrets in the diff (12 standard secret patterns).
   - `npm audit` / `pip-audit` / `cargo audit` clean for new dependencies.
3. Report findings as a markdown table: `severity | file:line | pattern | recommendation`.
4. If any `high` or `critical` severity finding is present → recommend `BLOCK`, do not push a fix.
