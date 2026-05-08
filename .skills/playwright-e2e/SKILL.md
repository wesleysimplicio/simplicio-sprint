---
name: playwright-e2e
description: escrever ou atualizar testes end-to-end Playwright usados como fallback de transport do SendSprint, garantindo trace, screenshot, vídeo e asserções consistentes
---

# Skill: `playwright-e2e`

Padrão para criar e atualizar testes E2E Playwright **no contexto do SendSprint**. Diferente de produtos com UI própria, o SendSprint usa Playwright como **transport fallback** dos operators (`JiraOperator`, `AzureDevopsOperator`) quando MCP e API REST não estão disponíveis. Esta skill cobre os dois casos:

- **A.** Testes que validam o transport `playwright` dos operators (lendo HTML fixtures ou CDP local).
- **B.** Smoke tests de navegador que dependem do CDP `PLAYWRIGHT_CDP_URL` do `.env.example`.

---

## Trigger

- Task altera `sendsprint/operators/*_operator.py` no transport `playwright`.
- Bug reportado contra fluxo de leitura de sprint via Playwright.
- Necessidade de validar comportamento contra mudança de DOM da Jira/ADO Cloud.
- Usuário pede explicitamente "smoke test playwright", "teste e2e do operator".
- Antes de fechar PR que toca `transport` priority em `operators/`.

---

## Steps

1. **Identifique o cenário**. Caminho feliz (sprint encontrada, items parseados) + erros (login expirado, 5xx, DOM mudou). Cada cenário vira `pytest` com `playwright.sync_api`.
2. **Crie o arquivo** em `tests/e2e/test_<operator>_playwright.py` (Python, não `.spec.ts`). SendSprint é Python — usar `pytest-playwright` ou `playwright.sync_api` direto + monkeypatch.
3. **Use fixtures locais** sempre que possível. HTML estático em `tests/fixtures/jira/<sprint>.html` servido via `http.server` em fixture pytest, em vez de hit em Jira real.
4. **Configure CDP local** quando precisar testar contra browser de verdade. Defaults: `PLAYWRIGHT_CDP_URL=http://127.0.0.1:9222`. Skipar com `pytest.mark.skipif(not cdp_available())` se ausente.
5. **Asserte estado final** com `expect(locator).to_have_text(...)`, `to_have_url(...)`. Não asserte só ausência de erro.
6. **Confirme evidência**. Screenshot do estado final + trace ZIP em `test-results/`. Configurado em `playwright.config.ts` na raiz.
7. **Rode local** com `pytest tests/e2e/ -v --tracing=retain-on-failure`.
8. **Commit**. Inclui `.py` de teste e fixtures HTML. NÃO commita `test-results/` nem `playwright-report/` (estão no `.gitignore`).
9. **PR** anexa screenshot do estado final do caminho feliz + lista cenários cobertos.

---

## Padrões

- **Linguagem**: Python (não TypeScript). SendSprint é Python-first.
- **Naming**: `test_<operator_or_flow>_playwright.py` em `tests/e2e/`.
- **Localização**: `tests/e2e/` (separado de `tests/` unit).
- **Seletores**: prefira `get_by_role`, `get_by_label`, `get_by_test_id`. Evite `locator("div.classe123")`.
- **Espera**: nunca `page.wait_for_timeout(ms)`. Use `expect(...).to_be_visible()`, `to_have_url`.
- **Setup/Teardown**: fixture pytest com `browser_context_args` para isolar.
- **Dados**: gere dados únicos por teste (`uuid.uuid4()`) para evitar colisão.
- **Sem `print`** no spec — use `pytest -v` ou `caplog`.
- **CDP optional**: se browser não disponível, retornar `pytest.skip()` (consistente com `StepReport.status="skipped"` do operator).

---

## Definition of Done

- [ ] Spec roda local sem erro: `pytest tests/e2e/ -v`.
- [ ] Cenários documentados: caminho feliz + ao menos 1 erro.
- [ ] Evidência salva em `test-results/` (trace, screenshot, vídeo conforme config).
- [ ] PR menciona screenshot do estado final + lista os cenários cobertos.
- [ ] Nenhum `wait_for_timeout` no código.
- [ ] Seletores resistentes (role/label/test-id).
- [ ] CI (`.github/workflows/dod.yml`) verde para o job de E2E (quando aplicável).

---

## Exemplo

```python
import pytest
from playwright.sync_api import expect, sync_playwright


@pytest.fixture
def cdp_url(monkeypatch):
    url = "http://127.0.0.1:9222"
    monkeypatch.setenv("PLAYWRIGHT_CDP_URL", url)
    return url


def test_jira_operator_reads_sprint_via_playwright(cdp_url, jira_html_fixture_server):
    """Happy path: operator lê sprint contra HTML fixture local servido em http://127.0.0.1:8765/sprint-42.html"""
    from sendsprint.operators import JiraOperator

    op = JiraOperator(base_url=jira_html_fixture_server, transport="playwright")
    sprint = op.read_sprint(sprint_id=42)

    assert sprint.id == 42
    assert len(sprint.items) > 0
    assert all(item.key.startswith("PROJ-") for item in sprint.items)


def test_jira_operator_skipped_when_cdp_unavailable(monkeypatch):
    """CDP ausente -> operator retorna StepReport(status='skipped')."""
    monkeypatch.delenv("PLAYWRIGHT_CDP_URL", raising=False)

    from sendsprint.operators import JiraOperator

    op = JiraOperator(base_url="https://example.atlassian.net", transport="playwright")
    with pytest.raises(RuntimeError, match="cdp"):
        op.read_sprint(sprint_id=42)
```

---

## Notas

- Configuração canônica em `playwright.config.ts` (raiz) — define output dir e reporters.
- Para Python+Playwright: usar `pytest-playwright` (`pip install pytest-playwright`) e adicionar a `[dev]` extras.
- Trace viewer: `npx playwright show-trace test-results/<trace>.zip`.
- Test flaky é bug. Marcar com `@pytest.mark.skip(reason="flaky, ver issue #N")` enquanto investiga — não silenciar.
