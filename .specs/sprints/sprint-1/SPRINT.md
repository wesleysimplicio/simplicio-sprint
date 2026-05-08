---
sprint: sprint-1
status: doing
start: 2026-05-08
end: 2026-05-22
owner: @sendsprint-core
---

# Sprint 1 — Agentic-starter pipeline + Ralph autonomous loop

## Objetivo

Adotar o padrão `agentic-starter` no SendSprint (specs/sprints, skills, DoD gate) e validar o Ralph como loop autônomo contra duas tasks pilotos sem dependência externa (Jira/ADO). Resultado: contribuidores e agents seguem um único contrato e o pipeline `ralph run` consegue executar uma sprint até verde.

## Datas

- **Início:** 2026-05-08
- **Fim previsto:** 2026-05-22
- **Demo/review:** 2026-05-21
- **Retrospectiva:** 2026-05-22

## Deliverables

A sprint só fecha como `done` quando os 4 entregáveis estão cumpridos:

1. **`.specs/sprints/` ativo** — `task-template.md`, `BACKLOG.md` e `sprint-1/SPRINT.md` em uso. Toda task nova obrigatoriamente segue o template.
2. **DoD gate** — `.github/workflows/dod.yml` adaptado para Python (ruff + pytest + coverage ≥ 80% + checagem de referência a task) bloqueia merge.
3. **Ralph configurado** — `.ralph/config.toml` com `adapter=claude`, sprint-1 reconhecida como entrada, `ralph run --max-iterations 5` roda fim a fim sem erro.
4. **2 tasks pilotos verdes** — `01-add-bun-detector.task.md` e `02-add-cargo-audit-tests.task.md` saem de `todo` para `done` com tests + cobertura + PR.

## Tasks da sprint

| Arquivo                                       | Status | Owner                  |
| --------------------------------------------- | ------ | ---------------------- |
| `01-add-bun-detector.task.md`                 | todo   | @sendsprint-core       |
| `02-add-cargo-audit-tests.task.md`            | todo   | @sendsprint-core       |

## Riscos

- **Ralph pode entrar em loop infinito** se não reconhecer DoD verde. Mitigação: `--max-iterations 5` cap + revisão manual antes de merge.
- **Cobertura ≥ 80%** pode quebrar PRs antigos. Mitigação: aplicar gate só em arquivos do diff (não no total).
- **Adapter Claude do Ralph** depende de `ANTHROPIC_API_KEY` no env do dev. Mitigação: documentar em `.env.example`.

## Dependências

- Ralph 0.1.14 instalado globalmente (`~/.nvm/versions/node/v18.20.8/bin/ralph`).
- `pytest`, `pytest-cov`, `ruff` no `[dev]` extras de `pyproject.toml`.
- ADR a abrir se `dod.yml` mudar contrato com PRs já abertos.

## Critérios de pronto da sprint

- [ ] As 2 tasks com status `done` no `BACKLOG.md`.
- [ ] CI verde nos PRs de ambas as tasks.
- [ ] Ralph completa `ralph run --max-iterations 5` sem erro de configuração.
- [ ] Demo registrada em `presentation/` (opcional).
- [ ] Retrospectiva preenchida ao fim.

## Notas de retrospectiva (preencher no fim)

- O que funcionou bem:
- O que travou:
- O que mudar na sprint-2:
