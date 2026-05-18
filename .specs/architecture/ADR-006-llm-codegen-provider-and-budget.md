# ADR-006: Adotar provider configurável com budget cap para o LLM codegen

## Status

Aceito

## Data

2026-05-18

## Autores

- Wesley Simplicio
- Codex

## Contexto

O Sprint 2 introduz geração opcional de código por item da sprint. O repositório já tinha um `LlmClient` multi-provider e um `CodeGenerator`, mas eles ainda não tinham um contrato operacional claro para orçamento, modelo e ativação por workspace.

Sem essa decisão, o fluxo corria dois riscos:

- custo imprevisível ao chamar o provedor padrão sem limite explícito;
- acoplamento prematuro a um único vendor;
- dificuldade para habilitar codegen em um workspace sem mexer em código.

## Decisão

Adotamos um provider configurável por `workspace.yaml`, com budget cap explícito e codegen estritamente opt-in.

Aplicação:

- `workspace.yaml::code_generation.enabled` controla a ativação;
- `provider`, `model` e `base_url` podem ser sobrescritos por workspace;
- `max_usd` e `max_tokens` são obrigatórios como guardrails locais;
- o fluxo sempre passa pelo diff unificado gerado pelo modelo e aplica o patch via `git apply`, mantendo lint, testes e review como gates obrigatórios.

## Consequências

### Positivas (+)

- reduz risco de custo descontrolado por chamada de LLM;
- permite usar Anthropic, OpenAI, Google, Groq ou Ollama sem refator do fluxo;
- mantém o comportamento default inalterado para quem não habilitar o recurso.

### Negativas (-)

- adiciona mais superfície de configuração no `workspace.yaml`;
- o estimador de custo continua aproximado, não contábil;
- diffs gerados pelo modelo ainda podem falhar em `git apply`.

### Neutras / observações

- a geração de código continua observável como `StepReport`, sem atalho para commit automático.

## Alternativas consideradas

### Alternativa A — Provider fixo em código

- Mais simples de implementar.
- Descartada porque forçaria um vendor e reduziria a utilidade do SendSprint em workspaces heterogêneos.

### Alternativa B — Codegen sempre ligado

- Removeria uma decisão do operador.
- Descartada porque mudaria o comportamento default e aumentaria custo/risco em toda execução.

## Critério de revisão

- Revisar se o estimador de custo se mostrar impreciso o bastante para causar budget overruns.
- Revisar se um provider único se tornar padrão dominante e a configuração deixar de gerar valor.

## Links

- Issue / task: `#17`
- Documentos relacionados: [DESIGN](./DESIGN.md), [PATTERNS](./PATTERNS.md)
