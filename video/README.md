# SendSprint — vídeo explicativo (Remotion)

Vídeo animado em React/Remotion que ensina, em ~56 segundos, como usar a skill
**SendSprint** no Claude Code (e em mais 12 IDEs/agentes). Estilo: gradient
escuro com partículas leves, terminais animados, ícones SVG, transições por
spring/fade.

> Stack: Remotion 4 + React 19 + TypeScript. 1920×1080 @ 30fps. Saída MP4 (h264) ou WebM.

## Previews

### Skill explainer (56s)

| 🇺🇸 English | 🇧🇷 Português |
|---|---|
| ![EN preview](./preview/sendsprint-en-preview.gif) | ![PT preview](./preview/sendsprint-preview.gif) |
| [▶️ MP4 (20 MB)](./preview/sendsprint-explainer-en.mp4) | [▶️ MP4 (20 MB)](./preview/sendsprint-explainer.mp4) |

### Run loop (22s) — usado no `web/README.md`

| 🇺🇸 English | 🇧🇷 Português |
|---|---|
| ![EN preview](./preview/runloop-en-preview.gif) | ![PT preview](./preview/runloop-preview.gif) |
| [▶️ MP4 (5.5 MB)](./preview/runloop-en.mp4) | [▶️ MP4 (5.5 MB)](./preview/runloop.mp4) |

> Os GIFs são previews 560p / 12fps. Os MP4s em `preview/` são 1080p @ 30fps.
> Os strings vêm do `src/i18n.tsx` — adicionar uma terceira língua = mais um
> entry no objeto `STRINGS` + uma nova `<Composition lang="es">`.

## Cenas

**Skill explainer** (`SendSprintExplainer`, 56s):

| # | Cena | Duração | O que mostra |
|---|---|---|---|
| 1 | `IntroScene` | 4s | Logo + título + subtítulo |
| 2 | `WhatIsScene` | 7s | O que é + 4 cards de features |
| 3 | `TriggerScene` | 6s | Frases-gatilho + terminal animado |
| 4 | `StepsScene` | 20s | Lista dos 10 passos + card focal por passo |
| 5 | `IDEsScene` | 6s | Grid das 12 integrações de IDE |
| 6 | `SetupScene` | 7s | Setup em 4 passos + terminal de instalação |
| 7 | `OutroScene` | 6s | CTA "rode o sendsprint" |

**Run loop** (`SendSprintRunLoop`, 22s):

| # | Bloco | Duração | O que mostra |
|---|---|---|---|
| 1 | Hero | ~2s | Título "rode até passar" + sub |
| 2 | Round 1 | ~8s | Steps 1–6, regressão FALHA com 3 testes |
| 3 | Fix-loop | ~3s | Patches sugeridos + retry |
| 4 | Round 2 | ~6s | Re-roda steps 3–6, regressão VERDE + galeria |
| 5 | Delivered | ~2s | "Sprint entregue" + URL do PR |

A timeline da skill explainer está em [`src/theme.ts`](./src/theme.ts) (`SCENES`);
o run loop tem timeline própria em [`src/scenes/RunLoopScene.tsx`](./src/scenes/RunLoopScene.tsx) (`T`).

## Como rodar

```bash
cd video
npm install
npm start                 # abre o Remotion Studio (preview interativo)
npm run build             # renderiza out/sendsprint-explainer.mp4
npm run build:webm        # renderiza out/sendsprint-explainer.webm (vp9)
npm run still             # exporta um frame estático em out/poster.png
npm run typecheck         # valida tipos
```

`npm start` abre o Studio em `http://localhost:3000` — você scrubeia a timeline,
inspeciona props, edita e vê o reload na hora.

## Composições disponíveis

| ID | Lang | Resolução | Uso |
|---|---|---|---|
| `SendSprintExplainer` | pt | 1920×1080 | README pt-BR |
| `SendSprintExplainerEN` | en | 1920×1080 | README EN / YouTube |
| `SendSprintExplainer1080Square` | pt | 1080×1080 | Instagram / LinkedIn |
| `SendSprintRunLoop` | pt | 1920×1080 | README pt-BR — demo do loop |
| `SendSprintRunLoopEN` | en | 1920×1080 | README EN — demo do loop |

Render manual:

```bash
npx remotion render src/index.ts SendSprintRunLoop preview/runloop.mp4 \
  --browser-executable=$(which chromium)   # ou chrome-headless-shell
```

Para renderizar a versão quadrada:

```bash
npx remotion render src/index.ts SendSprintExplainer1080Square out/square.mp4
```

## Customização rápida

- **Paleta + fontes**: `src/theme.ts` (`theme.gradient`, `theme.primary` …)
- **Conteúdo dos 10 passos**: array `STEPS` em `src/scenes/StepsScene.tsx`
- **Frases-gatilho**: array `triggers` em `src/scenes/TriggerScene.tsx`
- **IDEs suportados**: array `IDES` em `src/scenes/IDEsScene.tsx`
- **Comandos do terminal**: `installLines` em `SetupScene` e `lines` em
  `TriggerScene`
- **Logo**: SVG inline em `src/components/Logo.tsx`

## Adicionando imagens ou videos reais

1. Coloque assets em `video/public/` (ex.: `public/screenshot.png`,
   `public/clip.mp4`)
2. Importe `Img` ou `Video` do Remotion na cena que quiser:
   ```tsx
   import { Img, Video, staticFile } from "remotion";

   <Img src={staticFile("screenshot.png")} />
   <Video src={staticFile("clip.mp4")} />
   ```
3. Embrulhe num `<Sequence from={…} durationInFrames={…}>` se quiser
   programar entrada/saída.

## Pré-requisitos

- Node ≥ 18 (testado com 22)
- Para renderizar MP4: nada extra — Remotion baixa o Chromium headless na
  primeira execução.
- Para WebM/VP9: idem.
- Para H.265/ProRes/áudio avançado: instale `ffmpeg` no sistema.

## Estrutura

```
video/
├── package.json
├── tsconfig.json
├── remotion.config.ts
├── README.md
├── public/                  # assets estáticos (vazio por padrão)
└── src/
    ├── index.ts             # registerRoot
    ├── Root.tsx             # registra <Composition />
    ├── Video.tsx            # orquestra cenas via <Sequence />
    ├── theme.ts             # paleta, fps, timeline central
    ├── components/
    │   ├── Background.tsx   # gradient blobs animados + grid sutil
    │   ├── Particles.tsx    # partículas SVG flutuantes
    │   ├── AnimatedText.tsx # letras com stagger spring
    │   ├── Card.tsx         # cartão com glow + entrada animada
    │   ├── Logo.tsx         # logo SVG do SendSprint (raio)
    │   ├── Terminal.tsx     # terminal estilo macOS com typewriter
    │   └── StepIcon.tsx     # ícones SVG dos 10 passos
    └── scenes/
        ├── IntroScene.tsx
        ├── WhatIsScene.tsx
        ├── TriggerScene.tsx
        ├── StepsScene.tsx
        ├── IDEsScene.tsx
        ├── SetupScene.tsx
        └── OutroScene.tsx
```

## Notas

- Tudo é gerado em runtime — sem dependência de PNGs ou MP4s externos.
- Para trocar idioma do roteiro, edite os `text=` nas cenas — todo o conteúdo
  está em pt-BR por padrão.
- Os efeitos são leves (blur, gradient, partículas, springs) — render típico em
  CPU moderna fica em ~30–60s por minuto de vídeo.
