# SessionStart hook for Windows shells.
# Emits concise project context without requiring Bash.

[CmdletBinding()]
param()

@'
[Agentic-Starter - Skills always-on ativas neste projeto]

Skills padrao:
1. caveman - resposta curta, sem filler.
2. ralph-loop - planejar, executar, testar, corrigir e repetir ate DoD.
3. everything-claude-code - usar revisores/resolvers especializados quando disponiveis.

Padroes deste repo:
- PT-BR para conversa e docs internas; ingles para codigo, commits e docs canonicas.
- Conventional Commits.
- Nunca commitar segredos.
- Antes do commit: ruff critical nos Python staged e pytest tests -q.
'@
