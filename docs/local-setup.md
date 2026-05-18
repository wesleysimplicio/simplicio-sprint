# Local Setup

## Python

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e ".[dev,api]"
```

Use `.venv/bin/sendsprint` instead of relying on a global executable. In this
workspace, `python3 -m sendsprint.cli ...` may fail if the shell does not have
project dependencies installed globally.

## Node and Web

```bash
npm install
cd web && npm ci
```

The root Node project mainly hosts Playwright and passthrough checks. The local
dashboard lives in `web/`.

## Common Commands

```bash
taskflow inspect /Users/wesleysimplicio/Projetos/skills/SendSprint
npm run lint
npm test
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy sendsprint/ --ignore-missing-imports
.venv/bin/python -m pytest
taskflow run /Users/wesleysimplicio/Projetos/skills/SendSprint
```

## Local API and Dashboard

```bash
.venv/bin/python -m sendsprint.api
cd web && npm run dev
```

Expected local URLs:

- API: `http://localhost:8765`
- Dashboard: `http://localhost:8081`

## Credentials

- GitHub automation expects `gh auth status` to pass.
- Jira/Azure DevOps can use environment variables or keyring.
- Do not commit `.env` files or tokens.
- LLM providers are optional and must remain opt-in for code generation.
