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
| 1   | Adopt agentic-starter pipeline (specs, skills, dod, ralph)           | P0         | sprint-1    | done   |
| 2   | Validate Ralph autonomous loop against sprint-1 tasks                | P0         | sprint-1    | doing  |
| 3   | LLM-powered code generation per sprint item                          | P1         | sprint-2    | done   |
| 4   | Deploy trigger + status callback to Jira/ADO ticket                  | P1         | sprint-2    | done   |
| 5   | MCP server mode (expose SendSprint as MCP tool)                      | P1         | sprint-3    | done   |
| 6   | Add Bun/Deno detectors to `tech/detector.py`                         | P2         | sprint-3    | done   |
| 7   | Coverage badge + CHANGELOG automation in CI                          | P2         | sprint-4    | done   |
| 8   | Telemetry (opt-in) for step duration histograms                      | P2         | backlog     | done   |
| 9   | Real PyPI trusted publishing                                         | P0         | sprint-5    | todo   |
| 10  | `sendsprint doctor` readiness command                                | P0         | sprint-5    | todo   |
| 11  | Full dry-run execution plan                                          | P0         | sprint-5    | todo   |
| 12  | Per-task worktree isolation                                          | P0         | sprint-5    | todo   |
| 13  | Evidence bundle for every autonomous run                             | P0         | sprint-5    | todo   |
| 14  | GitHub Issues as a first-class tracker                               | P1         | sprint-6    | todo   |
| 15  | Configurable autonomy policy                                         | P1         | sprint-6    | todo   |
| 16  | Native Ralph Wiggum and Codex Goal loop semantics                    | P1         | sprint-6    | todo   |
| 17  | Stack templates for Angular, React, Vue.js, Node.js and common stacks | P1         | sprint-6    | todo   |
| 18  | Local dashboard for sprint execution                                 | P1         | sprint-7    | todo   |
| 19  | Extract project tasks from meeting transcripts                       | P1         | sprint-7    | todo   |
| 20  | Sprint Autopilot demo                                                | P2         | sprint-7    | todo   |
| 21  | Executive report output                                              | P2         | sprint-7    | todo   |
| 22  | Multi-agent control plane                                            | P2         | sprint-8    | todo   |

## Issues GitHub criadas para o roadmap

- [#27](https://github.com/wesleysimplicio/SendSprint/issues/27) — Release: restore PyPI trusted publishing
- [#28](https://github.com/wesleysimplicio/SendSprint/issues/28) — CLI: add `sendsprint doctor` readiness command
- [#29](https://github.com/wesleysimplicio/SendSprint/issues/29) — Dry-run: generate full execution plan
- [#30](https://github.com/wesleysimplicio/SendSprint/issues/30) — Execution: isolate each task in its own worktree
- [#31](https://github.com/wesleysimplicio/SendSprint/issues/31) — Evidence: bundle run artifacts for audit and review
- [#32](https://github.com/wesleysimplicio/SendSprint/issues/32) — Tracker: make GitHub Issues first-class
- [#33](https://github.com/wesleysimplicio/SendSprint/issues/33) — Policy: add configurable autonomy levels
- [#34](https://github.com/wesleysimplicio/SendSprint/issues/34) — Loop: model Ralph Wiggum and Codex Goal semantics
- [#35](https://github.com/wesleysimplicio/SendSprint/issues/35) — Templates: ship stack-specific validation recipes
- [#36](https://github.com/wesleysimplicio/SendSprint/issues/36) — Dashboard: add local sprint execution view
- [#37](https://github.com/wesleysimplicio/SendSprint/issues/37) — Demo: build Sprint Autopilot reference scenario
- [#38](https://github.com/wesleysimplicio/SendSprint/issues/38) — Reports: generate executive sprint summaries
- [#39](https://github.com/wesleysimplicio/SendSprint/issues/39) — Control plane: coordinate multi-agent execution safely
- [#40](https://github.com/wesleysimplicio/SendSprint/issues/40) — Ingest: extract project tasks from meeting transcripts

## Histórico recente (últimos done)

| #   | Título                                                       | Sprint     | Concluído em |
| --- | ------------------------------------------------------------ | ---------- | ------------ |
| 8   | Telemetry (opt-in) for step duration histograms              | backlog    | 2026-05-18   |
| 6   | Add Bun/Deno detectors to `tech/detector.py`                 | sprint-3   | 2026-05-18   |
| 5   | MCP server mode (expose SendSprint as MCP tool)              | sprint-3   | 2026-05-18   |
| 4   | Deploy trigger + status callback to Jira/ADO ticket          | sprint-2   | 2026-05-18   |
| 3   | LLM-powered code generation per sprint item                  | sprint-2   | 2026-05-18   |
| 1   | Adopt agentic-starter pipeline (specs, skills, dod, ralph)  | sprint-1   | 2026-05-18   |
| 0   | v0.4.0 — chat-trigger UX + 8 IDE manifests + OS-keyring     | sprint-0   | 2026-05-07   |

## Itens descartados ou movidos pra fora

- Nenhum item descartado ainda.

## Próximas decisões pendentes

- Validar o loop autônomo no `llm-project-mapper` usando a skill Ralph Wiggum do Claude Code e o `/goal` do Codex para o item #2.
- Converter o roadmap de Sprint Autopilot em sprints executáveis, começando pelos itens P0 em `docs/roadmap/sprint-autopilot-roadmap.md`.
