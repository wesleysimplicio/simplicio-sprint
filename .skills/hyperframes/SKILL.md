---
name: hyperframes
description: Renderiza as evidências de uma entrega como vídeo MP4 usando HyperFrames (HTML→MP4 via Node + FFmpeg). Ative quando o usuário pedir vídeo/clipe de evidência de uma sprint, RunReport ou EvidenceBundle, ou quando uma entrega precisar de prova visual além do JSON.
---

# Skill: `hyperframes`

Transforma `RunReport` / `EvidenceBundle` do SendSprint em um vídeo MP4 de evidência usando o framework open-source **HyperFrames** (https://github.com/wesleysimplicio/hyperframes — fork local) ou o upstream (https://github.com/heygen-com/hyperframes). Composições são HTML com `data-*` attributes — sem React, sem DSL proprietária. Sem código vendado dentro do `sendsprint/`; tudo é gerado sob demanda pelo agente.

---

## Trigger

Ative essa skill quando o usuário disser/pedir qualquer um destes:

- pt-BR: "vídeo da entrega", "evidência em vídeo", "renderizar evidências", "gerar clipe da sprint", "hyperframes", "vídeo de prova da entrega"
- en: "render evidence video", "delivery video", "evidence clip", "hyperframes the run", "video proof of delivery"
- es: "vídeo de entrega", "evidencia en vídeo"

Ative implicitamente quando:

- Existe um `evidence-bundles/evidence-<run_id>/manifest.json` ou `.sendsprint/evidence/<run_id>/bundle.json` no repo e o usuário pede "prova", "evidência visual", "video de demo" da última sprint.
- Há screenshots em `test-results/` ou no `EvidenceBundle.items` com `type=screenshot` e o objetivo é apresentar para stakeholder não-técnico.
- O comando `sendsprint bundle-evidence` foi executado e o usuário quer "subir o nível" da entrega.

**Não** ative para:

- Vídeos institucionais/marketing — esses moram em `video/` (Remotion).
- Geração de PR body — use `agents/pr_body_builder.py`.

---

## Steps

1. **Localize o input**. Pergunte/encontre um destes:
   - `report.json` (estrutura `sendsprint.models.reports.RunReport`).
   - `bundle.json` (estrutura `sendsprint.evidence.EvidenceBundle`).
   - Diretório de evidências (`evidence-bundles/evidence-<run_id>/`).
2. **Cheque o toolchain** com `node --version`, `ffmpeg -version` e `npx hyperframes --version`. Se algum estiver ausente, registre como `status="skipped"` e ofereça instalar (`npm install -g hyperframes` ou usar `npx hyperframes` direto) — NUNCA falsifique sucesso.
3. **Gere a composição HTML** em `hyperframes-out/composition.html`. Use o template em `## Composition template` abaixo. Estrutura mínima:
   - 1 cena `intro` (4s): título da sprint + workspace.
   - 1 cena `summary` (4s): contagem de steps OK/total, número de PRs, scope.
   - N cenas `step` (4s cada): uma por `StepReport`, com status colorido (`ok|failed|skipped`).
   - N cenas `screenshot` (2.5s cada): uma por `TestEvidence(kind="screenshot")` com `path` válido.
   - 1 cena `outro` (3s): URLs dos PRs criados.
4. **Escape user content**. Tudo que vier do report (sprint_id, workspace, step.name, step.message, pr.url) passa por `html.escape` em Python ou equivalente. Bug clássico: `sprint_id="<script>"` injeta no `<title>`.
5. **Renderize o MP4** (opcional, se toolchain disponível):
   ```bash
   npx hyperframes render hyperframes-out/composition.html \
     --out hyperframes-out/evidence-<run_id>.mp4
   ```
   Timeout: 600s. Captura `stderr` em caso de exit code ≠ 0.
6. **Anexe ao bundle**. Se existe um `EvidenceBundle`, adicione o MP4 como item:
   ```python
   from sendsprint.evidence import BundleManager, EvidenceItemType
   mgr = BundleManager()
   bundle = mgr.load_bundle(run_id)
   mgr.add_item(bundle, EvidenceItemType.screenshot, "hyperframes-out/evidence-<run_id>.mp4",
                metadata={"title": "delivery video", "kind": "video/mp4"})
   ```
7. **Reporte**. Console output em formato Rich, status colorido (green=ok, yellow=skipped, red=failed) — espelha o padrão dos outros agents.

---

## Padrões

- **Naming**: arquivo de saída sempre `composition.html` no diretório alvo. MP4 segue `evidence-<run_id>.mp4`.
- **Estrutura HTML**: 1 root `<div data-composition-id data-width data-height data-fps>` com `<section class="scene scene--<kind>" data-start data-duration>` internos. Cada `data-start` ≥ ao `data-start + data-duration` da cena anterior (sem overlap).
- **Resolução padrão**: 1920×1080 @ 30 fps — mesmo do `video/` Remotion stack.
- **Tema**: paleta dark (`--bg:#0b0f1a`, `--fg:#e8ecff`, `--ok:#6ee7b7`, `--fail:#fca5a5`, `--skip:#fcd34d`, `--accent:#818cf8`). Consistente com `video/src/theme.ts`.
- **Fallback obrigatório**: se `shutil.which("npx") is None` ou `hyperframes` não instalado, retorne `StepReport(status="skipped", message="…")` — padrão documentado em `AGENTS.md` §5.
- **Evite**: vendar a lib `hyperframes` no `pyproject.toml`. É opcional, fica fora das dependências do `sendsprint`.
- **Evite**: misturar com o pipeline Remotion (`video/`) — esse renderiza vídeos institucionais, não evidências por entrega.
- **Prefira**: subprocess wrapper que aceita `runner=` injetável (para testes com `monkeypatch`).

---

## Composition template

Use isso como ponto de partida ao gerar o HTML (Python f-string ou template engine — não importa):

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>SendSprint evidence — {run_id}</title>
<style>
  :root {
    color-scheme: dark;
    --bg:#0b0f1a; --fg:#e8ecff; --muted:#8a93b8;
    --ok:#6ee7b7; --fail:#fca5a5; --skip:#fcd34d; --accent:#818cf8;
  }
  body { margin:0; background:var(--bg); color:var(--fg);
         font-family: ui-sans-serif, system-ui, sans-serif; }
  .scene { position:absolute; inset:0; padding:96px; box-sizing:border-box;
           display:flex; flex-direction:column; justify-content:center; gap:24px; }
  .scene h1 { font-size:96px; margin:0; }
  .scene h2 { font-size:56px; margin:0; color:var(--accent); }
  .scene p  { font-size:32px; margin:0; color:var(--muted); }
  .scene .status-ok { color:var(--ok); }
  .scene .status-failed { color:var(--fail); }
  .scene .status-skipped { color:var(--skip); }
  .scene img { max-width:100%; max-height:720px; border-radius:16px; object-fit:contain; }
  .pill { display:inline-block; padding:4px 12px; border-radius:999px;
          background:rgba(129,140,248,0.15); font-size:24px; color:var(--accent); }
</style>
</head>
<body>
<div data-composition-id="sendsprint-evidence-{run_id}"
     data-width="1920" data-height="1080" data-fps="30">

  <section class="scene scene--intro" data-start="0.00" data-duration="4.00">
    <span class="pill">SendSprint</span>
    <h1>SendSprint Delivery</h1>
    <p>Sprint {sprint_id} — {workspace}</p>
  </section>

  <section class="scene scene--summary" data-start="4.00" data-duration="4.00">
    <h2 class="status-ok">{summary}</h2>
    <ul>
      <li>Steps OK: <strong>{steps_ok}/{steps_total}</strong></li>
      <li>PRs opened: <strong>{pr_count}</strong></li>
      <li>Scope: <strong>{scope_mode}</strong></li>
    </ul>
  </section>

  <!-- Para cada StepReport: -->
  <section class="scene scene--step" data-start="{cursor}" data-duration="4.00">
    <span class="pill">{repo_or_global}</span>
    <h2 class="status-{step.status}">Step {step.step}: {step.name}</h2>
    <p>{step.message}</p>
  </section>

  <!-- Para cada TestEvidence(kind=screenshot, path=…): -->
  <section class="scene scene--screenshot" data-start="{cursor}" data-duration="2.50">
    <span class="pill">screenshot</span>
    <h2>{evidence.title}</h2>
    <img src="{evidence.path}" alt="{evidence.title}" />
  </section>

  <section class="scene scene--outro" data-start="{cursor}" data-duration="3.00">
    <span class="pill">delivered</span>
    <h1>Sprint {sprint_id}</h1>
    <ul>
      <!-- 1 <li> por PR.url -->
    </ul>
  </section>

</div>
</body>
</html>
```

---

## Comando de render

```bash
# Pré-requisitos: Node ≥ 22, FFmpeg. Sem instalação global necessária:
npx hyperframes render hyperframes-out/composition.html \
  --out hyperframes-out/evidence-<run_id>.mp4

# Preview no browser (live reload) durante autoria:
npx hyperframes preview hyperframes-out/composition.html
```

Se preferir instalar globalmente: `npm install -g hyperframes`.

---

## Definition of Done

- [ ] `composition.html` existe no `output_dir` e abre num browser sem erro de console.
- [ ] Todas as cenas têm `data-start` ≥ `data-start+data-duration` da cena anterior (sem sobreposição).
- [ ] Toda string vinda do RunReport passou por `html.escape` (testar com `sprint_id="<script>"`).
- [ ] Se toolchain ausente → `StepReport(status="skipped", message="npx/hyperframes not installed — render skipped")`. Nunca `status="ok"` sem MP4 real.
- [ ] Se MP4 renderizado → arquivo `evidence-<run_id>.mp4` existe, `> 0 bytes`, ffprobe confirma `duration > 0`.
- [ ] Se existe `EvidenceBundle` para o `run_id`, o MP4 foi anexado como `EvidenceItem` com `metadata.kind="video/mp4"`.
- [ ] Console output usa cores Rich consistentes (green/yellow/red) com o resto do CLI.

---

## Exemplo (fluxo completo)

```python
# 1. Carregue o RunReport
from pathlib import Path
from sendsprint.models.reports import RunReport
report = RunReport.model_validate_json(Path("report.json").read_text())

# 2. Gere a composição HTML (template acima preenchido com os campos do report)
out_dir = Path("hyperframes-out")
out_dir.mkdir(exist_ok=True)
(out_dir / "composition.html").write_text(build_composition_html(report))

# 3. Renderize MP4 com fallback gracioso
import shutil, subprocess
if shutil.which("npx"):
    proc = subprocess.run(
        ["npx", "hyperframes", "render",
         str(out_dir / "composition.html"),
         "--out", str(out_dir / f"evidence-{report.sprint_id}.mp4")],
        capture_output=True, text=True, timeout=600, check=False,
    )
    status = "ok" if proc.returncode == 0 else "failed"
else:
    status = "skipped"

# 4. Anexe ao bundle (se existir)
from sendsprint.evidence import BundleManager, EvidenceItemType
mgr = BundleManager()
bundle = mgr.load_bundle(report.sprint_id)
if bundle and status == "ok":
    mgr.add_item(bundle, EvidenceItemType.screenshot,
                 str(out_dir / f"evidence-{report.sprint_id}.mp4"),
                 metadata={"title": "delivery video", "kind": "video/mp4"})
    mgr.finalize(bundle)
```

---

## Notas

- HyperFrames upstream: https://github.com/heygen-com/hyperframes (Apache 2.0).
- Fork de referência: https://github.com/wesleysimplicio/hyperframes.
- Pipeline interno de marketing (não confundir): `video/` (Remotion + React).
- ADR relacionado a evidências: `sendsprint/evidence.py` (`EvidenceBundle` v2.0).
- Se o usuário pedir Spanish/inglês na composição, espelhe os strings — não há i18n built-in, mude direto as labels do template.
- Para CI/headless: rode `npx hyperframes render` com `HEADLESS=1`. Sem display server o Puppeteer ainda funciona.
- **Não invente** flags do CLI hyperframes — se o usuário pedir feature avançada (transitions, audio mixing, shader effects), leia primeiro a doc upstream e só então proponha.
