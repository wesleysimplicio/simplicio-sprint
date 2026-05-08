# Backlog — SendSprint

Lista priorizada de tudo que precisa ser feito no SendSprint. Fonte da verdade de pendências.

## Como usar este backlog

- Cada linha vira uma `task.md` ao entrar em sprint.
- Prioridades: **P0** (bloqueador), **P1** (próximas 1-2 sprints), **P2** (radar).
- Status: `todo`, `doing`, `done`.
- Ordenação: P0 → P1 → P2; dentro da mesma prioridade, por sprint alvo.

## Regras de manutenção

- Toda nova ideia entra como P2 até alguém defender priorizar.
- Itens `done` ficam no histórico por uma sprint, depois arquivados em `BACKLOG-archive.md`.
- Item parado 2 sprints como `todo` → reavalia ou remove.
- Quem altera prioridade ou move pra `doing` atualiza tabela no mesmo PR.

## Backlog atual

| #   | Título                                                               | Prioridade | Sprint alvo | Status |
| --- | -------------------------------------------------------------------- | ---------- | ----------- | ------ |
| 1   | Adopt agentic-starter pipeline (specs, skills, dod, ralph)           | P0         | sprint-1    | doing  |
| 2   | Validate Ralph autonomous loop against sprint-1 tasks                | P0         | sprint-1    | todo   |
| 3   | LLM-powered code generation per sprint item                          | P1         | sprint-2    | todo   |
| 4   | Deploy trigger + status callback to Jira/ADO ticket                  | P1         | sprint-2    | todo   |
| 5   | MCP server mode (expose SendSprint as MCP tool)                      | P1         | sprint-3    | todo   |
| 6   | Add Bun/Deno detectors to `tech/detector.py`                         | P2         | sprint-3    | todo   |
| 7   | Coverage badge + CHANGELOG automation in CI                          | P2         | sprint-4    | todo   |
| 8   | Telemetry (opt-in) for step duration histograms                      | P2         | backlog     | todo   |

## Histórico recente (últimos done)

| #   | Título                                                       | Sprint     | Concluído em |
| --- | ------------------------------------------------------------ | ---------- | ------------ |
| 0   | v0.4.0 — chat-trigger UX + 8 IDE manifests + OS-keyring     | sprint-0   | 2026-05-07   |

## Itens descartados ou movidos pra fora

- Nenhum item descartado ainda.

## Próximas decisões pendentes

- Provedor LLM padrão para item #3 (Anthropic? OpenAI? local?). Depende de ADR.
- Estratégia de retries para item #4 (idempotência do callback).
- Schema MCP do item #5 (alinhar com `mcp-server-patterns`).
