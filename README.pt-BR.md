# SendSprint

<p align="center">
  <img src="./docs/assets/sendsprint-hero.png" alt="SendSprint transforma tarefas da sprint em pull requests validados" />
</p>

> 🇧🇷 Português. Read in English: [README.md](README.md).

**SendSprint é um agente autônomo que finaliza os cards atribuídos a você.**
Ele lê sua sprint no **Jira**, **Azure DevOps** ou **GitHub Issues**, manda cada
tarefa para o **[simplicio-cli](https://github.com/wesleysimplicio/simplicio-cli)**
executar o código, coleta evidências (testes + tela), faz commit num branch
isolado e abre um **pull request em draft** com as evidências anexadas. Depois
acompanha o PR e devolve seus comentários de review ao simplicio até você aprovar.

Você não fica no teclado invocando. Um trigger agendado roda; seu único trabalho
é **revisar o PR em draft**.

## A divisão que faz funcionar

- **SendSprint = o agente (o cérebro).** Dono do fluxo do início ao fim.
- **simplicio-cli = o executor (a mão).** Sem estado. Roda *uma task → diff
  aplicado*. Não sabe o que é sprint, branch ou PR.

```
trigger (cron / GitHub Action / Claude web)   ← tira você do loop
  └─ SendSprint (agente)
       1. lê a sprint        Jira / Azure DevOps / GitHub   (--scope mine)
       2. organiza as tasks
       3. simplicio task ...  ← a única coisa que o simplicio faz
       3b. coleta evidência   testes + screenshot Playwright
       4. commit + push
       5. abre PR em DRAFT    ← sua única superfície de revisão
       6. anexa evidência     resultado dos testes + imagens embutidas
       7. atualiza o ticket   "In Review" + link do PR
       8. acompanha o PR       comentário? → simplicio ajusta → nova evidência
            ✓ você aprova → merge → próximo card
```

## Instalação

```bash
pip install -e .
pip install simplicio-cli
pip install -e ".[screenshot]" && playwright install chromium   # opcional
```

## Uso

```bash
sendsprint login jira
sendsprint run jira 42 --repo . --repo-slug owner/repo --scope mine

# desatendido (sem você no teclado)
sendsprint watch jira 42 --repo . --repo-slug owner/repo --once
```

Veja [README.md](README.md) para detalhes de arquitetura, variáveis de ambiente
e o trigger agendado em [`.github/workflows/sendsprint.yml`](./.github/workflows/sendsprint.yml).

## Licença

MIT — veja [LICENSE](./LICENSE).
