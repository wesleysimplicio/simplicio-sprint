import React from "react";

export type Lang = "pt" | "en";

export const LangContext = React.createContext<Lang>("pt");
export const useLang = (): Lang => React.useContext(LangContext);

export type Strings = {
  // IntroScene
  intro_subtitle: string;
  intro_tag: string;
  // WhatIsScene
  what_eyebrow: string;
  what_title: string;
  what_lede: string;
  what_features: { emoji: string; title: string; desc: string }[];
  // TriggerScene
  trigger_eyebrow: string;
  trigger_title: string;
  trigger_lede: string;
  trigger_terminal_title: string;
  trigger_lines: { prompt?: string; text: string }[];
  trigger_chips: { lang: string; phrase: string }[];
  // StepsScene
  steps_eyebrow: string;
  steps_title: string;
  steps: {
    title: string;
    desc: string;
    details: [string, string];
  }[];
  steps_progress_label: string;
  // IDEsScene
  ides_eyebrow: string;
  ides_title: string;
  ides_lede: string;
  // SetupScene
  setup_eyebrow: string;
  setup_title: string;
  setup_lede: string;
  setup_steps: { title: string; desc: string }[];
  setup_install_title: string;
  setup_msg_stack_detected: string;
  setup_msg_creds_saved: string;
  // OutroScene
  outro_title: string;
  outro_cta: string;
  // Run loop video
  rl_hero_eyebrow: string;
  rl_hero_title: string;
  rl_hero_lede: string;
  rl_round_label: (n: number, of: number) => string;
  rl_fixloop_label: string;
  rl_delivered_label: string;
  rl_chip_running: string;
  rl_chip_idle: string;
  rl_subtitle: string;
  rl_step_names: Record<number, string>;
  rl_regression_failed: string;
  rl_regression_passed: string;
  rl_regression_help_failed: string;
  rl_regression_help_passed: string;
  rl_fixloop_subtitle: string;
  rl_fixloop_intro: string;
  rl_fixloop_patches: string[];
  rl_delivered_title: string;
  rl_delivered_summary: string;
};

export const STRINGS: Record<Lang, Strings> = {
  pt: {
    intro_subtitle: "Sua sprint, entregue do início ao fim",
    intro_tag: "GUIA RÁPIDO • CLAUDE CODE SKILL",
    what_eyebrow: "O QUE É?",
    what_title: "Um agente que entrega sua sprint",
    what_lede: "Você descreve. Ele lê, codifica, testa e abre o PR.",
    what_features: [
      { emoji: "🧭", title: "Lê a sprint", desc: "Jira ou Azure DevOps" },
      { emoji: "🛠️", title: "Codifica e testa", desc: "Worktree + lint + E2E" },
      { emoji: "🛡️", title: "Revisa segurança", desc: "Secrets + audit (flag-only)" },
      { emoji: "🚀", title: "Abre o PR", desc: "GitHub ou Azure DevOps" },
    ],
    trigger_eyebrow: "COMO ATIVAR",
    trigger_title: "Diga a frase mágica",
    trigger_lede:
      "A skill detecta o gatilho em pt-BR, inglês ou espanhol — e também pelo slash command.",
    trigger_terminal_title: "~/sendsprint — claude code",
    trigger_lines: [
      { prompt: "you", text: "rode o sendsprint" },
      { prompt: "claude", text: "→ ativando skill SendSprint…" },
      { prompt: "claude", text: "→ lendo sprint do Jira #42…" },
      { prompt: "claude", text: "✓ 8 itens carregados, iniciando flow" },
    ],
    trigger_chips: [
      { lang: "pt-BR", phrase: "rode o sendsprint" },
      { lang: "en", phrase: "run sendsprint" },
      { lang: "es", phrase: "ejecutar sprint" },
      { lang: "slash", phrase: "/sendsprint" },
    ],
    steps_eyebrow: "O FLOW",
    steps_title: "10 passos automatizados",
    steps: [
      {
        title: "Lê a sprint",
        desc: "Jira ou Azure DevOps",
        details: ["transport: mcp → api → playwright", "--scope mine filtra só você"],
      },
      {
        title: "Mapeia arquitetura",
        desc: "Score < 0.6? gera baseline",
        details: ["ArchitectureMapper.map(repo)", "build_architecture(repo)"],
      },
      {
        title: "Dev: install + build",
        desc: "Worktree isolado, 16 package managers",
        details: ["WorktreeManager", "DevAgent + detect_tech"],
      },
      {
        title: "Lint",
        desc: "19 stacks suportados",
        details: ["eslint • ruff • clippy • golangci", "phpcs • rubocop • dart analyze"],
      },
      {
        title: "Testes",
        desc: "Unit + Playwright E2E",
        details: ["screenshots em evidence/", "TestRunner roda tudo"],
      },
      {
        title: "Segurança (flag-only)",
        desc: "12 padrões + audit dependências",
        details: ["secrets, .env gitignore", "ADR-005: nunca auto-fix"],
      },
      {
        title: "Fix loop",
        desc: "Re-roda até 3× se falhar",
        details: ["MAX_FIX_LOOPS = 3", "lint + tests + security"],
      },
      {
        title: "Commit + push",
        desc: "Worktree branch → origin",
        details: ["git push --force-with-lease", "branch isolada por sprint item"],
      },
      {
        title: "Cria o PR",
        desc: "GitHub gh ou Azure DevOps REST",
        details: ["PrCreator", "URL no RunReport.prs[]"],
      },
      {
        title: "Revisa e entrega",
        desc: "Diff checks + RunReport",
        details: ["sem TODO/FIXME/debug", "report.json exportado"],
      },
    ],
    steps_progress_label: "progresso",
    ides_eyebrow: "ONDE FUNCIONA",
    ides_title: "13 IDEs / agentes prontos",
    ides_lede: "Mesma skill, mesmo gatilho — copia o manifesto e roda.",
    setup_eyebrow: "COMEÇANDO",
    setup_title: "4 passos pra rodar",
    setup_lede:
      "Credenciais ficam no keyring do SO. Depois é só conversar com a skill.",
    setup_steps: [
      { title: "Instale", desc: "pip install -e .[dev]" },
      { title: "Init", desc: "sendsprint init: descobre stack" },
      { title: "Login", desc: "credenciais no OS keyring" },
      { title: "Use", desc: "“rode o sendsprint” no chat" },
    ],
    setup_install_title: "~/sendsprint — setup",
    setup_msg_stack_detected: "stack detectado, .specs/ preenchido",
    setup_msg_creds_saved: "credenciais salvas no keyring (chmod 600)",
    outro_title: "Pronto pra entregar?",
    outro_cta: "rode o sendsprint",
    rl_hero_eyebrow: "O LOOP QUE NÃO PARA",
    rl_hero_title: "rode até passar.",
    rl_hero_lede:
      "Tests + regression + evidência por round, fix-loop automático, PR só quando tudo estiver verde.",
    rl_round_label: (n, of) => `ROUND ${n} / ${of}`,
    rl_fixloop_label: "FIX-LOOP",
    rl_delivered_label: "DELIVERED",
    rl_chip_running: "rodando",
    rl_chip_idle: "aguardando",
    rl_subtitle: "SendSprint • run loop • localhost",
    rl_step_names: {
      1: "lê a sprint",
      2: "mapeia arquitetura",
      3: "dev: install + build",
      4: "lint",
      5: "tests + regressão",
      6: "segurança",
      7: "fix-loop",
      8: "commit + push",
      9: "cria PR",
      10: "entregue",
    },
    rl_regression_failed: "✗ regressão detectada",
    rl_regression_passed: "✓ regressão verde",
    rl_regression_help_failed: "playwright + pytest report — 3 falhas:",
    rl_regression_help_passed: "47 passed · 0 failed · coverage 92.4%",
    rl_fixloop_subtitle: "fix-loop",
    rl_fixloop_intro: "3 testes falharam → iniciando rodada 2 / 3",
    rl_fixloop_patches: [
      "› revert primary color #22d3ee → #7c5cff",
      "› ajustar regex de validação de email",
      "› patches aplicados no worktree, repetindo dev → tests",
    ],
    rl_delivered_title: "Sprint entregue",
    rl_delivered_summary:
      "10/10 steps OK · 2 rounds de fix-loop · regressão verde · coverage 92.4%",
  },
  en: {
    intro_subtitle: "Your sprint, delivered end-to-end",
    intro_tag: "QUICK GUIDE • CLAUDE CODE SKILL",
    what_eyebrow: "WHAT IS IT?",
    what_title: "An agent that ships your sprint",
    what_lede: "You describe. It reads, codes, tests, and opens the PR.",
    what_features: [
      { emoji: "🧭", title: "Reads the sprint", desc: "Jira or Azure DevOps" },
      { emoji: "🛠️", title: "Codes & tests", desc: "Worktree + lint + E2E" },
      { emoji: "🛡️", title: "Security review", desc: "Secrets + audit (flag-only)" },
      { emoji: "🚀", title: "Opens the PR", desc: "GitHub or Azure DevOps" },
    ],
    trigger_eyebrow: "HOW TO TRIGGER",
    trigger_title: "Just say the magic phrase",
    trigger_lede:
      "The skill detects the trigger in English, Portuguese or Spanish — also via slash command.",
    trigger_terminal_title: "~/sendsprint — claude code",
    trigger_lines: [
      { prompt: "you", text: "run sendsprint" },
      { prompt: "claude", text: "→ activating SendSprint skill…" },
      { prompt: "claude", text: "→ reading sprint from Jira #42…" },
      { prompt: "claude", text: "✓ 8 items loaded, starting flow" },
    ],
    trigger_chips: [
      { lang: "en", phrase: "run sendsprint" },
      { lang: "pt-BR", phrase: "rode o sendsprint" },
      { lang: "es", phrase: "ejecutar sprint" },
      { lang: "slash", phrase: "/sendsprint" },
    ],
    steps_eyebrow: "THE FLOW",
    steps_title: "10 automated steps",
    steps: [
      {
        title: "Reads the sprint",
        desc: "Jira or Azure DevOps",
        details: ["transport: mcp → api → playwright", "--scope mine filters to you"],
      },
      {
        title: "Maps architecture",
        desc: "Score < 0.6? builds a baseline",
        details: ["ArchitectureMapper.map(repo)", "build_architecture(repo)"],
      },
      {
        title: "Dev: install + build",
        desc: "Isolated worktree, 16 package managers",
        details: ["WorktreeManager", "DevAgent + detect_tech"],
      },
      {
        title: "Lint",
        desc: "19 stacks supported",
        details: ["eslint • ruff • clippy • golangci", "phpcs • rubocop • dart analyze"],
      },
      {
        title: "Tests",
        desc: "Unit + Playwright E2E",
        details: ["screenshots in evidence/", "TestRunner runs everything"],
      },
      {
        title: "Security (flag-only)",
        desc: "12 patterns + dependency audit",
        details: ["secrets, .env gitignore", "ADR-005: never auto-fix"],
      },
      {
        title: "Fix loop",
        desc: "Re-runs up to 3× on failure",
        details: ["MAX_FIX_LOOPS = 3", "lint + tests + security"],
      },
      {
        title: "Commit + push",
        desc: "Worktree branch → origin",
        details: ["git push --force-with-lease", "isolated branch per sprint item"],
      },
      {
        title: "Opens the PR",
        desc: "GitHub gh or Azure DevOps REST",
        details: ["PrCreator", "URL in RunReport.prs[]"],
      },
      {
        title: "Reviews & ships",
        desc: "Diff checks + RunReport",
        details: ["no TODO/FIXME/debug", "report.json exported"],
      },
    ],
    steps_progress_label: "progress",
    ides_eyebrow: "WHERE IT RUNS",
    ides_title: "13 IDEs / agents ready",
    ides_lede: "Same skill, same trigger — copy the manifest and go.",
    setup_eyebrow: "GETTING STARTED",
    setup_title: "4 steps to run",
    setup_lede:
      "Credentials live in the OS keyring. After that, just talk to the skill.",
    setup_steps: [
      { title: "Install", desc: "pip install -e .[dev]" },
      { title: "Init", desc: "sendsprint init: discovers your stack" },
      { title: "Login", desc: "credentials in the OS keyring" },
      { title: "Use it", desc: "“run sendsprint” in chat" },
    ],
    setup_install_title: "~/sendsprint — setup",
    setup_msg_stack_detected: "stack detected, .specs/ scaffolded",
    setup_msg_creds_saved: "credentials saved to keyring (chmod 600)",
    outro_title: "Ready to ship?",
    outro_cta: "run sendsprint",
    rl_hero_eyebrow: "THE LOOP THAT WON'T STOP",
    rl_hero_title: "run until it passes.",
    rl_hero_lede:
      "Tests + regression + per-round evidence, automatic fix-loop, PR only when everything's green.",
    rl_round_label: (n, of) => `ROUND ${n} / ${of}`,
    rl_fixloop_label: "FIX-LOOP",
    rl_delivered_label: "DELIVERED",
    rl_chip_running: "running",
    rl_chip_idle: "idle",
    rl_subtitle: "SendSprint • run loop • localhost",
    rl_step_names: {
      1: "read sprint",
      2: "map architecture",
      3: "dev: install + build",
      4: "lint",
      5: "tests + regression",
      6: "security",
      7: "fix-loop",
      8: "commit + push",
      9: "open PR",
      10: "delivered",
    },
    rl_regression_failed: "✗ regression detected",
    rl_regression_passed: "✓ regression green",
    rl_regression_help_failed: "playwright + pytest report — 3 failures:",
    rl_regression_help_passed: "47 passed · 0 failed · coverage 92.4%",
    rl_fixloop_subtitle: "fix-loop",
    rl_fixloop_intro: "3 tests failed → starting round 2 / 3",
    rl_fixloop_patches: [
      "› revert primary color #22d3ee → #7c5cff",
      "› fix email validation regex",
      "› patches applied to worktree, replaying dev → tests",
    ],
    rl_delivered_title: "Sprint delivered",
    rl_delivered_summary:
      "10/10 steps OK · 2 fix-loop rounds · regression green · coverage 92.4%",
  },
};

export const useStrings = (): Strings => STRINGS[useLang()];
