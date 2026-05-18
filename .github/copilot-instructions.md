# GitHub Copilot Instructions — SendSprint

**Read [AGENTS.md](../AGENTS.md) FIRST** — canonical source for stack, layout, commands, patterns, gotchas, commit conventions, and Definition of Done.

This file = GitHub Copilot-specific shorthand. Do not duplicate AGENTS.md content here.

---

## Quick context

SendSprint = Python multi-agent skill, 10-step sprint delivery flow, Jira/ADO → PR. Stack: Python ≥ 3.11, Pydantic v2, Typer, Rich, httpx, Playwright sync.

---

## Copilot suggestions — DO

- Use **Pydantic v2** (`BaseModel`, `Field`, `model_dump`, `model_dump_json`). NOT v1 (`dict()`, `json()`).
- Use **type hints everywhere**. `from __future__ import annotations` at top of every Python file.
- Use **`pathlib.Path`** not `os.path`.
- Use **`subprocess.run(..., capture_output=True, text=True, timeout=N, check=False)`**. Always set timeout.
- Wrap external tool calls in `try/except (FileNotFoundError, subprocess.TimeoutExpired, subprocess.CalledProcessError)` and return `StepReport(status="skipped"|"failed", details={...})`.
- Match step numbers to flow position: TestRunner=5, SecurityReviewer=6, LintRunner=4, PrCreator=9, PrReviewer=10.
- Cap report list lengths (e.g., max 20 secrets, max 20 vulns) to avoid bloat.

## Copilot suggestions — DON'T

- DON'T use `requests` — use `httpx`.
- DON'T use `os.system` or `os.popen` — use `subprocess.run`.
- DON'T add new deps without confirming in pyproject.toml first.
- DON'T auto-fix security findings (ADR-005: flag-only).
- DON'T reorder transport fallback chain (`mcp` → `api` → `playwright`).
- DON'T modify step numbers without updating ALL agents + skill manifests.

---

## Common file edits

When editing any of these, also bump version + CHANGELOG:

- `sendsprint/__init__.py` → `__version__`
- `pyproject.toml` → `version = "..."`
- `README.md` → status line
- `CHANGELOG.md` → new entry (Added/Changed/Fixed/Removed/Security)

---

## Test pattern

```python
def test_<thing>_<case>(monkeypatch, tmp_path):
    def mock_run(*args, **kwargs):
        return subprocess.CompletedProcess(args[0], 0, stdout="ok", stderr="")
    monkeypatch.setattr(subprocess, "run", mock_run)
    # arrange + act + assert
```

<!-- codex-long-running-agent-overlay:start -->
## Universal Long-Running Agent Overlay

This section complements the repository-specific guidance already in this file. If anything here conflicts with the repo-specific rules above, the repo-specific rules win.

- `PRD.md` is the task source of truth for long-running sessions.
- `PROGRESS.md` is the persistent checkpoint log.
- `GOAL_RESULT.md` is the final execution report.
- Before coding, read this file, `PRD.md`, `PROGRESS.md` when it exists, `README.md`, project manifests, tests, and the relevant source folders.
- Work in small checkpoints, run the smallest relevant validation after each meaningful change, update `PROGRESS.md`, and continue until complete or genuinely blocked.
- Stop only when the requested work is complete, validation is documented, and `GOAL_RESULT.md` reflects the outcome.
- Do not rewrite unrelated architecture, fake successful validation, expose secrets, or push without explicit operator instruction for the active session.
<!-- codex-long-running-agent-overlay:end -->
