# SendSprint — Development Workflow

> Day-to-day loop. From clone to PR.

---

## Setup (one-time)

```bash
git clone https://github.com/beyondlabs/sendsprint.git
cd sendsprint
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium
cp .env.example .env  # then fill secrets
```

Required env vars (see `.env.example`):

- `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` (if using Jira)
- `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT` (if using ADO)
- `LLM_PROVIDER`, `LLM_MODEL`, `ANTHROPIC_API_KEY` (or `OPENAI_API_KEY`) for optional LLM steps

---

## Daily loop

```
┌─ pull main ──────────────────────────────┐
│ git checkout main && git pull            │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│ create branch                            │
│ git checkout -b feat/<short-desc>        │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│ code + test                              │
│ - implement                              │
│ - pytest -m "not integration and not canary" -q
│ - ruff check . && ruff format .         │
│ - mypy sendsprint/                       │
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│ commit                                   │
│ git add -A                               │
│ git commit -m "feat(operators): add gitlab support"
└────────────────┬─────────────────────────┘
                 │
┌────────────────▼─────────────────────────┐
│ push + open PR                           │
│ git push -u origin feat/<short-desc>     │
│ gh pr create --fill                      │
└──────────────────────────────────────────┘
```

---

## Commit messages (Conventional Commits)

```
<type>(<scope>): <subject>

<optional body>

<optional footer>
```

**Types:** `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`, `ci`.

**Scopes:** `cli`, `flow`, `operators`, `agents`, `architecture`, `worktree`, `llm`, `models`, `skills`, `docs`.

**Examples:**
```
feat(operators): add GitLab Issues operator
fix(worktree): cleanup on KeyboardInterrupt
docs(adr): adopt ADR-005 flag-only security
test(jira): record VCR cassette for sprint 42
```

---

## Test discipline

| When | Run |
|------|-----|
| Every save | `pytest tests/<modified_module>` (fast loop) |
| Pre-commit | `pytest -m "not integration and not canary" -q` (full unit) |
| Pre-push | `pytest -m "not canary"` (unit + integration) |
| Weekly / on-demand | `pytest -m canary` (live APIs, requires secrets) |

See [/.specs/architecture/ADR-003-mock-fallback.md](../architecture/ADR-003-mock-fallback.md) for tier rationale.

---

## Lint + format

```bash
ruff check .         # lint
ruff format .        # format
mypy sendsprint/     # type-check
```

CI blocks merge if any of the three fail.

---

## Branch naming

| Prefix | When | Example |
|--------|------|---------|
| `feat/` | new feature | `feat/gitlab-operator` |
| `fix/` | bug fix | `fix/worktree-cleanup-on-sigint` |
| `refactor/` | no behavior change | `refactor/extract-pr-creator` |
| `docs/` | docs only | `docs/adr-006-llm-budget` |
| `chore/` | tooling/deps | `chore/bump-pydantic-2.7` |

---

## PR review checklist

- [ ] Tests pass (Tier 1 + Tier 2 if integration touched)
- [ ] `ruff check .` clean
- [ ] `mypy sendsprint/` clean
- [ ] CHANGELOG.md updated under `[Unreleased]`
- [ ] If new public API: docstring + example in module header
- [ ] If new ADR: linked from DESIGN.md + AGENTS.md
- [ ] If touching transport order: justify why and update ADR-002
- [ ] If touching SecurityReviewer: ensure flag-only invariant preserved (ADR-005)

---

## Delivery evidence checklist

Use this checklist when SendSprint executes user sprint work in external repos:

- [ ] Branch was created from `develop` or the configured base branch in an isolated worktree.
- [ ] Dirty original checkouts were not reused for delivery changes.
- [ ] Each repo was classified as changed, validated-only, or not applicable.
- [ ] Validated-only repos have a reason, such as "API contract already covers the behavior".
- [ ] Targeted tests for the affected area passed.
- [ ] Full-suite failures outside the affected area were reported as unrelated, not ignored.
- [ ] Visual evidence includes screenshot/video, or an auth/environment blocker artifact.
- [ ] Azure DevOps PR links the originating work item and includes configured required reviewers.

---

## Release

1. Bump version in `pyproject.toml` + `sendsprint/__init__.py:__version__`.
2. Move `[Unreleased]` entries → `[X.Y.Z] - YYYY-MM-DD` in `CHANGELOG.md`.
3. Tag: `git tag -a vX.Y.Z -m "Release X.Y.Z"`.
4. Push tag: `git push origin vX.Y.Z`.
5. CI publishes to PyPI on tag push.

SemVer: `MAJOR.MINOR.PATCH`.
- `MAJOR`: breaking change to step numbers, RunReport schema, or transport order.
- `MINOR`: new operator, new agent, new ADR.
- `PATCH`: bug fix, doc, internal refactor.

---

## See also

- [CONTRIBUTING.md](CONTRIBUTING.md) — what reviewers expect
- [/AGENTS.md](../../AGENTS.md) — canonical instructions
- [/.specs/architecture/PATTERNS.md](../architecture/PATTERNS.md) — code idioms
