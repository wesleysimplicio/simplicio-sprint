# SendSprint API

FastAPI server que expõe o SendSprint (operadores Jira/ADO + SprintFlow) por
HTTP + SSE. É o backend que o app `mobile/` consome localmente.

## Subir

```bash
pip install -e ".[api]"
python -m sendsprint.api          # default em :8765
# ou
sendsprint-api                    # mesmo entrypoint
```

Variáveis de ambiente:

| Var | Default | Uso |
|---|---|---|
| `SENDSPRINT_API_HOST` | `0.0.0.0` | Bind do uvicorn (use `0.0.0.0` pra ser visível na LAN) |
| `SENDSPRINT_API_PORT` | `8765` | Porta |

OpenAPI docs em `http://<host>:8765/docs`.

## Endpoints

| Método | Path | O que faz |
|---|---|---|
| GET | `/health` | Versão + flags de provedor configurado |
| POST | `/auth/jira` | `{base_url, email, api_token}` → valida e salva no keyring |
| POST | `/auth/azuredevops` | `{organization, project, pat}` → valida e salva no keyring |
| GET | `/auth/status` | Diz quais provedores têm credencial cacheada |
| GET | `/sprints?provider=…` | Lista sprints ativas (Jira board ou ADO team) |
| GET | `/sprints/{id}?provider=…&scope=mine` | Itens da sprint, com filtro opcional `mine` |
| POST | `/sprints/import` | Importa todas as sprints em background (job) |
| GET | `/sprints/import/{job_id}` | Status do job de import |
| POST | `/runs` | Inicia um run: `{provider, sprint_id, mode, item_keys, repo_path?}` |
| GET | `/runs` | Lista runs em memória |
| GET | `/runs/{id}` | Status do run (`queued/running/done/failed`) |
| GET | `/runs/{id}/events` | **SSE stream** — eventos em tempo real do flow |
| GET | `/runs/{id}/evidence/{name}` | Serve screenshots/logs gerados em `evidence/{run_id}/` |

## Fluxo SSE

`GET /runs/{id}/events` emite eventos JSON conforme cada step do `SprintFlow`
é completado:

```
event: hello
data: {"run_id":"abc123"}

data: {"type":"step","step":4,"name":"lint","status":"running","progress":0.3}
data: {"type":"step","step":4,"name":"lint","status":"ok","progress":0.4}
data: {"type":"evidence","evidence_path":"evidence/abc123/login.png"}
data: {"type":"done","failed":false,"pr_url":"https://github.com/…/pull/42"}
```

`type` ∈ `step | log | evidence | summary | done | error`. Stream fecha após
`done` ou `error`.

## Modos de execução

`POST /runs` aceita `mode`:

- `"all"` — roda todos os itens da sprint
- `"mine"` — usa `--scope mine` (filtra por accountId/email/displayName do usuário)
- `"selected"` — só os `item_keys` enviados

Se `repo_path` for passado, o backend tenta o `SprintFlow` real
(`git worktree`, `npm install`, `pytest`, …). Sem `repo_path` ou sem
credenciais válidas, cai num **modo demo** que simula os 10 steps com
evidências e PR fictícios — útil pra desenvolver o app mobile.

## Estrutura

```
sendsprint/api/
├── __init__.py
├── __main__.py        # python -m sendsprint.api
├── server.py          # FastAPI app + lifespan + CORS
├── schemas.py         # Pydantic request/response models
├── routes/
│   ├── auth.py
│   ├── sprints.py
│   └── runs.py
└── runs/
    ├── events.py      # asyncio.Queue broker para SSE
    ├── manager.py     # registry + thread executor
    └── bridge.py      # SprintFlow real OU modo demo
```

## Testes

```bash
pytest tests/test_api.py -v
```

5 smoke tests cobrem health, listagem demo, run + SSE evento, 404s.

## Notas de segurança

- Credenciais persistem no **OS keyring** (mesma camada da CLI; ver
  `sendsprint.credentials`). O backend nunca devolve tokens em respostas.
- CORS está aberto (`allow_origins=["*"]`) pra facilitar o dev. Se for expor
  além do localhost, restrinja em `server.py`.
- O servidor é **single-tenant** — espera estar rodando na máquina do dev. Não
  use atrás de proxy público sem autenticação adicional.
