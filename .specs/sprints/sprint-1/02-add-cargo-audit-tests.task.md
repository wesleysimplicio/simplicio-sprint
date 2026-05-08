---
id: TASK-002
title: Add cargo-audit coverage tests to security reviewer
sprint: sprint-1
owner: @sendsprint-core
status: todo
---

# TASK-002 — Add cargo-audit coverage tests to security reviewer

## Contexto

`sendsprint/agents/security_reviewer.py` já chama `cargo audit --json` para projetos Rust (referenciado em `CHANGELOG.md` v0.3.x), mas a suíte `tests/test_security_reviewer.py` não cobre o caminho cargo, só `npm audit` e o scan de secrets. Sem teste, qualquer mudança no parser de saída cargo pode quebrar silenciosamente. Origem: gap detectado durante adoção do gate DoD — cobertura mínima do diff ≥ 80% exige que todo branch executável tenha teste. Esta task valida o pipeline Ralph contra uma mudança que **só é teste** (sem código de produção novo) — útil pra confirmar que o loop reconhece DoD verde só com teste.

Impactados:

- `tests/test_security_reviewer.py` — novos casos para cargo audit (happy, vulns presentes, binário ausente, JSON corrompido).
- `tests/fixtures/cargo-audit-output.json` — payload sintético usado pelos testes.
- `sendsprint/agents/security_reviewer.py` — pequeno ajuste no parser se algum AC falhar (mantenha mudança cirúrgica).

## Acceptance Criteria

- [ ] AC-1 — Quando `cargo audit --json` retorna 0 vulnerabilidades, `SecurityReviewer.scan()` retorna `StepReport(step=6, status="ok", details={"cargo_findings": 0, ...})`.
- [ ] AC-2 — Quando `cargo audit --json` retorna 3 vulnerabilidades, `details.cargo_findings == 3` e `findings[*]` contém `{advisory_id, severity, package}`.
- [ ] AC-3 — Quando `cargo` não está no PATH, `StepReport.status == "skipped"`, `details.reason == "cargo not installed"`, sem levantar exceção.
- [ ] AC-4 — Quando `cargo audit` retorna stdout não-JSON, `StepReport.status == "failed"`, `details.error` contém `"json parse error"`.
- [ ] AC-5 — Cap de 20 findings por repo (regra existente do `AGENTS.md` §5) é respeitado: 25 vulns no input → 20 em `findings`, `details.truncated == True`.

## Out of scope

- Não modifica scan de secrets nem `npm audit` (já cobertos).
- Não adiciona `pip-audit` (Python) — existe item separado no backlog.
- Não publica nova versão major: bump é patch (`0.4.0 → 0.4.1`) por ser only-tests + parser fix.

## Test plan

### Unit

- [ ] `test_security_cargo_clean` — mock `subprocess.run` retornando JSON com `vulnerabilities.count == 0`. Assertar `status="ok"`, `cargo_findings=0`.
- [ ] `test_security_cargo_with_vulns` — JSON com 3 vulns. Assertar `cargo_findings=3` e shape de cada finding.
- [ ] `test_security_cargo_missing_binary` — `subprocess.run` levanta `FileNotFoundError`. Assertar `status="skipped"`, `reason="cargo not installed"`.
- [ ] `test_security_cargo_invalid_json` — stdout = `"not json"`. Assertar `status="failed"` e `error` mencionando parse.
- [ ] `test_security_cargo_truncates_at_20` — JSON com 25 vulns. Assertar `len(findings) == 20`, `truncated=True`.
- [ ] Cobertura de `sendsprint/agents/security_reviewer.py` ≥ 90% após adicionar os testes.

### Integration

- [ ] `test_flow_security_step_in_rust_repo` — `SprintFlow` em fixture `tests/fixtures/rust-app/` (com `Cargo.toml`) atravessa step 6 e retorna `StepReport.step == 6`.

### End-to-end (Playwright fallback)

N/A — não toca operators.

```bash
ruff check sendsprint/agents/security_reviewer.py tests/test_security_reviewer.py
pytest tests/test_security_reviewer.py -v --cov=sendsprint/agents/security_reviewer --cov-report=term-missing
```

## Definition of Done

- [ ] Todos os ACs verificados.
- [ ] `pytest tests/ -v` 100% verde.
- [ ] Coverage de `security_reviewer.py` ≥ 90%.
- [ ] `ruff check` limpo.
- [ ] Versão bumpada para `0.4.1` nos 4 lugares.
- [ ] `CHANGELOG.md` recebe entrada `Fixed` ou `Tests` (escolher conforme houver fix de parser).
- [ ] PR referencia esta task.
- [ ] Status atualizado em `BACKLOG.md` (linha relacionada) e `SPRINT.md`.

## Pegadinhas conhecidas

- `cargo audit --json` formata `vulnerabilities.list[].advisory.id` (string, ex: `RUSTSEC-2024-0001`) — não confundir com `id` numérico.
- Testes precisam de `monkeypatch.setattr("subprocess.run", ...)` — não chamar cargo de verdade no CI.
- Cap de 20 já existe — só validar comportamento, não reimplementar.
- Manter exit code 1 do `cargo audit` quando há vulns NÃO marca o step como `failed` — `vulns > 0` é informativo (security é flag-only per `AGENTS.md §7`).

## Links

- Backlog: `.specs/sprints/BACKLOG.md` (gap detectado durante #1)
- Sprint: `.specs/sprints/sprint-1/SPRINT.md`
- Reviewer atual: `sendsprint/agents/security_reviewer.py`
- Padrão de fixture: `tests/conftest.py`
- Issue: `#<numero>` (criar ao iniciar)
- PR: `#<numero>` (preencher ao abrir)
