---
id: TASK-XXX
title: <Título curto e imperativo>
sprint: sprint-XX
owner: <handle do responsável ou @sendsprint-core>
status: todo
---

# TASK-XXX — <Título curto e imperativo>

> Use este arquivo como modelo para criar novas tasks dentro de uma sprint do SendSprint. Copie, renomeie para `NN-slug.task.md` (ex: `02-add-deno-detector.task.md`) e preencha cada section. Não apague seções: se não se aplica, escreva "N/A" e justifique em uma linha.

## Contexto

Descreva em 3-6 linhas:

- O problema que esta task resolve no fluxo de 10 passos do SendSprint.
- Qual agente/operador/módulo é impactado (`operators/`, `agents/`, `architecture/`, `tech/`, `flow/`, `cli.py`).
- Por que agora (link com objetivo da sprint em `SPRINT.md`).
- Referência ao item de origem no `BACKLOG.md` (`#N`).

## Acceptance Criteria

Critérios objetivamente verificáveis. Cada item deve poder ser confirmado com um teste pytest, um log estruturado ou um StepReport.

- [ ] AC-1 — Quando <condição/input>, o sistema deve <comportamento esperado>.
- [ ] AC-2 — Quando <erro/edge case>, o `StepReport.status` deve ser `failed` com `details` explicando a causa.
- [ ] AC-3 — A função/CLI exibe <estado/saída> em modo verbose.
- [ ] AC-4 — A operação completa em até <tempo/sla> sob <volume>.

## Out of scope

Liste o que **não** será feito nesta task.

- Não inclui <feature relacionada> — fica para a task TASK-YYY.
- Não altera o contrato dos modelos Pydantic existentes — depende de ADR.
- Não cobre <edge case raro> — abrir item separado no backlog se aparecer.

## Test plan

### Unit

- [ ] Cobrir <regra de domínio principal> com casos válidos e inválidos.
- [ ] Mockar dependências externas (`httpx.Client.request`, `subprocess.run`) com `monkeypatch`.
- [ ] Cobrir caminho feliz + ao menos 1 fallback (transport degradado, ferramenta ausente).
- [ ] Atingir cobertura mínima de 80% nos arquivos novos/alterados.

### Integration

- [ ] Testar interação entre <operador/agente> e <módulo dependente> usando fixtures pytest.
- [ ] Validar contrato de I/O dos modelos `Sprint`, `SprintItem`, `StepReport`, `RunReport`.
- [ ] Cobrir caminho feliz + 1 caminho de erro (rede caiu, token inválido).

### End-to-end (Playwright fallback)

> Aplicável quando a task afeta o transport `playwright` de um operator (Jira/ADO).

- [ ] Cenário feliz: operator lê sprint via Playwright contra fixture HTML/CDP local.
- [ ] Cenário de erro: página de login expirada, token revogado, 5xx.
- [ ] Evidências (screenshot, trace) salvas em `test-results/` e anexadas ao PR.

```bash
ruff check sendsprint/
ruff format --check sendsprint/
pytest tests/ -v --cov=sendsprint --cov-report=term-missing
# se afeta playwright fallback:
pytest tests/e2e/ -v
```

## Definition of Done

- [ ] Todos os ACs marcados e verificados.
- [ ] `pytest tests/ -v` 100% verde local e no CI.
- [ ] Coverage do diff ≥ 80% (`.github/workflows/dod.yml`).
- [ ] `ruff check` e `ruff format --check` limpos.
- [ ] Versão bumpada nos 4 lugares (`sendsprint/__init__.py`, `pyproject.toml`, `README.md`, `CHANGELOG.md`).
- [ ] PR aberto referenciando esta task e ADR aplicável.
- [ ] Code review aprovado por 1 revisor.
- [ ] Mudança de schema/contract registrada em ADR (`.specs/architecture/ADR-XXX-*.md`).
- [ ] Status atualizado em `BACKLOG.md` e em `sprint-XX/SPRINT.md`.

## Pegadinhas conhecidas

- Transport fallback é fixo: `mcp` → `api` → `playwright`. Não reordenar.
- Worktree cria git worktree real; teste usa `tempfile.TemporaryDirectory()` para limpar.
- Fix loop tem cap de 3 iterações — passar disso vira `failed`.
- Security reviewer é flag-only: NUNCA auto-corrigir secrets.
- Step numbers em `StepReport(step=N, ...)` precisam refletir ordem do flow.

## Links

- Backlog: `.specs/sprints/BACKLOG.md` (item #N)
- Sprint: `.specs/sprints/sprint-XX/SPRINT.md`
- Vision/Domain: `.specs/product/VISION.md`, `.specs/product/DOMAIN.md`
- Arquitetura: `.specs/architecture/DESIGN.md`, `.specs/architecture/PATTERNS.md`
- ADRs relacionadas: `ADR-XXX-<slug>.md`
- Issue: `#<numero>`
- PR: `#<numero>` (preencher após abrir)
