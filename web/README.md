# SendSprint — Web (localhost)

Browser UI que controla o backend SendSprint rodando localmente. Tudo
acontece em **localhost** — sem celular, sem app store, sem Expo Go. Você
abre `http://localhost:8081` no navegador, conecta no backend
(`http://localhost:8765`), escolhe Jira ou Azure DevOps, autentica, lista
sprints ativas e dispara o run loop. O loop **roda em iterações até
todos os testes (incluindo regressão) passarem** ou estourar o limite de
3 rounds.

> Stack: Expo SDK 51 + react-native-web + React Navigation 6 + TypeScript.
> Mesmo código que rodaria em iOS/Android é compilado pra web pelo Metro.

## Demo do run loop (Remotion)

![SendSprint run loop](../video/preview/runloop-preview.gif)

<p align="center">
  <a href="../video/preview/runloop.mp4">▶️ MP4 cheio (1920×1080, ~22s)</a>
  &nbsp;·&nbsp;
  <a href="../video/preview/runloop-en.mp4">🇺🇸 English</a>
</p>

Mostra exatamente o que você verá em `RunScreen` ao clicar "Iniciar entrega":
round 1 falha com regressão visual → fix loop sugere patches → round 2
verde → commit → PR.

## Como rodar

### 0) Suba tudo de uma vez

```bash
pip install -e ".[api]"
cd web && npm install
sendsprint web
```

Isso garante o backend em `http://127.0.0.1:8765`, sobe a UI em
`http://localhost:8081` e abre o browser. O primeiro `sendsprint run`,
`sendsprint watch` ou `sendsprint sprint` do dia faz esse bootstrap
automaticamente, a menos que vocÃª passe `--no-dashboard`.
Para autonomia mÃ¡xima em loop contÃ­nuo, use
`sendsprint full --workspace workspace.yaml`.
Se vocÃª quiser isso persistido como padrÃ£o local, rode
`sendsprint configure-defaults --repo . --workspace workspace.yaml`.

### 1) Suba o backend (no Mac/Linux/WSL)

```bash
# na raiz do repo
pip install -e ".[api]"
python -m sendsprint.api          # default em :8765
# ou
sendsprint-api
```

Saúde: `curl http://localhost:8765/health` → `{ok:true,...}`.

### 2) Suba o web

```bash
cd web
npm install
npm run dev          # = expo start --web
```

Abre `http://localhost:8081` no navegador. Mesmo `localhost`, então o
backend default (`http://localhost:8765`) funciona out-of-the-box. Só
clicar **"Conectar"** na primeira tela.

### 3) Build pra produção (opcional)

```bash
npm run build        # gera dist/ via expo export --platform web
npm run preview      # serve dist/ em :4173
```

## Telas (em ordem)

| # | Tela | O que faz |
|---|---|---|
| 1 | `ConnectScreen` | URL do backend + ping em `/health` |
| 2 | `ProviderScreen` | Escolhe Jira ou Azure DevOps |
| 3 | `AuthScreen` | Credenciais (vão direto pro keyring do **backend**, nunca ficam no browser) |
| 4 | `SprintsScreen` | Lista sprints ativas + botão "Importar todas em background" |
| 5 | `SprintDetailScreen` | Itens; modos: **sprint inteira / só meus / itens escolhidos** |
| 6 | `RunScreen` | 10 steps + **loop até passar** + galeria de evidências por round + painel de regressão |
| 7 | `ResultScreen` | Resumo + link pro PR + metadados |

## O run loop (`RunScreen`)

A tela faz long-poll via SSE em `GET /runs/{id}/events`. O backend orquestra:

```
round 1 ──▶ steps 1-6 ──▶ tests-regression FAILED ──▶ step 7 fix-loop
                                                          │
                                                          ▼
round 2 ──▶ steps 3-6 ──▶ tests-regression OK ──▶ step 8 commit
                                                          │
                                                          ▼
                                                 step 9 PR + step 10 deliver
```

Eventos SSE recebidos:

| `type` | Quando | UI |
|---|---|---|
| `step` | cada transição running/ok/failed | `StepRow` atualiza ícone + cor |
| `loop` | nova iteração (`iteration`/`max_iterations`) | counter no footer "↻ round 2/3" |
| `regression` | result do passo de regressão por round | painel de badges verdes/vermelhos + lista de testes que falharam |
| `evidence` | screenshot capturado | thumbnail na galeria, agrupada por round |
| `log` | mensagem livre (patches sugeridos, etc.) | linha mono no log box |
| `done` | run terminou | botão "Ver resultado" libera |

## Estrutura

```
web/
├── App.tsx                    # entrypoint
├── app.json                   # Expo config (platforms: ["web"])
├── package.json
├── tsconfig.json
├── babel.config.js
└── src/
    ├── theme.ts               # paleta (mesma do vídeo Remotion)
    ├── navigation.tsx         # native-stack
    ├── store/session.tsx      # AsyncStorage (web) + ApiClient
    ├── api/
    │   ├── client.ts          # fetch tipado
    │   ├── sse.ts             # browser-native EventSource
    │   └── types.ts
    ├── components/            # Button, Card, Input, Screen, StepRow
    └── screens/               # 7 telas listadas acima
```

## Comandos

```bash
npm run dev           # Metro web em :8081 (alias de start)
npm run start         # mesma coisa
npm run build         # bundle estático em dist/
npm run preview       # serve dist/ em :4173
npm run typecheck     # tsc --noEmit
```

## Por que Expo + react-native-web?

A intenção original era rodar também em iOS/Android, então a stack ficou
RN. A pivotagem pra "só web" mantém o mesmo código mas:

- `app.json` declara `platforms: ["web"]` (sem ios/android)
- `package.json` removeu `react-native-event-source` (web tem `EventSource` nativo)
- Scripts `npm run android` / `npm run ios` foram removidos
- `start` agora é `expo start --web`

Se algum dia voltar a querer iOS/Android, é só recolocar essas linhas.

## Customização

- **Cores**: `src/theme.ts` (mesma paleta do vídeo Remotion)
- **Endpoint default**: `app.json` em `expo.extra.defaultBackend`
- **Adicionar novo provedor**: 1) array em `ProviderScreen.tsx`; 2) `api/client.ts`; 3) backend em `sendsprint/api/routes/auth.py`

## Notas

- O navegador **não armazena tokens** — eles vão direto pro `/auth/{provider}` no backend, que persiste no keyring do SO (chmod 600 em Linux/macOS).
- Sem credenciais reais, o backend volta sprints/run em **modo demo** com loop, screenshots e PR fictícios — todo o flow é demoable a partir do `npm run dev`.
