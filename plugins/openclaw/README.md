# SendSprint — OpenClaw plugin

Plugin package for [OpenClaw](https://openclaw.dev) that positions OpenClaw as the **independent reviewer + security validator** around SendSprint deliveries.

## Stance

`read-only-by-default`. The plugin **never**:

- pushes commits,
- opens PRs,
- auto-fixes security findings (ADR-005 — flag-only),
- bypasses SendSprint's policy gates.

## What you get

- `openclaw-plugin.json` — plugin manifest with `role: reviewer`.
- `skills/sendsprint.md` — canonical skill manifest.
- `commands/` — `review-sprint`, `preflight`, `security-review`, `doctor`, `inspect-run`.
- `hooks/` — pre-commit + post-edit guards.

## Install

### Option A — OpenClaw plugin folder

```bash
mkdir -p ~/.openclaw/plugins
cp -r plugins/openclaw ~/.openclaw/plugins/sendsprint
```

### Option B — via SendSprint CLI

```bash
sendsprint plugins install --platform openclaw --packaged
```

## Requirements

- OpenClaw ≥ 1.0.
- `sendsprint` on PATH (`pip install sendsprint`).
- Read access to SendSprint artifacts (`report.json`, `evidence/`, `.sendsprint/`).

## Typical workflow

1. **Pre-delivery**: `/preflight <provider> <id>` → validate inputs, credentials, workspace before any writes.
2. **Delivery happens** (run by the Claude/Codex/Hermes plugin, not OpenClaw).
3. **Post-delivery**: `/review-sprint` → cross-check `report.json` + PR diff against the DoD checklist.
4. **Security**: `/security-review` → re-scan secrets/audit findings; report only.
5. **Forensics**: `/inspect-run <run_id> --cost` → review token cost + step durations.

See [skills/sendsprint.md](./skills/sendsprint.md) for the full contract.
