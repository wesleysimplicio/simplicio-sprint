# RELEASE — `SendSprint`

Processo para cortar uma release do `SendSprint` (Python + Node tooling). Releases são tagueadas, automatizadas via GitHub Actions e reversíveis. Dono do processo: `@wesleysimplicio`.

---

## 1. Princípios

- **SemVer estrito.** `MAJOR.MINOR.PATCH`. Quebra contrato = MAJOR, feature compatível = MINOR, fix compatível = PATCH.
- **Tag é fonte de verdade.** Nada de "release sem tag". Sem tag, sem deploy de produção.
- **CHANGELOG é contrato com o usuário.** Toda release tem entrada lida e revisada.
- **Rollback em minutos.** Toda release tem caminho documentado de volta.

---

## 2. Bump de versão (SemVer)

Critério rápido:

| Mudança | Bump |
|---------|------|
| Bug fix interno, sem mudar API/UX | PATCH (`1.4.2` -> `1.4.3`) |
| Feature nova, retrocompatível | MINOR (`1.4.2` -> `1.5.0`) |
| Quebra de API, schema, contrato | MAJOR (`1.4.2` -> `2.0.0`) |
| Pre-release, RC | sufixo (`1.5.0-rc.1`) |

No SendSprint, o número de versão precisa ficar alinhado em:
- `pyproject.toml`
- `sendsprint/__init__.py`
- `package.json`

Bump idempotente:

```bash
# Manual sync in this repo
# - pyproject.toml
# - sendsprint/__init__.py
# - package.json
```

---

## 3. Atualizar `CHANGELOG.md`

Formato Keep a Changelog. Toda release tem bloco com seções abaixo (omita as vazias):

```markdown
## [1.5.0] - 2026-05-07

### Added
- Magic link login flow (auth) - task #12.

### Changed
- Checkout error messages now use i18n keys.

### Fixed
- Double-charge on 3DS retry (#48).

### Removed
- Legacy session cookie (deprecated em v1.3).

### Security
- Bump <lib> from 4.1.2 to 4.1.5 (CVE-2026-0001).
```

Regras:
- PT-BR no chat, **CHANGELOG sempre em inglês** (face pública do repo).
- Sem entrada genérica tipo "various improvements". Específico ou nada.
- `Security` ganha destaque, com CVE/advisory linkado.
- Entrada referencia task ou PR (#numero).

### Automação do SendSprint

- `python scripts/build_changelog.py --since <tag> --write-unreleased` atualiza o bloco `## [Unreleased]` com Conventional Commits.
- `python scripts/build_changelog.py --promote <version>` promove o bloco `Unreleased` para `## [<version>] - YYYY-MM-DD`.
- `.github/workflows/release-hygiene.yml` roda isso automaticamente:
  - em `push` para `main`, recalcula `docs/assets/coverage-badge.svg` e sincroniza o `Unreleased` quando existe tag base;
  - em `push` de tag `v*.*.*`, promove o changelog para a versão recém-tagueada.

---

## 4. Criar tag

Após bump e CHANGELOG mergeados em `main`:

```bash
git checkout main
git pull --rebase origin main

# valida que CHANGELOG e package version batem
git tag -a v1.5.0 -m "Release 1.5.0"
git push origin v1.5.0
```

Tag deve apontar pro commit em que CHANGELOG e version foram atualizados. Não tag em commit antigo.

> Tag é imutável. Errou? Cria nova patch (`v1.5.1`) com correção. Nunca delete e re-cria tag publicada.

---

## 5. Automação via GitHub Actions

No SendSprint, o fluxo atual é dividido assim:

- `.github/workflows/release-hygiene.yml`
  - gera / atualiza `docs/assets/coverage-badge.svg`;
  - mantém `CHANGELOG.md` com bloco `[Unreleased]`;
  - promove o changelog em pushes de tag `v*.*.*`.
- `.github/workflows/pypi-publish.yml`
  - publica no PyPI quando uma GitHub Release é publicada, usando PyPI Trusted Publishing.

### PyPI Trusted Publishing

O workflow de produção não deve usar `PYPI_API_TOKEN`. A configuração esperada
no PyPI para o projeto `sendsprint` é:

| Claim | Valor |
|---|---|
| Owner | `wesleysimplicio` |
| Repository | `SendSprint` |
| Workflow | `pypi-publish.yml` |
| Environment | vazio / não configurado |
| Trigger | GitHub Release publicada a partir de tag `v*.*.*` |

O workflow precisa manter:

```yaml
permissions:
  contents: read
  id-token: write
```

E a ação `pypa/gh-action-pypi-publish@release/v1` sem `password`.

Exemplo de refresh manual local:

```bash
pytest tests/ --cov=sendsprint --cov-report=xml:coverage.xml
python scripts/generate_coverage_badge.py --coverage coverage.xml --output docs/assets/coverage-badge.svg
python scripts/build_changelog.py --since v0.12.1 --write-unreleased
```

Publicação continua disparada pela release/tag:

```yaml
on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Build artifact
        run: python -m build
      - name: Publish package
        uses: pypa/gh-action-pypi-publish@release/v1
```

Acompanhar o run:

```bash
gh run watch
gh run list --workflow=pypi-publish.yml --limit 5
```

Falhou? Workflow é idempotente, pode re-rodar. Se rollout passou mas smoke falhou, etapa de rollback dispara automático (próxima seção).

---

## 6. Smoke tests pós-release

Pequeno conjunto de cenários críticos rodando contra produção logo após o rollout. Objetivo: detectar regressão grande em < 5min.

Cobertura mínima:
- `pytest tests/ --cov=sendsprint --cov-report=xml:coverage.xml`
- `python scripts/generate_coverage_badge.py --coverage coverage.xml --output docs/assets/coverage-badge.svg`
- `python scripts/build_changelog.py --since <última-tag> --write-unreleased`
- `npm run test:e2e` quando houver `BASE_URL` disponível para o smoke web

Smoke roda dentro do workflow `deploy-prod.yml`. Falha = rollback automático.

---

## 7. Rollback

Quando: smoke falhou, métrica spikou, usuários reportando incidente, sentry com taxa de erro > baseline.

### Estratégia: revert tag e redeploy da anterior

Mais rápido e seguro que tentar fix em produção.

```bash
# identifica tag anterior
gh release list --limit 5

# dispara redeploy da tag anterior
git checkout v1.4.2
gh workflow run deploy-prod.yml --ref v1.4.2

# acompanha
gh run watch
```

### Marca a release ruim

```bash
gh release edit v1.5.0 --notes "ROLLED BACK - see incident #INC-2026-05-07"
```

CHANGELOG ganha nota:

```markdown
## [1.5.0] - 2026-05-07 [ROLLED BACK]
> Rolled back at 14:32 UTC. See incident report INC-2026-05-07.
```

### Pós-rollback

- Postmortem em `.specs/incidents/INC-YYYY-MM-DD.md` em até 48h.
- Fix vai em PR normal (com teste regressivo) e tagueia próxima patch (`v1.5.1`).
- Atualiza skill/playbook se causa-raiz era processo, não código.

---

## 8. Pre-releases e RCs

Para mudanças grandes (MAJOR), considere RC antes da release final:

```bash
git tag v2.0.0-rc.1
git push origin v2.0.0-rc.1
```

- Workflow separado `deploy-rc.yml` envia pra ambiente `rc.<PRODUCT_NAME>.io`.
- Beta testers usam por 3-7 dias antes do tag final `v2.0.0`.
- Bugs em RC viram patch no RC (`v2.0.0-rc.2`), não em PATCH SemVer ainda.

---

## 9. Checklist do release manager

- [ ] `main` verde (build, lint, unit, e2e).
- [ ] Versão bumpada conforme SemVer.
- [ ] `CHANGELOG.md` atualizado, revisado, em inglês.
- [ ] Tag criada apontando pro commit certo.
- [ ] Workflow de deploy completou verde.
- [ ] Smoke tests passaram.
- [ ] Métricas estáveis nos primeiros 30min.
- [ ] Notificação pra `<TEAM>` enviada.
- [ ] Release notes publicadas (`gh release create v1.5.0 -F CHANGELOG.md`).

Em incidente, congelar releases até postmortem fechar com ação concreta no roadmap.
