# SendSprint Deployment and Release Topology

SendSprint currently ships as a Python package and a GitHub repository release.
There is no always-on hosted service required for normal operation.

## Local Environments

| Environment | Command | Purpose |
|---|---|---|
| CLI | `.venv/bin/sendsprint --help` | Operator entry point |
| API | `.venv/bin/python -m sendsprint.api` | Local FastAPI backend on `localhost:8765` |
| Dashboard | `cd web && npm run dev` | Local run UI on `localhost:8081` |
| Tests | `.venv/bin/python -m pytest`, `npm run lint`, `npm test` | Validation |

## CI

- `.github/workflows/ci.yml`: root Node lint/test and optional Playwright.
- `.github/workflows/sendsprint.yml`: Python package validation.
- `.github/workflows/release-hygiene.yml`: coverage badge and changelog refresh.
- `.github/workflows/dod.yml`: Definition of Done checks.
- `.github/workflows/scaffold-self-check.yml`: scaffold compatibility checks.

## Release

- Source version: `pyproject.toml`, `sendsprint/__init__.py`, README status.
- Changelog: `CHANGELOG.md`; release hygiene can refresh generated sections.
- Distribution: GitHub release tag triggers `.github/workflows/pypi-publish.yml`.
- Target: PyPI package `sendsprint`.

## Publish Safety

- Do not deploy or publish manually unless explicitly requested.
- Production package publish should use a GitHub release tag.
- Trusted publishing work belongs to issue `#27`; token-based fallback exists
  today but should not be treated as the target state.

## Runtime Integrations

- GitHub PR/issue integration uses authenticated `gh`.
- Jira/Azure DevOps credentials may be stored through keyring or environment.
- Optional deploy callbacks are configured in `WorkspaceConfig.deploy` and must
  remain disabled unless explicitly requested.
