# SendSprint

<p align="center">
  <img src="./docs/assets/sendsprint-hero.png" alt="SendSprint transforma tarefas da sprint em pull requests validados" />
</p>

<p align="center">
  <a href="https://pypi.org/project/simplicio-sprint/"><img alt="PyPI" src="https://img.shields.io/pypi/v/simplicio-sprint.svg?label=pacote%20pypi"></a>
  <a href="https://pypi.org/project/simplicio-sprint/"><img alt="Versões Python" src="https://img.shields.io/pypi/pyversions/simplicio-sprint.svg"></a>
  <a href="./LICENSE"><img alt="Licença" src="https://img.shields.io/pypi/l/simplicio-sprint.svg"></a>
</p>

> 🇧🇷 Português. Read in English: [README.md](README.md).

**SendSprint é um agente autônomo que finaliza os cards atribuídos a você.**
Ele lê sua sprint no **Jira**, **Azure DevOps** ou **GitHub Issues**, reescreve
cada card no formato do
**[simplicio-mapper](https://github.com/wesleysimplicio/simplicio-mapper)**,
manda a edição de código de verdade para o
**[simplicio-cli](https://github.com/wesleysimplicio/simplicio-cli)**, coleta
evidências (testes + tela), faz commit num branch isolado e abre um **pull
request em draft** com as evidências anexadas. Depois acompanha o PR e devolve
seus comentários de review ao simplicio até você aprovar.

Você não fica no teclado invocando. Um trigger agendado roda; seu único trabalho
é **revisar o PR em draft**.

## Conteúdo

- [A divisão que faz funcionar](#a-divisão-que-faz-funcionar)
- [O fluxo completo](#o-fluxo-completo)
- [Demonstração: um card de front, ponta a ponta](#demonstração-um-card-de-front-ponta-a-ponta)
- [Instalação](#instalação)
- [Configurar credenciais](#configurar-credenciais)
- [Como invocar](#como-invocar)
- [Modo Watch (o escutador)](#modo-watch-o-escutador)
- [Os specs do simplicio-mapper](#os-specs-do-simplicio-mapper)
- [O fan-out de 600 subagentes](#o-fan-out-de-600-subagentes)
- [Manter as ferramentas atualizadas](#manter-as-ferramentas-atualizadas)
- [Instalar a skill no seu IDE / agente](#instalar-a-skill-no-seu-ide--agente)
- [Logging — registra cada etapa](#logging--registra-cada-etapa)
- [Arquitetura](#arquitetura)
- [Variáveis de ambiente](#variáveis-de-ambiente)
- [Referência de comandos](#referência-de-comandos)
- [Perguntas frequentes](#perguntas-frequentes)
- [Testes](#testes) · [Licença](#licença)

## A divisão que faz funcionar

- **SendSprint = o agente (o cérebro).** Dono do fluxo do início ao fim:
  ler → mapear → executar → evidência → commit → PR → atualizar ticket → loop de review.
- **simplicio-cli = o executor (a mão).** Sem estado. Roda *uma task → diff
  aplicado*. Não sabe o que é sprint, branch ou PR.

Essa separação é a ideia toda: o cérebro nunca escreve código, e a mão nunca
toma decisões. Cada um pode ser testado e trocado de forma independente.

## O fluxo completo

```
trigger (cron / GitHub Action / Claude web)   ← tira você do loop
  └─ SendSprint (agente)
       0. atualiza ferramentas  último simplicio-cli / -prompt / -mapper (conforme o profile)
       1. lê a sprint           Jira / Azure DevOps / GitHub   (mcp → api, --scope mine)
       2. mapeia cada card      → .specs/sprints/sprint-XX/NN-slug.task.md  (formato simplicio-mapper)
       2b. (opcional) fan-out   brainstorm de edge cases com 600 subagentes do simplicio-prompt
       3. simplicio task ...    ← a única coisa que o simplicio faz (uma task → diff)
       3b. coleta evidência     testes + screenshot Playwright
       4. commit + push         git worktree isolado, backoff limitado
       5. abre PR em DRAFT      ← sua única superfície de revisão
       6. anexa evidência       resultado dos testes + imagens embutidas
       7. atualiza o ticket     "In Review" + link do PR
       8. acompanha o PR        comentário? → simplicio ajusta → nova evidência
            ✓ você aprova → merge → próximo card

   …e cada etapa acima é gravada num arquivo de log (veja Logging).
```

## Demonstração: um card de front, ponta a ponta

Uma simulação versionada prova o fluxo inteiro para um **card de front**, sem
precisar de credenciais reais nem navegador no CI:
[`tests/test_e2e_frontend_sim.py`](./tests/test_e2e_frontend_sim.py).

```bash
pytest tests/test_e2e_frontend_sim.py -q
```

O card "**WEB-7 — Add a Login button to the homepage header**" chega do Jira
**via MCP**, e o teste percorre cada estágio:

1. **Coleta** a task do Jira (transporte MCP) → um `Sprint` com o card.
2. **Mapeia** para `.specs/sprints/sprint-42/01-add-a-login-button…task.md`
   (os critérios de aceite viram `AC-1`, `AC-2`).
3. **Executa** — a edição simulada adiciona o botão no `index.html`
   (`<a href="/login"><button>Login</button></a>`), exatamente como o simplicio aplica um diff.
4. **Evidência** — roda os testes e captura um **screenshot** commitado em
   `.sendsprint/evidence/WEB-7/screen.png`.
5. **PR** — abre um pull request em **draft** com a evidência embutida.

O "print" capturado da tela entregue:

![Evidência de entrega de front do SendSprint](./docs/assets/sendsprint-frontend-demo.png)

…e o comentário de evidência que o SendSprint posta no PR:

```markdown
## SendSprint evidence

### Steps
- [x] execute
- [x] evidence
- [x] commit

### Tests & screens
- ✅ **unit**: pytest — exit 0
- ✅ **screenshot**: homepage

  ![homepage](https://raw.githubusercontent.com/acme/web/feature/web-7/.sendsprint/evidence/WEB-7/screen.png)
```

> O teste versionado usa um PNG mínimo injetado para rodar em qualquer lugar; com
> o Playwright instalado (`pip install -e ".[screenshot]" && playwright install chromium`)
> o fluxo real captura um screenshot verdadeiro da tela — foi assim que a imagem
> acima foi gerada.

## Instalação

```bash
# 1) o próprio SendSprint (publicado no PyPI como `simplicio-sprint`)
pip install simplicio-sprint

# 2) o executor (necessário para editar código de verdade)
pip install simplicio-cli

# 3) opcional: evidência de tela com Playwright
pip install "simplicio-sprint[screenshot]" && playwright install chromium

# 4) opcional mas recomendado: pega o último de cada ferramenta externa
#    (também instala o kernel do simplicio-prompt usado pelo --fanout)
sendsprint update
```

Trabalhando no próprio agente? Clone o repo e use `pip install -e ".[dev]"`.

Requisitos: **Python ≥ 3.11** e **git**. O `sendsprint update` também precisa de
`git` no PATH para clonar os auxiliares simplicio-prompt / simplicio-mapper.

## Configurar credenciais

As credenciais vêm do keyring do SO (via `sendsprint login`) ou de variáveis de
ambiente. Você só precisa da(s) fonte(s) que realmente usa.

```bash
# armazenamento único no keyring
sendsprint login jira           # pede email + API token
sendsprint login azuredevops    # pede organização + PAT
# GitHub usa a variável de ambiente GITHUB_TOKEN — sem entrada no keyring
```

Ou por variáveis de ambiente — veja [Variáveis de ambiente](#variáveis-de-ambiente).

## Como invocar

Há dois jeitos: **direto pelo CLI** ou **pedindo a um agente de IA** (Claude
Code, Codex, Cursor, …) que tenha a skill do SendSprint instalada.

### A) Direto, pelo CLI

```bash
# sprint 42 do Jira
sendsprint run jira 42 --repo . --repo-slug owner/repo --scope mine

# iteração do Azure DevOps (repare na barra invertida escapada)
sendsprint run azuredevops "Team\\Sprint 12" --repo . --repo-slug repoId

# milestone #7 do GitHub (ou "*" para todas as issues abertas atribuídas a você)
sendsprint run github 7 --repo . --repo-slug owner/repo --scope mine
```

O que cada argumento significa:

| Argumento | Significado |
|---|---|
| `<source>` | `jira` \| `azuredevops` \| `github` |
| `<sprint>` | id da sprint Jira, caminho de iteração ADO, ou milestone GitHub (`*` = todas abertas) |
| `--repo` | caminho do repositório git alvo |
| `--repo-slug` | `owner/repo` (GitHub) ou id do repositório (Azure DevOps) — usado no PR |
| `--scope mine` | entrega só os cards atribuídos a você (`all` para a sprint inteira) |
| `--base` | branch alvo do PR (padrão `develop`) |
| `--fanout` | roda o brainstorm de 600 subagentes por card (opt-in) |
| `--no-specs` | pula a escrita do arquivo `.specs/` do simplicio-mapper |
| `-o report.json` | grava o relatório completo do run em JSON |

### B) Pedindo a um agente de IA

Se a skill estiver instalada (veja
[Instalar a skill](#instalar-a-skill-no-seu-ide--agente)), o assistente **nunca
reimplementa o fluxo — ele chama o CLI `sendsprint`**. Estas frases disparam:

- 🇧🇷 "rode o sendsprint", "executar sprint", "entregar sprint"
- 🇺🇸 "run sendsprint", "ship my sprint", "deliver my sprint"
- 🇪🇸 "ejecutar sprint"
- o comando de barra `/sendsprint`
- ou simplesmente citar id da sprint + fonte + repo juntos

Quando seus servidores MCP (Atlassian / Azure DevOps / GitHub) estão
disponíveis, o agente os registra para os operadores lerem o estado real via
MCP; caso contrário, os operadores caem na API REST automaticamente.

## Modo Watch (o escutador)

O modo watch é como o SendSprint **roda sem você no teclado**. Ele consulta a
fonte, entrega os cards que ainda não entregou, e lembra o que já mandou para
nunca duplicar trabalho.

```bash
# uma passada e sai — é o que um cron / GitHub Action / trigger agendado chama
sendsprint watch jira 42 --repo . --repo-slug owner/repo --once

# fica vivo e roda uma passada a cada 15 minutos (Ctrl-C para parar)
sendsprint watch jira 42 --repo . --repo-slug owner/repo --interval 15

# no máximo N cards por ciclo (padrão 1 — PRs pequenos e revisáveis)
sendsprint watch github "*" --repo . --repo-slug owner/repo --once --max-per-cycle 3
```

Como ele se comporta:

- Sempre escopa para os **seus** cards (`--scope mine`).
- As chaves dos cards entregues ficam em **`.sendsprint/runs/watch-state.json`**;
  a próxima passada pula esses. Apague o arquivo para reentregar.
- `--once` faz um único ciclo e sai com código diferente de zero se alguma etapa
  falhar (ideal para CI). Sem `--once` ele roda em loop, um ciclo a cada
  `--interval` minutos, e **continua vivo mesmo se um ciclo falhar** (o erro vai
  para o log).
- Cada card entregue ainda para num **PR em draft** — o watch nunca faz merge.

### Agendando

Rode `sendsprint watch ... --once` a partir de:

- um **GitHub Action** agendado — veja
  [`.github/workflows/sendsprint.yml`](./.github/workflows/sendsprint.yml);
- um **cron**;
- um **trigger agendado do Claude Code on the web**
  ([docs](https://code.claude.com/docs/en/claude-code-on-the-web)).

Você também pode ficar de olho no PR depois de aberto: um agente inscrito na
atividade do PR reage aos comentários de review rodando o loop de revisão
(abaixo).

## Os specs do simplicio-mapper

Antes de entregar um card ao simplicio-cli, o SendSprint o escreve no formato do
[simplicio-mapper](https://github.com/wesleysimplicio/simplicio-mapper) dentro
do worktree, para o executor ter contexto rico e estruturado:

```
.specs/sprints/
├── BACKLOG.md
└── sprint-XX/
    ├── SPRINT.md
    └── NN-slug.task.md     # frontmatter + Acceptance Criteria, Test plan, Definition of Done
```

Cada arquivo de task carrega título, descrição, critérios de aceite (convertidos
em `AC-1`, `AC-2`, …), labels e link do ticket. Desligue com `--no-specs`.

## O fan-out de 600 subagentes

Opcionalmente, antes de implementar um card, o SendSprint pode espalhar a task
por **centenas de subagentes reais** via
[simplicio-prompt](https://github.com/wesleysimplicio/simplicio-prompt) para
levantar edge cases e um plano, e então funde o resultado na task do simplicio.

```bash
# 600 subagentes por card (precisa do kernel + chave de provider)
sendsprint run jira 42 --repo . --repo-slug owner/repo --fanout

# prévia de custo offline — sem chave de API, sem rede
sendsprint run jira 42 --repo . --repo-slug owner/repo --fanout --fanout-dry-run
```

É **opt-in** e **degrada com elegância**: sem kernel ou chave, registra uma etapa
`skipped` e segue. O `sendsprint update` instala o kernel e aponta o
`SIMPLICIO_PROMPT_KERNEL` para ele automaticamente.

## Manter as ferramentas atualizadas

`sendsprint update` pega o último de cada parte móvel:

```bash
sendsprint update                 # as três
sendsprint update --no-mapper     # pula o simplicio-mapper
```

| Ferramenta | Como atualiza |
|---|---|
| simplicio-cli | `pip install -U simplicio-cli` |
| simplicio-prompt | git clone/pull no cache, define `SIMPLICIO_PROMPT_KERNEL` |
| simplicio-mapper | git clone/pull no cache |

O `run` e o `watch` também atualizam no início, conforme o seu profile de runtime
(`~/.config/sendsprint/profile.yaml`). Pule por execução com `--no-update`, ou
globalmente com `SENDSPRINT_NO_UPDATE=1`.

## Instalar a skill no seu IDE / agente

`sendsprint install` escreve a skill do SendSprint na convenção de cada agente, a
partir de uma fonte única, para as frases-gatilho funcionarem em todo lugar.

```bash
sendsprint install --all                 # todos os agentes suportados
sendsprint install -t cursor -t claude    # só esses
sendsprint install --all --repo /caminho/do/projeto
```

| Agente | Onde a skill é escrita |
|---|---|
| Claude Code | `.claude/skills/sendsprint/SKILL.md` |
| Cursor | `.cursor/rules/sendsprint.mdc` |
| Kiro | `.kiro/steering/sendsprint.md` |
| Gemini | `GEMINI.md` (bloco gerenciado) |
| Codex / OpenCode / Antigravity | `AGENTS.md` (bloco gerenciado) |
| Hermes / openclaw | `AGENTS.md` (bloco gerenciado — fallback) |

Arquivos compartilhados (`AGENTS.md`, `GEMINI.md`) recebem um **bloco gerenciado
idempotente** entre marcadores, então reexecutar nunca sobrescreve seu conteúdo.

## Logging — registra cada etapa

Todo comando configura o logger `sendsprint` para um **arquivo de log rotativo**
(detalhe DEBUG completo) mais o console. O log registra cada etapa da entrega,
toda invocação do simplicio / fan-out, escolhas de transporte e erros.

```bash
# opções globais (antes do subcomando)
sendsprint --log-level DEBUG run jira 42 --repo . --repo-slug owner/repo
sendsprint --log-json --log-file ./run.jsonl run github "*" --repo .
```

- Local padrão: `~/.local/state/sendsprint/logs/sendsprint.log` (mude com
  `SENDSPRINT_LOG_DIR`).
- `--log-json` grava um objeto JSON por linha (fácil de ingerir).
- O `run` também arquiva o `RunReport` completo em JSON ao lado dos logs
  (`run-<timestamp>.report.json`).

## Arquitetura

```
sendsprint/
├── operators/      leitores de tasks: JiraOperator, AzureDevopsOperator, GitHubIssuesOperator (mcp|api)
│   └── _mcp_bridge.py  seam MCP injetado pelo host (register_provider → fetch)
├── executor/       SimplicioExecutor — a fronteira com o simplicio-cli (task → diff aplicado)
├── mapper/         MapperAdapter — renderiza um Sprint nos specs .specs/ do simplicio-mapper
├── prompt/         PromptFanout — fan-out de subagentes do simplicio-prompt (--subagents 600)
├── delivery/       worktree, git_ops (commit+push), evidence (testes+telas), pr (cria+review)
├── models/         Sprint, SprintItem, StepReport, RunReport, ScopeConfig (Pydantic v2)
├── github_integration.py  ReviewReader (feedback do PR) + comentário de evidência + CI
├── scope.py        filtragem --scope mine
├── bootstrap.py    sendsprint update (pega o último das ferramentas) + checagens no início
├── installer.py    sendsprint install (escreve a skill por agente)
├── logging_setup.py  logging central (arquivo + console, JSON opcional)
├── flow.py         o orquestrador (ler → mapear → simplicio → evidência → PR → loop de review)
├── watch.py        o trigger desatendido
└── cli.py          CLI Typer: run, watch, update, install, login, logout, version
```

## Variáveis de ambiente

| Variável | Para |
|---|---|
| `JIRA_BASE_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` | Jira |
| `AZURE_DEVOPS_ORG`, `AZURE_DEVOPS_PROJECT`, `AZURE_DEVOPS_PAT` | Azure DevOps |
| `GITHUB_TOKEN`, `GITHUB_REPO` | GitHub Issues + PRs |
| `SIMPLICIO_MODEL`, `SIMPLICIO_BASE_URL`, `SIMPLICIO_TEST_CMD` | simplicio-cli |
| `SIMPLICIO_PROMPT_KERNEL` | caminho do kernel do fan-out (definido pelo `sendsprint update`) |
| `SENDSPRINT_CACHE_DIR` | onde ficam as ferramentas clonadas (padrão `~/.cache/sendsprint`) |
| `SENDSPRINT_LOG_DIR` | onde ficam os logs (padrão `~/.local/state/sendsprint/logs`) |
| `SENDSPRINT_NO_UPDATE` | defina como `1` para pular a atualização no início |
| `SENDSPRINT_CONFIG_DIR` | local do profile (padrão `~/.config/sendsprint`) |

## Referência de comandos

| Comando | O que faz |
|---|---|
| `sendsprint run <source> <sprint>` | entrega a sprint: cada card → simplicio → evidência → PR draft |
| `sendsprint watch <source> <sprint>` | trigger desatendido; `--once` para cron/CI, senão em loop |
| `sendsprint update` | pega o último simplicio-cli / -prompt / -mapper |
| `sendsprint install --all` | escreve a skill em todos os agentes suportados |
| `sendsprint login <provider>` | guarda credenciais no keyring do SO |
| `sendsprint logout <provider> <account>` | remove uma credencial guardada |
| `sendsprint version` | mostra a versão |

Opções globais (antes do subcomando): `--log-level`, `--log-file`, `--log-json`.

## Perguntas frequentes

**Preciso do simplicio-cli instalado?**
Para editar código de verdade, sim (`pip install simplicio-cli`). Sem ele, a
etapa de execução é reportada como `skipped` e nenhum diff é gerado — o resto do
fluxo ainda roda para você ver a engrenagem.

**E se eu não tiver servidor MCP do Jira/ADO/GitHub?**
Sem problema. O transporte é `auto`: tenta MCP primeiro (quando o host registra
um provider) e cai na API REST. Configure as credenciais REST e está tudo certo.

**Ele faz merge ou push na minha branch principal?**
Não. Ele empurra o trabalho para uma **branch isolada** e abre um **PR em draft**.
Você revisa e faz merge. O watch é igual — sempre para no PR draft.

**Ele mexe em arquivos fora da task?**
O executor é restrito a "mexer só no que a task exige; manter os testes verdes".
O mapper só escreve em `.specs/`. O instalador de skill só escreve nos arquivos
dedicados ou num bloco marcado em `AGENTS.md`/`GEMINI.md`.

**O fan-out de 600 subagentes é obrigatório?**
Não — é opt-in (`--fanout`) e pula com elegância sem kernel/chave. Use
`--fanout-dry-run` para prever o custo offline.

**Um revisor deixou um comentário — o que acontece?**
O loop de review lê o feedback acionável, roda o simplicio de novo para resolver,
recoleta evidência fresca, e dá push — repetindo até você aprovar. Um agente
inscrito na atividade do PR pode conduzir isso automaticamente.

**Onde vejo o que aconteceu?**
No arquivo de log (`~/.local/state/sendsprint/logs/sendsprint.log`) e no
`RunReport` JSON arquivado. Use `--log-level DEBUG` para detalhe completo.

**Como reentrego um card que o watch já mandou?**
Apague a chave dele (ou o arquivo) em `.sendsprint/runs/watch-state.json`.

## Testes

```bash
pip install -e ".[dev]"
pytest tests/ -q
ruff check sendsprint/ && ruff format sendsprint/
```

## Licença

MIT — veja [LICENSE](./LICENSE).
