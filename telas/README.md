# Telas SendSprint

Esta pasta concentra o pacote de design operacional do SendSprint.

Arquivos:
- `SCREEN_INVENTORY.md`: inventario completo de telas por plataforma, fluxo e estado.
- `GPT_IMAGE_2_PROMPTS.md`: prompts detalhados para gerar os mockups no estilo clean, funcional e proximo de Codex/Claude.
- `manifest.json`: mapa estruturado das superficies, modulos e eventos.
- `exports/`: destino reservado para imagens exportadas e tratadas para versionamento.
- `extract_storyboard_screens.py`: recorta os storyboards gerados em imagens individuais por tela.

Boards versionados nesta rodada:
- `exports/web-master-storyboard.png`
- `exports/desktop-master-storyboard.png`
- `exports/mobile-console-master-storyboard.png`
- `exports/enterprise-operations-storyboard.png`

Telas individuais:
- `exports/screens/manifest.json`: manifest gerado com origem, crop box, superficie e caminho de cada tela.
- `exports/screens/web/`: web app, incluindo login, shell, conexoes, backlog, run, resultado e operacoes.
- `exports/screens/desktop-windows/`: shell desktop Windows.
- `exports/screens/desktop-macos/`: shell desktop macOS.
- `exports/screens/mobile-ios/`: fluxo iPhone.
- `exports/screens/mobile-android/`: fluxo Android.
- `exports/screens/console/`: console UX e estados do fluxo console.
- `exports/screens/enterprise/`: telas corporativas usadas tambem como referencias para web manager/admin/reports.

Observacao:
- O prompt pack foi preparado para geracao com `gpt-image-2`.
- Os boards mestres em `exports/*.png` continuam sendo a fonte visual. Os arquivos em `exports/screens/**` sao recortes fieis desses boards, sem redesenho ou reinterpretacao.
