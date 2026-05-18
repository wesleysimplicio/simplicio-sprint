# Scripts

## `build_changelog.py`

Builds or promotes `CHANGELOG.md` sections from git history. Used by release
hygiene workflows.

## `generate_coverage_badge.py`

Reads coverage XML and updates `docs/assets/coverage-badge.svg`.

## `generate_demo_screenshots.py`

Creates static demo evidence screenshots used by the local API/dashboard demo.

## Standard Validation Wrapper

Project-level closure should still use:

```bash
taskflow run /Users/wesleysimplicio/Projetos/skills/SendSprint
```

This keeps the local human-review checklist aligned with the global workflow.
