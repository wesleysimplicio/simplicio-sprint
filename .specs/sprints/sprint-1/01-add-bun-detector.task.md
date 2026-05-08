---
id: TASK-001
title: Add Bun runtime marker to tech detector
sprint: sprint-1
owner: @sendsprint-core
status: todo
---

# TASK-001 — Add Bun runtime marker to tech detector

## Contexto

`sendsprint/tech/detector.py` mapeia 25+ stacks via marcadores no filesystem (presença de `package.json`, `pyproject.toml`, `Cargo.toml`, etc.) mas não reconhece projetos Bun (`bun.lockb` + `bunfig.toml`). Times que usam Bun caem no detector Node genérico, o que faz o `dev` agent (`agents/dev.py`) tentar `npm install` no lugar de `bun install`. Origem: item #6 do `BACKLOG.md` (priorizado para sprint-1 por ser baixo risco e validar o pipeline Ralph contra mudança real de domínio).

Impactados:

- `sendsprint/tech/detector.py` — adicionar `bun` em `KNOWN_TECHS` e classificá-lo em `BACK_TECHS`.
- `sendsprint/agents/dev.py` — comando install/build (`bun install`, `bun run build`).
- `sendsprint/agents/lint_runner.py` — usar `bun x eslint .` quando detectado bun + presença de `eslint`.
- `sendsprint/agents/test_runner.py` — `bun test` como runner unit.
- `tests/test_tech_detector.py` e `tests/test_agents.py` — fixtures e asserts.

## Acceptance Criteria

- [ ] AC-1 — Quando `repo/bun.lockb` existe, `detect_tech(path)` retorna `["bun"]` com confidence ≥ 0.9.
- [ ] AC-2 — Quando `bun.lockb` + `package.json` coexistem, `bun` ganha sobre `node` (mais específico).
- [ ] AC-3 — `DevAgent.install_and_build()` em repo bun roda `bun install` seguido de `bun run build` se script existe; senão pula build com `StepReport.status="skipped"` + `details.reason="no build script"`.
- [ ] AC-4 — `LintRunner` em repo bun com config eslint roda `bun x eslint .` e retorna `StepReport` com `findings` parseados.
- [ ] AC-5 — `TestRunner` em repo bun roda `bun test` e parseia resultado JSON.
- [ ] AC-6 — Quando binário `bun` ausente do PATH, todos os agents retornam `StepReport.status="skipped"` com `details.reason="bun not installed"` (mock fallback do AGENTS.md §5).

## Out of scope

- Não inclui detecção de Deno (`deno.json`) — fica para TASK-XXX da sprint-3.
- Não altera fluxo `mcp → api → playwright` dos operators.
- Não publica nova versão major: bump é minor (`0.4.0 → 0.5.0`) por ser feature backwards-compatible.
- Não cria ADR — patrón de adicionar tech está documentado em `AGENTS.md §5` (não é decisão arquitetural nova).

## Test plan

### Unit

- [ ] `test_detector_bun_only` — fixture com só `bun.lockb` retorna `["bun"]`.
- [ ] `test_detector_bun_wins_over_node` — fixture com `bun.lockb` + `package.json` retorna `bun` antes de `node`.
- [ ] `test_dev_agent_bun_install` — monkeypatch `subprocess.run` para `bun install`, assertar comando exato.
- [ ] `test_dev_agent_bun_skipped_no_binary` — `subprocess.run` levanta `FileNotFoundError`, retorna `StepReport(status="skipped")`.
- [ ] `test_lint_runner_bun_eslint` — fixture com `eslint.config.js`, assertar `bun x eslint .` chamado.
- [ ] `test_test_runner_bun_test` — assertar `bun test --reporter=json` e parse de saída.
- [ ] Cobertura mínima 85% em `sendsprint/tech/detector.py` e arquivos tocados em `sendsprint/agents/`.

### Integration

- [ ] `test_flow_bun_repo` — `SprintFlow.run()` com fixture `tests/fixtures/bun-app/` (apenas `bun.lockb` + `package.json` mínimo) atravessa steps 3-5 sem erro.
- [ ] Validar contrato `StepReport(step=3, name="Dev", status="ok", details={"runtime": "bun", ...})`.

### End-to-end (Playwright fallback)

N/A — esta task não toca o transport `playwright` dos operators.

```bash
ruff check sendsprint/
ruff format --check sendsprint/
pytest tests/test_tech_detector.py tests/test_agents.py -v --cov=sendsprint/tech --cov=sendsprint/agents --cov-report=term-missing
```

## Definition of Done

- [ ] Todos os ACs marcados.
- [ ] `pytest tests/ -v` 100% verde local e CI.
- [ ] Coverage do diff ≥ 80% (gate `dod.yml`).
- [ ] `ruff check` e `ruff format --check` limpos.
- [ ] Versão bumpada para `0.5.0` em `sendsprint/__init__.py`, `pyproject.toml`, `README.md` (linha de status), `CHANGELOG.md`.
- [ ] PR aberto referenciando esta task (`Closes .specs/sprints/sprint-1/01-add-bun-detector.task.md`).
- [ ] Code review aprovado por 1 revisor.
- [ ] Status atualizado em `BACKLOG.md` (#6 → done) e `SPRINT.md`.

## Pegadinhas conhecidas

- `bun.lockb` é binário (não texto). Não tente parsear conteúdo — só checar existência.
- `bun test` saída JSON difere de `jest`/`vitest`: campo `tests` é flat, sem `numFailedTests`. Conferir parser.
- Em CI sem `bun` instalado, gate de coverage não pode quebrar — usar fallback `skipped` e marcar como pass.
- `DevAgent` precisa ler `package.json` para checar `scripts.build` antes de chamar `bun run build`.

## Links

- Backlog: `.specs/sprints/BACKLOG.md` (item #6)
- Sprint: `.specs/sprints/sprint-1/SPRINT.md`
- Padrão de adicionar tech: `AGENTS.md` §5 ("Adding a new tech to detector")
- Detector atual: `sendsprint/tech/detector.py`
- Agent dev: `sendsprint/agents/dev.py`
- Issue: `#<numero>` (criar ao iniciar)
- PR: `#<numero>` (preencher ao abrir)
