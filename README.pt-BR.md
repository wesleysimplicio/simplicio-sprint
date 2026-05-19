# SendSprint

![Coverage](./docs/assets/coverage-badge.svg)

> 🇧🇷 Versão em português. Read this in English: [README.md](README.md).

SendSprint e um **utilitario pessoal de entrega autonoma sprint-para-PR** — um pacote open-source publico que voce instala na sua propria maquina e autoriza contra os repos onde voce ja trabalha. Ele le itens da sprint no Jira ou Azure DevOps, mapeia a arquitetura alvo, cria branches/worktrees isolados, builda, testa, valida seguranca, captura evidencias, comita, abre pull requests, revisa o diff e reporta o estado da entrega em um fluxo controlado com geracao de codigo por LLM e callback de deploy opt-in.

**Nao tem servico hospedado, nao tem SaaS, nao tem billing nem assinatura.** Tudo roda local sob seu controle: credenciais ficam no keyring do SO, trabalho acontece em worktrees no seu disco, e qualquer acao contra um projeto da empresa e autorizada pelo operador que iniciou a execucao. O repo continua publico no GitHub pra quem quiser instalar do mesmo jeito — mas o fluxo e seu, nao produto de ninguem.

A proposta e simples: remover o custo de coordenacao manual entre backlog, codigo, testes, evidencia e PR. O SendSprint cria uma esteira repetivel da sprint ate `develop` pra um unico engenheiro, com preflight, dry-run, execucao resumivel, branch por task e saida auditavel.

## Visuais de produtividade

### Sem vs. com SendSprint

![Sem vs. com SendSprint](./docs/assets/sendsprint-productivity-before-after.png)

### SendSprint como motor de entrega

![Motor de produtividade SendSprint](./docs/assets/sendsprint-productivity-engine.png)

## 🎬 Vídeos

### Produtividade antes/depois (47s)

![Poster SendSprint antes e depois](./video/preview/sendsprint-before-after-poster-pt.png)

<p align="center">
  <a href="./video/preview/sendsprint-before-after-pt.mp4">▶️ MP4 em português (1920×1080, 47s, 7.1 MB)</a>
  &nbsp;·&nbsp;
  <a href="./video/preview/sendsprint-before-after-en.mp4">🇺🇸 MP4 em inglês (1920×1080, 47s, 7.1 MB)</a>
</p>

### Explicacao do produto (56s)

![Prévia do vídeo SendSprint](./video/preview/sendsprint-preview.gif)

<p align="center">
  <a href="./video/preview/sendsprint-explainer.mp4">▶️ MP4 completo (1920×1080, 56s, 20 MB)</a>
  &nbsp;·&nbsp;
  <a href="./video/preview/poster.png">🖼️ Poster</a>
</p>

### Demo do run loop (22s) — o que o `web/RunScreen` mostra

![Run loop SendSprint](./video/preview/runloop-preview.gif)

<p align="center">
  <a href="./video/preview/runloop.mp4">▶️ MP4 completo (1920×1080, 22s, 5.5 MB)</a>
  &nbsp;·&nbsp;
  <a href="./video/">🛠️ Código-fonte (Remotion)</a>
</p>

> 🇺🇸 English versions of these videos: see [README.md](README.md).

## Apresentacoes

Decks executivos da implementacao estao disponiveis em formato editavel e PDF:

- [PPTX em ingles](./docs/presentations/sendsprint-implementation-en.pptx) · [PDF em ingles](./docs/presentations/sendsprint-implementation-en.pdf)
- [PPTX em portugues](./docs/presentations/sendsprint-implementation-pt-BR.pptx) · [PDF em portugues](./docs/presentations/sendsprint-implementation-pt-BR.pdf)
- [Previews dos slides](./docs/presentations/README.md)

Os MP4s são gerados localmente pelo Remotion com trilha musical e efeitos sonoros de workflow (`cd video && npm run build:preview`).
O do run loop mostra exatamente o que acontece no navegador quando você abre
`http://localhost:8081` e clica "Iniciar entrega": round 1 falha com regressão
visual, fix-loop aplica patches, round 2 fica verde, PR abre.

## 🌐 Rodar no navegador (web)

```bash
# 1) backend
pip install -e ".[api]"
python -m sendsprint.api          # http://localhost:8765

# 2) web UI (outro terminal)
cd web && npm install && npm run dev   # http://localhost:8081
```

Veja [`web/README.md`](./web/README.md) pro passo-a-passo e
[`sendsprint/api/README.md`](./sendsprint/api/README.md) pra API HTTP/SSE.


Funciona em **13 ferramentas de IA pra código**: Claude Code, Codex CLI, GitHub Copilot, Cursor, Windsurf, Kiro, Zed, Cline, Continue, Aider, Sourcegraph Cody, Hermes, Openclaw.

> **Status:** v0.16.0 — Watcher do Sprint Autopilot. `sendsprint watch` monitora Jira/Azure DevOps por tasks elegiveis atribuidas ao operador, deduplica por revision/estado, respeita policy de autonomia, roda em modo conservador de planejamento por padrao e persiste watch-state/evidencias locais. `sendsprint doctor`, templates de validacao por stack, dry-run completo, worktrees deterministicas por task, evidence bundles, helpers de GitHub Issues, contratos Ralph Wiggum / Codex Goal, ingestao de transcricoes para tasks, dashboard, relatorios executivos e workflow PyPI Trusted Publishing inclusos. O fluxo principal ainda inclui `sendsprint sprint`, leitura Jira/Azure DevOps, codegen/deploy opt-in, estado resumivel, PRs, validacao pos-PR, badge de coverage e promocao automatica do changelog.

---

## Fluxo

| Passo | Nome | O que faz |
|------|------|-------------|
| 1 | **Ler sprint** | Busca stories/tasks/bugs no Jira ou Azure DevOps |
| 2 | **Mapeamento de arquitetura** | Inspeciona docs do repo; gera baseline se score < 0.6 |
| 3 | **Dev** | Detecta tech stack, cria worktree, instala deps + build |
| 4 | **Lint** | Análise estática por tech (eslint, ruff, clippy, etc.) |
| 5 | **Testes** | Unit + Playwright E2E com evidência em screenshot |
| 6 | **Security review** | Scan flag-only (segredos, .env, npm audit) |
| 7 | **Fix loop** | Se lint/teste/sec falhar: re-build + re-run (até 3 rodadas) |
| 8 | **Commit** | `git add -A && git commit` no branch do worktree |
| 9 | **Criar PR** | GitHub (gh CLI) ou Azure DevOps via REST |
| 10 | **Review do PR + Entregue** | Análise de diff + RunReport com export JSON |

Hooks opcionais:

- **Passo 3.5 — geracao por LLM** aplica um diff unificado opt-in entre build e lint.
- **Passo 11 — trigger de deploy** envia um webhook opt-in apos a criacao do PR e tenta atualizar o status do ticket.

Prioridade de transporte: `mcp` -> `api` -> `playwright`.

---

## Requisitos

- Python `>=3.11`
- Playwright (`playwright install chromium`)
- Opcional: token Jira / PAT Azure DevOps, ou MCP server Atlassian / Azure DevOps

---

## Instalação

```bash
git clone https://github.com/wesleysimplicio/SendSprint.git
cd SendSprint
pip install -e .
playwright install chromium
cp .env.example .env  # preencha credenciais
```

O SendSprint tambem pode expor o proprio tooling deterministico como servidor
MCP via stdio:

```bash
sendsprint mcp-serve
```

Tools MCP padrao atuais:

- `sendsprint_detect_tech`
- `sendsprint_check_architecture`
- `sendsprint_version`

O transporte usa JSON-RPC 2.0 com framing por `Content-Length`, entao Claude
Code e hosts MCP parecidos podem subir o processo direto.

---

## Quick start

### CLI

```bash
# Fluxo completo de 10 passos contra sprint Jira
sendsprint run jira 42 --workspace workspace.yaml --scope mine -o report.json

# Mesmo fluxo com patch gerado por LLM e callback de deploy opt-in
sendsprint run jira 42 --workspace workspace.yaml --scope mine --llm-codegen --deploy

# Fluxo completo contra Azure DevOps
sendsprint run azuredevops "Team\\Sprint 12" --repo ./repo

# Validar ambiente/sprint antes de entregar
sendsprint preflight azuredevops "Team\\Sprint 12" --workspace workspace.yaml

# Planejar branches/repos/PRs sem gravar arquivos nem abrir PR
sendsprint run azuredevops "Team\\Sprint 12" --workspace workspace.yaml --dry-run

# Retomar uma execucao de forma idempotente
sendsprint run azuredevops "Team\\Sprint 12" --workspace workspace.yaml --run-id sprint-12

# Monitorar tasks atribuidas em modo conservador de planejamento
sendsprint watch --workspace workspace.yaml --autonomy plan

# Rodar um ciclo sem alterar repos nem watch-state
sendsprint watch --workspace workspace.yaml --dry-run

# Detectar tech stack
sendsprint detect-tech ./repo

# Conferir mapeamento de arquitetura (com auto-build se faltar)
sendsprint check-architecture ./repo --build

# Sincronizar os arquivos mais recentes do agentic-starter
sendsprint sync-agentic-starter ./repo --ref latest
```

### Python

```python
from sendsprint.flow import SprintFlow
from sendsprint.operators import JiraOperator
from sendsprint.workspace import load_workspace
from sendsprint.scope import build_scope

ws = load_workspace("workspace.yaml")
scope = build_scope(mode="mine", user_email="dev@example.com")
flow = SprintFlow(operator=JiraOperator(), workspace=ws, scope=scope)
result = flow.run(sprint_id=42)
print(result.run_report.summary)
```

### Apenas ler sprint

```python
from sendsprint.operators import JiraOperator

op = JiraOperator(
    base_url="https://your-org.atlassian.net",
    transport="auto",
)
sprint = op.read_sprint(sprint_id=42)
for item in sprint.items:
    print(f"  [{item.type}] {item.key} - {item.title} ({item.status})")
```

---

## Workspace multi-repo

Defina repos em `workspace.yaml`:

```yaml
name: my-project
root_path: /home/dev/repos
new_projects_dir: Projetos/novos
pr_provider: github
default_base_branch: develop
branch_name_template: feature/{number}-{title}
pr_reviewers:
  - reviewer@example.com
required_pr_reviewers:
  - lead@example.com
code_generation:
  enabled: false
  provider: anthropic
  model: claude-opus-4-7
  max_usd: 1.0
  max_tokens: 8000
deploy:
  enabled: false
  provider: webhook
  url: https://deploy.example.com/hooks/sendsprint
  final_status: Deployed
watch:
  enabled: true
  provider: azuredevops
  interval_minutes: 15
  scope: assigned_to_me
  allowed_states:
    - New
  ignored_states:
    - Removed
    - Closed
    - Done
  work_item_types:
    - Task
  iteration_path: Team\\Sprint 12
  max_tasks_per_cycle: 1
  require_clean_worktree: true
  evidence_required: true
  playwright_required_for_front: true
  create_pr: true
  pr_target_branch: develop
repos:
  - name: backend-api
    path: backend-api
    role: api
    tech: dotnet
    default_branch: main
    pr_target_branch: develop
    # Regra opcional por repo:
    # required_pr_reviewers:
    #   - daniel.ribeiro_ext@interplayers.com.br
  - name: frontend-web
    path: frontend-web
    role: front
    tech: angular
  - name: mobile-app
    path: mobile-app
    role: mobile
    tech: flutter
```

---

## Arquitetura

```
sendsprint/
├── operators/         JiraOperator, AzureDevopsOperator (mcp|api|playwright)
├── models/            Sprint, SprintItem, StepReport, RunReport (Pydantic v2)
├── agents/
│   ├── worktree.py    Isolamento via git worktree p/ branches paralelos
│   ├── dev.py         Install + build por tech (16 package managers)
│   ├── lint_runner.py Análise estática por tech (19 linters)
│   ├── test_runner.py Unit + E2E com evidência em screenshot
│   ├── security_reviewer.py  Scan secret, env audit, npm audit
│   ├── pr_creator.py  Cria PR no GitHub (gh) / Azure DevOps (REST)
│   └── pr_reviewer.py Checks estáticos no diff (TODO, debug, linhas longas)
├── architecture/
│   ├── mapper.py      Score de arquitetura ponderado
│   └── builder.py     Gera docs baseline automaticamente
├── tech/
│   └── detector.py    Detecção por marker no filesystem (25+ techs)
├── workspace/
│   └── loader.py      Config YAML/JSON multi-repo
├── scope.py           Filtro `--scope mine` (account_id, email, name)
├── flow/
│   └── sprint_flow.py Orquestrador + hooks opt-in de codegen/deploy
├── llm/               Cliente LLM provider-agnostic
└── cli.py             CLI Typer
```

---

## Variáveis de ambiente

| Variável | Necessária pra |
|----------|-------------|
| `JIRA_BASE_URL` | API Jira |
| `JIRA_EMAIL` | API Jira |
| `JIRA_API_TOKEN` | API Jira |
| `AZURE_DEVOPS_ORG` | API Azure DevOps |
| `AZURE_DEVOPS_PROJECT` | API Azure DevOps |
| `AZURE_DEVOPS_PAT` | API Azure DevOps |
| `PLAYWRIGHT_CDP_URL` | Fallback Playwright (default `http://127.0.0.1:9222`) |
| `LLM_PROVIDER` | Step LLM (opcional) |
| `LLM_MODEL` | Step LLM (opcional) |

---

## Integracoes com assistentes

Manifestos de integracao por plataforma sob `skills/`:

| Arquivo | Plataforma |
|------|---------|
| `skills/claude/SKILL.md` | Claude Code |
| `skills/codex/AGENTS.md` | Codex / OpenAI |
| `skills/hermes/hermes.md` | Hermes Agent |
| `skills/openclaw/openclaw.md` | Openclaw |
| `skills/copilot/copilot-instructions.md` | GitHub Copilot |

Cada um aponta para o mesmo core Python; o manifesto ensina o assistente host a invocar o SendSprint de forma consistente.

---

## Testes

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

A suite cobre operators, mapper/builder de arquitetura, detector de tech, filtro de scope, loader de workspace, overrides da CLI e todos os agents, incluindo a orquestracao de codegen/deploy.

---

## Roadmap

- [x] Step 1 - Leitura de sprint (Jira + Azure DevOps, MCP / API / Playwright)
- [x] Step 2 - Mapeamento de arquitetura + auto-build de docs baseline
- [x] Step 3 - Dev agent (detecção de tech, isolamento via worktree, install + build)
- [x] Step 4 - Test runner (unit + Playwright E2E com evidência)
- [x] Step 5 - Security reviewer (flag-only: segredos, env, npm audit)
- [x] Step 6 - Fix loop (re-build + re-test, até 3 rodadas)
- [x] Step 7 - Criação de PR (GitHub gh CLI + Azure DevOps REST)
- [x] Step 8 - Review de PR (checks estáticos no diff)
- [x] Step 9 - RunReport com evidência completa
- [x] Suporte a workspace multi-repo (workspace.yaml)
- [x] Filtro `--scope mine` por usuário corrente
- [x] Geração de código por LLM por sprint item
- [x] Trigger de deploy + callback de status pra ticket
- [x] Modo MCP server (expor SendSprint como tool MCP)

---

## Uso pessoal e autorizacao pelo operador

SendSprint e um utilitario pessoal. Implicacoes praticas:

- **Nao existe servico hospedado.** Nao tem dashboard SaaS, nao tem tenant
  gerenciado, nao tem portal de billing. Tudo roda do seu terminal contra
  `localhost`.
- **Voce e o operador.** Cada leitura do Jira/ADO, cada operacao git e cada PR
  e iniciada por um humano rodando `sendsprint sprint` (ou subindo a API
  local). A ferramenta nao age sozinha em horario agendado.
- **Repos de empresa rodam sob sua autoridade.** Quando voce aponta o
  SendSprint pra um repo da empresa, voce esta usando seu proprio acesso —
  mesmas credenciais e mesmas branches que voce usaria na mao. Nao se cria
  nova fronteira de permissao.
- **Utilitario publico.** Este repo e MIT no GitHub. Outros engenheiros podem
  instalar do mesmo jeito (`pip install -e .`) e rodar nas proprias maquinas
  contra os proprios projetos. Nao ha oferta comercial planejada.

Se um dia voce quiser uma versao hospedada/multi-tenant, faca fork e construa
voce mesmo — a arquitetura e local-first de proposito.

## Licença

MIT - veja [LICENSE](./LICENSE).
