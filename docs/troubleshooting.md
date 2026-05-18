# Troubleshooting

## `sendsprint` command not found

Use the repo-local binary:

```bash
.venv/bin/sendsprint --help
```

If `.venv` is missing:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[dev,api]"
```

## `python3 -m sendsprint.cli` cannot import `typer`

The global Python does not have project dependencies. Use `.venv/bin/python` or
install the repo in editable mode inside `.venv`.

## Playwright tests skip or do not capture browser evidence

Install Chromium and provide a target URL when needed:

```bash
npm run playwright:install
BASE_URL=http://localhost:8081 npm run test:e2e
```

## PyPI publish fails

Check `.github/workflows/pypi-publish.yml`, GitHub release tag, and PyPI trusted
publisher configuration. Issue `#27` owns the token-to-trusted-publisher
restoration.

## Worktree conflicts

List and prune stale worktrees:

```bash
git worktree list
git worktree prune
```

Do not delete unrelated user worktrees without confirming ownership.

## Security review fails

High or critical findings are intentionally blocking. SendSprint reports them
and does not auto-fix security-sensitive code.
