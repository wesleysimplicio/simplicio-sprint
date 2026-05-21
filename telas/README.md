# Telas SendSprint

Esta pasta concentra o pacote de design operacional do SendSprint.

Arquivos:
- `SCREEN_INVENTORY.md`: inventário completo de telas por plataforma, fluxo e estado.
- `GPT_IMAGE_2_PROMPTS.md`: prompts detalhados para gerar os mockups no estilo clean, funcional e próximo de Codex/Claude.
- `manifest.json`: mapa estruturado das superfícies, módulos e eventos.
- `exports/`: destino reservado para imagens exportadas e tratadas para versionamento.

Observação:
- O prompt pack foi preparado para geração com `gpt-image-2`.
- Nesta sessão, o repositório passa a versionar o inventário, os prompts e o plano de layout. As imagens geradas em sessão interativa dependem do pipeline do gerador e podem precisar ser exportadas manualmente para `telas/exports/` em uma etapa posterior.
