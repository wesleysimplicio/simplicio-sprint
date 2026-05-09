# SendSprint — App Mobile

App **Expo / React Native** que serve como controle remoto da skill SendSprint
rodando localmente. Você abre no celular, escolhe Jira ou Azure DevOps,
autentica, lista sprints ativas, escolhe os itens a entregar, e acompanha em
tempo real cada step do fluxo (lint → test → security → commit → PR) com
evidências e screenshots.

> Stack: Expo SDK 51 · React Native 0.74 · React Navigation 6 · TypeScript · SSE.

## Telas

| # | Tela | O que faz |
|---|---|---|
| 1 | `ConnectScreen` | URL do backend (`http://<IP>:8765`) + ping em `/health` |
| 2 | `ProviderScreen` | Escolha entre Jira e Azure DevOps |
| 3 | `AuthScreen` | Formulário de credenciais (token salvo no keyring do **backend**) |
| 4 | `SprintsScreen` | Lista sprints ativas + botão "Importar todas em background" |
| 5 | `SprintDetailScreen` | Lista os itens; modos: **sprint inteira / só meus / itens escolhidos** |
| 6 | `RunScreen` | 10 steps animados em tempo real via SSE + log + galeria de evidências |
| 7 | `ResultScreen` | Resumo final + link pro PR + metadados do run |

## Como rodar

### 1) Suba o backend (no Mac/Linux/WSL)

```bash
# na raiz do repo
pip install -e ".[api]"
python -m sendsprint.api          # default em :8765
# ou
sendsprint-api
```

Saúde: `curl http://localhost:8765/health` → `{ok:true,...}`.

### 2) Suba o app — caminho mais rápido: **navegador (web)**

```bash
cd mobile
npm install
npm run web                  # ou: npm start → tecla "w"
```

Abre `http://localhost:8081` no navegador. UI mobile renderizada via
`react-native-web` — mesmo código, mesma navegação, mesma stack de telas.
Ideal pra desenvolver e ver o fluxo todo sem celular.

> **Conexão direta**: já que o backend está no mesmo `localhost`, o
> `defaultBackend` (`http://localhost:8765`) funciona out-of-the-box. Só
> apertar "Conectar" na primeira tela.

### 3) Opcional — celular real (Expo Go)

```bash
npm start
```

Escaneie o QR com **Expo Go** (iOS App Store / Google Play). Ao abrir o app:

- **Simulador iOS**: deixe `http://localhost:8765`
- **Celular físico**: troque por `http://<IP-da-máquina>:8765` (mesma Wi-Fi)
- **Emulador Android**: use `http://10.0.2.2:8765`

### 3) Fluxo

```
Connect → Provider → Auth → Sprints → SprintDetail → Run (SSE) → Result
```

Modos de execução:

- **Sprint inteira** → roda todos os itens (`mode=all`)
- **Só meus** → filtra pelo email do usuário autenticado (`mode=mine`, usa `--scope mine`)
- **Itens escolhidos** → seleciona N itens com checkbox (`mode=selected`)

## Estrutura

```
mobile/
├── App.tsx                    # entrypoint
├── app.json                   # Expo config (name, scheme, defaultBackend)
├── package.json
├── tsconfig.json
├── babel.config.js
└── src/
    ├── theme.ts               # paleta + radius/spacing
    ├── navigation.tsx         # native-stack
    ├── store/session.tsx      # AsyncStorage + ApiClient
    ├── api/
    │   ├── client.ts          # fetch wrapper
    │   ├── sse.ts             # SSE via react-native-event-source
    │   └── types.ts
    ├── components/            # Button, Card, Input, Screen, StepRow
    └── screens/               # 7 telas listadas acima
```

## Comandos

```bash
npm start             # inicia o Metro bundler + abre Expo Dev Tools
npm run ios           # abre no Simulator iOS
npm run android       # abre no emulador / device USB
npm run web           # abre no navegador
npm run typecheck     # tsc --noEmit
```

## Personalização

- **Cores**: `src/theme.ts` (mesma paleta do vídeo Remotion)
- **Endpoint default**: `app.json` em `expo.extra.defaultBackend`
- **Adicionar novo provedor**: 1) array em `ProviderScreen.tsx`; 2) `api/client.ts` (`auth*`); 3) backend rota em `sendsprint/api/routes/auth.py`

## Como o real-time funciona

`RunScreen` abre uma conexão **SSE** em
`GET /runs/{id}/events`. O backend stream-eia eventos JSON conforme cada step
do `SprintFlow` é completado:

```json
{"type":"step","step":4,"name":"lint","status":"running","progress":0.3}
{"type":"evidence","evidence_path":"evidence/abc123/login.png"}
{"type":"done","pr_url":"https://github.com/.../pull/42"}
```

## Notas

- O app **não armazena tokens** — eles vão direto pra `/auth/jira` ou `/auth/azuredevops` que persiste no keyring do SO no **backend** (chmod 600 em Linux/macOS).
- Sem credenciais, o backend retorna sprints/run em **modo demo** — você consegue clicar todo o flow.
- `react-native-event-source` é o polyfill SSE pra React Native (a `EventSource` nativa não existe).
