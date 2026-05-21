import React from "react";
import {
  AbsoluteFill,
  Sequence,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { AnimatedText } from "./components/AnimatedText";
import { Background } from "./components/Background";
import { Card } from "./components/Card";
import { Logo } from "./components/Logo";
import { Particles } from "./components/Particles";
import { Terminal, type TerminalLine } from "./components/Terminal";
import { Soundtrack } from "./Soundtrack";
import { FPS, theme } from "./theme";

export type PromoLang = "pt" | "en";

const PROMO_SCENES = {
  hook: { start: 0, dur: 90 },
  shell: { start: 90, dur: 120 },
  connect: { start: 210, dur: 120 },
  backlog: { start: 330, dur: 150 },
  execution: { start: 480, dur: 150 },
  manager: { start: 630, dur: 120 },
  outro: { start: 750, dur: 120 },
} as const;

export const PROMO_TOTAL_FRAMES = 870;

export const promoCues = [
  { frame: 0, cue: "whoosh" as const, volume: 0.35 },
  { frame: 72, cue: "click" as const, volume: 0.3 },
  { frame: 120, cue: "click" as const, volume: 0.32 },
  { frame: 210, cue: "error" as const, volume: 0.38 },
  { frame: 252, cue: "whoosh" as const, volume: 0.42 },
  { frame: 330, cue: "click" as const, volume: 0.32 },
  { frame: 390, cue: "click" as const, volume: 0.32 },
  { frame: 450, cue: "success" as const, volume: 0.46 },
  { frame: 540, cue: "click" as const, volume: 0.34 },
  { frame: 612, cue: "success" as const, volume: 0.5 },
  { frame: 690, cue: "click" as const, volume: 0.32 },
  { frame: 810, cue: "success" as const, volume: 0.56 },
];

const copy = {
  pt: {
    hookTag: "SENDSPRINT · PROMO",
    hookTitle: "A sprint entra. A entrega sai.",
    hookSubtitle:
      "Console + Web para conectar backlog, importar sprint, executar tarefas e deixar tudo rastreado.",
    shellEyebrow: "CHAT-FIRST OPERATION",
    shellTitle: "Comece pelo chat. O SendSprint assume o fluxo.",
    shellBody:
      "Uma shell limpa, no estilo workspace operacional: login, contexto vazio, botão iniciar e importação guiada da sprint.",
    shellPrompt: "Importe minha sprint do Azure DevOps e prepare o backlog.",
    shellHints: [
      "Login por e-mail",
      "Tela inicial vazia",
      "Botão iniciar",
      "Conectar Azure, Jira ou GitHub",
    ],
    connectEyebrow: "CONEXÃO COM FALLBACK REAL",
    connectTitle: "Se a API falhar, o SendSprint continua.",
    connectBody:
      "401 na importação? O fluxo ativa Playwright e pode escalar para Claude, Codex, Hermes e OpenClaw até capturar a sprint.",
    fallbackSteps: [
      "Sprint URL recebida e PAT validado",
      "API retornou 401",
      "Fallback Playwright capturando board e metadados",
      "Claude / Codex / Hermes / OpenClaw se necessário",
      "Backlog importado no SendSprint",
    ],
    backlogEyebrow: "KANBAN OPERACIONAL",
    backlogTitle: "O board vira o centro do trabalho.",
    backlogBody:
      "Cards com detalhes do Jira, Azure ou GitHub, histórico completo de movimentação, logs por task e bloqueio de execução sem repositório configurado.",
    backlogColumns: [
      "Backlog",
      "Planning",
      "Coding",
      "Testing",
      "Review",
      "Deploy",
    ],
    executionEyebrow: "EXECUÇÃO COM CONTEXTO",
    executionTitle: "Mapeia, planeja, programa, testa e evidencia.",
    executionBody:
      "Cada task passa por arquitetura, planning, coding, testing e review. Os logs mostram tudo: branch, worktree, lint, testes, tokens e modelo.",
    executionLines: [
      { prompt: "ui", text: "Task movida para Planning: SS-2418" },
      { prompt: "flow", text: "mapeando arquitetura com llm-project-mapper..." },
      { prompt: "flow", text: "worktree criado em feat/ss-2418" },
      { prompt: "flow", text: "rodando lint + testes + evidencia..." },
      { prompt: "flow", text: "PR pronto, aguardando review humana" },
    ],
    managerEyebrow: "VISÃO DE GESTÃO",
    managerTitle: "Empresa e gerente enxergam o que está acontecendo.",
    managerBody:
      "Horas, tokens, modelos por tarefa, status da sprint, histórico por usuário e relatórios de operação em tempo real.",
    managerMetrics: [
      { label: "Sprints ativas", value: "12", delta: "+3" },
      { label: "Tokens hoje", value: "1.8M", delta: "-12%" },
      { label: "Horas rastreadas", value: "284h", delta: "+41h" },
      { label: "Modelos em uso", value: "5", delta: "Claude / Codex" },
    ],
    outroTitle: "Conecte. Importe. Entregue.",
    outroBody:
      "Menos coordenação manual. Mais backlog operando com contexto, evidência e fluxo rastreável do começo ao fim.",
    outroCta: "Teste local agora com Console + Web",
  },
  en: {
    hookTag: "SENDSPRINT · PROMO",
    hookTitle: "Sprint in. Delivery out.",
    hookSubtitle:
      "Console + Web to connect backlog, import sprints, execute tasks, and keep every move auditable.",
    shellEyebrow: "CHAT-FIRST OPERATION",
    shellTitle: "Start in chat. Let SendSprint run the flow.",
    shellBody:
      "A clean operational shell: sign in, land on an empty workspace, hit start, and connect your sprint intake.",
    shellPrompt: "Import my Azure DevOps sprint and prepare the backlog.",
    shellHints: [
      "Email login",
      "Empty landing shell",
      "Start button",
      "Connect Azure, Jira, or GitHub",
    ],
    connectEyebrow: "REAL FALLBACK CHAIN",
    connectTitle: "If the API fails, SendSprint keeps going.",
    connectBody:
      "401 during import? The flow activates Playwright and can escalate to Claude, Codex, Hermes, and OpenClaw until the sprint is captured.",
    fallbackSteps: [
      "Sprint URL received and PAT validated",
      "API returned 401",
      "Playwright fallback capturing board and metadata",
      "Claude / Codex / Hermes / OpenClaw if needed",
      "Backlog imported into SendSprint",
    ],
    backlogEyebrow: "OPERATIONS KANBAN",
    backlogTitle: "The board becomes the operating center.",
    backlogBody:
      "Cards pull full Jira, Azure, or GitHub context, keep movement history, expose per-task logs, and refuse execution until repositories are configured.",
    backlogColumns: [
      "Backlog",
      "Planning",
      "Coding",
      "Testing",
      "Review",
      "Deploy",
    ],
    executionEyebrow: "EXECUTION WITH CONTEXT",
    executionTitle: "Map, plan, code, test, and capture evidence.",
    executionBody:
      "Every task moves through architecture, planning, coding, testing, and review. Logs show branch, worktree, lint, tests, tokens, and model usage.",
    executionLines: [
      { prompt: "ui", text: "Task moved to Planning: SS-2418" },
      { prompt: "flow", text: "mapping architecture with llm-project-mapper..." },
      { prompt: "flow", text: "worktree created at feat/ss-2418" },
      { prompt: "flow", text: "running lint + tests + evidence..." },
      { prompt: "flow", text: "PR ready, waiting for human review" },
    ],
    managerEyebrow: "MANAGER VIEW",
    managerTitle: "Leads and companies see what's happening.",
    managerBody:
      "Hours, tokens, models per task, sprint status, per-user history, and operational reports in real time.",
    managerMetrics: [
      { label: "Active sprints", value: "12", delta: "+3" },
      { label: "Tokens today", value: "1.8M", delta: "-12%" },
      { label: "Tracked hours", value: "284h", delta: "+41h" },
      { label: "Models in use", value: "5", delta: "Claude / Codex" },
    ],
    outroTitle: "Connect. Import. Deliver.",
    outroBody:
      "Less manual coordination. More backlog moving with context, evidence, and an auditable flow from start to finish.",
    outroCta: "Test it locally now with Console + Web",
  },
} as const;

type Props = { lang?: PromoLang };

const promoBlue = "#58a6ff";
const promoBlueSoft = "#8cd0ff";
const promoBlueDeep = "#0b1731";

export const SendSprintLaunchPromo: React.FC<Props> = ({ lang = "pt" }) => {
  const t = copy[lang];

  return (
    <AbsoluteFill style={{ background: "#040814" }}>
      <Soundtrack cues={promoCues} musicVolume={0.13} />
      <Sequence from={PROMO_SCENES.hook.start} durationInFrames={PROMO_SCENES.hook.dur}>
        <HookScene title={t.hookTitle} subtitle={t.hookSubtitle} tag={t.hookTag} />
      </Sequence>
      <Sequence from={PROMO_SCENES.shell.start} durationInFrames={PROMO_SCENES.shell.dur}>
        <ShellScene
          eyebrow={t.shellEyebrow}
          title={t.shellTitle}
          body={t.shellBody}
          prompt={t.shellPrompt}
          hints={t.shellHints}
        />
      </Sequence>
      <Sequence
        from={PROMO_SCENES.connect.start}
        durationInFrames={PROMO_SCENES.connect.dur}
      >
        <ConnectScene
          eyebrow={t.connectEyebrow}
          title={t.connectTitle}
          body={t.connectBody}
          steps={t.fallbackSteps}
        />
      </Sequence>
      <Sequence
        from={PROMO_SCENES.backlog.start}
        durationInFrames={PROMO_SCENES.backlog.dur}
      >
        <BacklogScene
          eyebrow={t.backlogEyebrow}
          title={t.backlogTitle}
          body={t.backlogBody}
          columns={t.backlogColumns}
        />
      </Sequence>
      <Sequence
        from={PROMO_SCENES.execution.start}
        durationInFrames={PROMO_SCENES.execution.dur}
      >
        <ExecutionScene
          eyebrow={t.executionEyebrow}
          title={t.executionTitle}
          body={t.executionBody}
          lines={t.executionLines}
        />
      </Sequence>
      <Sequence
        from={PROMO_SCENES.manager.start}
        durationInFrames={PROMO_SCENES.manager.dur}
      >
        <ManagerScene
          eyebrow={t.managerEyebrow}
          title={t.managerTitle}
          body={t.managerBody}
          metrics={t.managerMetrics}
        />
      </Sequence>
      <Sequence from={PROMO_SCENES.outro.start} durationInFrames={PROMO_SCENES.outro.dur}>
        <OutroScene title={t.outroTitle} body={t.outroBody} cta={t.outroCta} />
      </Sequence>
    </AbsoluteFill>
  );
};

const sceneOpacity = (frame: number, durationInFrames: number) => {
  const fadeIn = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 16, durationInFrames],
    [1, 0],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    },
  );
  return fadeIn * fadeOut;
};

const SectionIntro: React.FC<{
  eyebrow: string;
  title: string;
  body: string;
  width?: number;
}> = ({ eyebrow, title, body, width = 760 }) => (
  <div className="flex flex-col gap-4" style={{ maxWidth: width }}>
    <div
      className="font-mono text-[17px] tracking-[0.25em] text-ss-blue-soft"
    >
      {eyebrow}
    </div>
    <div
      className="font-sans text-[56px] leading-[1.02] font-extrabold text-ss-text"
      style={{ maxWidth: width }}
    >
      {title}
    </div>
    <div
      className="font-sans text-[22px] leading-[1.5] text-ss-muted"
      style={{ maxWidth: width }}
    >
      {body}
    </div>
  </div>
);

const HookScene: React.FC<{
  tag: string;
  title: string;
  subtitle: string;
}> = ({ tag, title, subtitle }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = sceneOpacity(frame, durationInFrames);
  const slide = interpolate(frame, [0, 24], [40, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity }}>
      <Background variant="deep" />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 18% 20%, rgba(88,166,255,0.25), transparent 35%), radial-gradient(circle at 78% 35%, rgba(140,208,255,0.18), transparent 30%)",
        }}
      />
      <Particles count={24} color="rgba(88,166,255,0.5)" speed={0.2} />
      <AbsoluteFill
        style={{
          padding: 88,
          display: "grid",
          gridTemplateColumns: "0.95fr 1.05fr",
          alignItems: "center",
          gap: 40,
          transform: `translateY(${slide}px)`,
        }}
      >
        <div style={{ display: "flex", justifyContent: "center" }}>
          <Logo size={280} />
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div
            style={{
              color: promoBlueSoft,
              fontFamily: theme.fontMono,
              fontSize: 18,
              letterSpacing: 5,
            }}
          >
            {tag}
          </div>
          <AnimatedText
            text={title}
            size={96}
            weight={900}
            align="left"
            gradient
            letterStagger={1.3}
          />
          <div
            style={{
              color: theme.textMuted,
              fontFamily: theme.fontSans,
              fontSize: 28,
              lineHeight: 1.45,
              maxWidth: 760,
            }}
          >
            {subtitle}
          </div>
          <div style={{ display: "flex", gap: 14, marginTop: 12 }}>
            <HeroBadge text="Azure · Jira · GitHub" />
            <HeroBadge text="Console + Web" />
            <HeroBadge text="Logs + Evidence" />
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const HeroBadge: React.FC<{ text: string }> = ({ text }) => (
  <div
    className="ss-pill ss-fluid px-4 py-2.5 font-mono text-base text-ss-text"
    style={{
      background: "rgba(88,166,255,0.1)",
      borderColor: "rgba(88,166,255,0.28)",
    }}
  >
    {text}
  </div>
);

const AppShell: React.FC<{
  section: string;
  title: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
}> = ({ section, title, children, footer }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const lift = spring({
    frame,
    fps,
    config: { damping: 18, stiffness: 130, mass: 0.65 },
  });

  return (
    <Card
      className="ss-glass ss-fluid overflow-hidden"
      width={1760}
      padding={0}
      glow="rgba(88,166,255,0.18)"
      style={{
        overflow: "hidden",
        transform: `translateY(${interpolate(lift, [0, 1], [32, 0])}px) scale(${interpolate(
          lift,
          [0, 1],
          [0.96, 1],
        )})`,
      }}
    >
      <div
        style={{
          height: 980,
          background: "linear-gradient(180deg, rgba(8,12,28,0.98), rgba(6,10,23,0.94))",
          display: "grid",
          gridTemplateColumns: "280px 1fr",
        }}
      >
        <div
          className="flex flex-col gap-[18px] border-r border-ss-blue/15 bg-[linear-gradient(180deg,rgba(10,16,34,0.96),rgba(7,12,26,0.92))] px-[22px] py-[26px]"
        >
          <div className="flex items-center gap-3">
            <div
              className="ss-blue-gradient flex h-[42px] w-[42px] items-center justify-center rounded-[14px] font-mono text-[18px] font-black text-ss-blue-deep"
            >
              SS
            </div>
            <div className="flex flex-col gap-0.5">
              <div
                className="font-sans text-[22px] font-bold text-ss-text"
              >
                SendSprint
              </div>
              <div
                className="font-mono text-sm text-ss-muted"
              >
                Console + Web
              </div>
            </div>
          </div>
          <SidebarItem label="Chat" active={section === "Chat"} />
          <SidebarItem label="Backlog" active={section === "Backlog"} />
          <SidebarItem label="Runs" active={section === "Runs"} />
          <SidebarItem label="Manager" active={section === "Manager"} />
          <SidebarItem label="Support" active={section === "Support"} />
          <div style={{ flex: 1 }} />
          <div
            className="ss-glass-soft ss-fluid flex flex-col gap-2 rounded-[18px] p-[18px]"
          >
            <div
              className="font-mono text-[13px] tracking-[0.16em] text-ss-blue-soft"
            >
              ACTIVE WORKSPACE
            </div>
            <div
              className="font-sans text-[20px] font-bold text-ss-text"
            >
              acme / nebula / orion
            </div>
            <div
              className="font-sans text-[15px] leading-[1.45] text-ss-muted"
            >
              Sprint import, agent execution, evidence, and delivery history.
            </div>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column" }}>
          <div
            className="flex h-[86px] items-center justify-between border-b border-ss-blue/12 bg-[rgba(7,11,24,0.82)] px-7"
          >
            <div className="flex flex-col gap-1">
              <div
                className="font-mono text-[13px] tracking-[0.16em] text-ss-muted"
              >
                {section.toUpperCase()}
              </div>
              <div
                className="font-sans text-[28px] font-bold text-ss-text"
              >
                {title}
              </div>
            </div>
            <div className="flex gap-3">
              <HeaderPill label="Connected" tone="blue" />
              <HeaderPill label="Sprint live" tone="green" />
              <HeaderPill label="Free mode" tone="neutral" />
            </div>
          </div>
          <div style={{ flex: 1, padding: 28, display: "flex", flexDirection: "column" }}>
            {children}
          </div>
          {footer ? (
            <div
              style={{
                borderTop: "1px solid rgba(88,166,255,0.12)",
                padding: "18px 28px 24px",
                background: "rgba(6,10,22,0.94)",
              }}
            >
              {footer}
            </div>
          ) : null}
        </div>
      </div>
    </Card>
  );
};

const SidebarItem: React.FC<{ label: string; active?: boolean }> = ({
  label,
  active = false,
}) => (
  <div
    className={`ss-fluid flex h-12 items-center rounded-[14px] px-[14px] font-sans text-[18px] ${
      active
        ? "border border-ss-blue/20 bg-ss-blue/14 font-bold text-ss-text"
        : "border border-transparent font-medium text-ss-muted"
    }`}
  >
    {label}
  </div>
);

const HeaderPill: React.FC<{
  label: string;
  tone: "blue" | "green" | "neutral";
}> = ({ label, tone }) => {
  const color =
    tone === "green" ? theme.success : tone === "blue" ? promoBlueSoft : theme.textMuted;
  const bg =
    tone === "green"
      ? "rgba(52,211,153,0.12)"
      : tone === "blue"
        ? "rgba(88,166,255,0.12)"
        : "rgba(255,255,255,0.06)";
  return (
    <div
      className="ss-fluid rounded-full border px-4 py-2.5 font-mono text-[14px]"
      style={{
        borderColor: `${color}33`,
        color,
        background: bg,
      }}
    >
      {label}
    </div>
  );
};

const ShellScene: React.FC<{
  eyebrow: string;
  title: string;
  body: string;
  prompt: string;
  hints: readonly string[];
}> = ({ eyebrow, title, body, prompt, hints }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = sceneOpacity(frame, durationInFrames);

  return (
    <AbsoluteFill style={{ opacity }}>
      <Background variant="soft" />
      <Particles count={18} color="rgba(88,166,255,0.45)" speed={0.18} />
      <AbsoluteFill style={{ padding: 60, display: "flex", alignItems: "center" }}>
        <AppShell
          section="Chat"
          title="Empty shell ready to start"
          footer={<Composer text={prompt} frameOffset={18} />}
        >
          <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: 24, flex: 1 }}>
            <Card
              className="ss-glass ss-fluid rounded-[28px]"
              padding={28}
              glow="rgba(88,166,255,0.12)"
              style={{ display: "flex", flexDirection: "column", gap: 24 }}
            >
              <SectionIntro eyebrow={eyebrow} title={title} body={body} width={760} />
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
                  gap: 12,
                }}
              >
                {hints.map((hint, index) => (
                  <HintTile key={hint} text={hint} delay={index * 8} />
                ))}
              </div>
              <div
                style={{
                  flex: 1,
                  borderRadius: 22,
                  border: "1px dashed rgba(88,166,255,0.26)",
                  background:
                    "linear-gradient(180deg, rgba(88,166,255,0.06), rgba(88,166,255,0.03))",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  minHeight: 260,
                }}
              >
                <div style={{ textAlign: "center", display: "flex", flexDirection: "column", gap: 14 }}>
                  <div
                    style={{
                      color: theme.text,
                      fontFamily: theme.fontSans,
                      fontSize: 36,
                      fontWeight: 700,
                    }}
                  >
                    Tudo começa vazio.
                  </div>
                  <div
                    style={{
                      color: theme.textMuted,
                      fontFamily: theme.fontSans,
                      fontSize: 20,
                    }}
                  >
                    Login, contexto limpo e início guiado para a sprint.
                  </div>
                  <div
                    style={{
                      alignSelf: "center",
                      marginTop: 8,
                      padding: "14px 20px",
                      borderRadius: 14,
                      background: "linear-gradient(135deg, #58a6ff, #8cd0ff)",
                      color: promoBlueDeep,
                      fontFamily: theme.fontSans,
                      fontSize: 18,
                      fontWeight: 800,
                    }}
                  >
                    Iniciar
                  </div>
                </div>
              </div>
            </Card>
            <Card
              className="ss-glass-soft ss-fluid rounded-[28px]"
              padding={28}
              glow="rgba(88,166,255,0.12)"
              style={{ display: "flex", flexDirection: "column", gap: 18 }}
            >
              <SectionLabel text="SESSION" />
              <UserCard />
              <SectionLabel text="INPUT MODES" />
              <ModePill text="Azure DevOps sprint" active />
              <ModePill text="Jira sprint" />
              <ModePill text="GitHub issues" />
              <ModePill text="Manual backlog" />
            </Card>
          </div>
        </AppShell>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Composer: React.FC<{ text: string; frameOffset?: number }> = ({
  text,
  frameOffset = 0,
}) => {
  const frame = useCurrentFrame();
  const typed = Math.min(text.length, Math.max(0, Math.floor((frame - frameOffset) * 1.8)));
  const visible = text.slice(0, typed);
  const showCursor = Math.floor(frame / 12) % 2 === 0;
  return (
    <div
      className="ss-panel-border ss-fluid flex h-[72px] items-center justify-between gap-[18px] rounded-[20px] bg-[rgba(12,18,36,0.96)] pl-[22px] pr-[18px]"
    >
      <div
        className="flex items-center gap-2 font-mono text-[18px] text-ss-text"
      >
        <span className="text-ss-blue-soft">you</span>
        <span>
          {visible}
          {showCursor ? <span className="text-ss-blue-soft">|</span> : null}
        </span>
      </div>
      <div
        className="ss-blue-gradient ss-fluid flex h-[42px] w-[42px] items-center justify-center rounded-[14px] font-sans text-[18px] font-black text-ss-blue-deep"
      >
        ↑
      </div>
    </div>
  );
};

const HintTile: React.FC<{ text: string; delay: number }> = ({ text, delay }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [delay, delay + 16], [0, 1], {
    extrapolateRight: "clamp",
  });
  const x = interpolate(frame, [delay, delay + 16], [-16, 0], {
    extrapolateRight: "clamp",
  });
  return (
    <div
      className="ss-glass-soft ss-fluid rounded-[16px] px-[18px] py-4 font-sans text-[18px] text-ss-text"
      style={{
        opacity,
        transform: `translateX(${x}px)`,
      }}
    >
      {text}
    </div>
  );
};

const UserCard: React.FC = () => (
  <div
    className="ss-glass-soft ss-fluid flex items-center gap-[14px] rounded-[18px] p-[18px]"
  >
    <div
      className="ss-blue-gradient flex h-[44px] w-[44px] items-center justify-center rounded-[14px] font-sans font-black text-ss-blue-deep"
    >
      WS
    </div>
    <div className="flex flex-col gap-0.5">
      <div
        className="font-sans text-[18px] font-bold text-ss-text"
      >
        wesley@company.com
      </div>
      <div
        className="font-mono text-sm text-ss-muted"
      >
        Active · free local mode
      </div>
    </div>
  </div>
);

const SectionLabel: React.FC<{ text: string }> = ({ text }) => (
  <div
    className="font-mono text-[13px] tracking-[0.16em] text-ss-blue-soft"
  >
    {text}
  </div>
);

const ModePill: React.FC<{ text: string; active?: boolean }> = ({
  text,
  active = false,
}) => (
  <div
    className={`ss-fluid flex h-[52px] items-center rounded-[16px] px-4 font-sans text-[17px] ${
      active
        ? "border border-ss-blue/24 bg-ss-blue/12 text-ss-text"
        : "border border-white/8 bg-white/3 text-ss-muted"
    }`}
  >
    {text}
  </div>
);

const ConnectScene: React.FC<{
  eyebrow: string;
  title: string;
  body: string;
  steps: readonly string[];
}> = ({ eyebrow, title, body, steps }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = sceneOpacity(frame, durationInFrames);

  return (
    <AbsoluteFill style={{ opacity }}>
      <Background variant="deep" />
      <Particles count={22} color="rgba(140,208,255,0.48)" speed={0.22} />
      <AbsoluteFill style={{ padding: 60, display: "flex", alignItems: "center" }}>
        <AppShell section="Chat" title="Sprint intake and provider connection">
          <div style={{ display: "grid", gridTemplateColumns: "0.95fr 1.05fr", gap: 24, flex: 1 }}>
            <Card
              className="ss-glass ss-fluid rounded-[28px]"
              padding={28}
              glow="rgba(88,166,255,0.14)"
              style={{ display: "flex", flexDirection: "column", gap: 24 }}
            >
              <SectionIntro eyebrow={eyebrow} title={title} body={body} width={640} />
              <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
                <ProviderBadge name="Azure DevOps" active />
                <ProviderBadge name="Jira" />
                <ProviderBadge name="GitHub" />
              </div>
              <div
                style={{
                  borderRadius: 20,
                  border: "1px solid rgba(88,166,255,0.14)",
                  background: "rgba(255,255,255,0.03)",
                  padding: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 14,
                }}
              >
                <ConnectionRow label="Sprint URL" value="https://dev.azure.com/acme/nebula/orion/_sprints/taskboard/Sprint 24" />
                <ConnectionRow label="PAT" value="••••••••••••••••" />
                <ConnectionRow label="Scope" value="mine · wesley@company.com" />
                <ConnectionRow label="Portfolio" value="acme" />
                <ConnectionRow label="Project / Team" value="nebula / orion" />
              </div>
            </Card>
            <Card
              className="ss-glass-soft ss-fluid rounded-[28px]"
              padding={28}
              glow="rgba(88,166,255,0.14)"
              style={{ display: "flex", flexDirection: "column", gap: 16 }}
            >
              <SectionLabel text="FALLBACK CHAIN" />
              {steps.map((step, index) => (
                <FallbackStep key={step} text={step} index={index} />
              ))}
            </Card>
          </div>
        </AppShell>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const ProviderBadge: React.FC<{ name: string; active?: boolean }> = ({
  name,
  active = false,
}) => (
  <div
    className={`ss-fluid rounded-[16px] px-4 py-3 font-sans text-[18px] ${
      active
        ? "border border-ss-blue/24 bg-ss-blue/12 font-bold text-ss-text"
        : "border border-white/8 bg-white/3 font-medium text-ss-muted"
    }`}
  >
    {name}
  </div>
);

const ConnectionRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div style={{ display: "grid", gridTemplateColumns: "150px 1fr", gap: 16, alignItems: "center" }}>
    <div
      style={{
        color: theme.textMuted,
        fontFamily: theme.fontMono,
        fontSize: 14,
      }}
    >
      {label}
    </div>
    <div
      style={{
        color: theme.text,
        fontFamily: theme.fontMono,
        fontSize: 16,
        lineHeight: 1.45,
      }}
    >
      {value}
    </div>
  </div>
);

const FallbackStep: React.FC<{ text: string; index: number }> = ({ text, index }) => {
  const frame = useCurrentFrame();
  const delay = 8 + index * 18;
  const active = frame > delay + 12;
  const opacity = interpolate(frame, [delay, delay + 16], [0, 1], {
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        opacity,
        display: "grid",
        gridTemplateColumns: "44px 1fr",
        gap: 14,
        alignItems: "center",
        padding: "14px 16px",
        borderRadius: 16,
        border: active ? "1px solid rgba(88,166,255,0.2)" : "1px solid rgba(255,255,255,0.06)",
        background: active ? "rgba(88,166,255,0.08)" : "rgba(255,255,255,0.02)",
      }}
    >
      <div
        style={{
          width: 44,
          height: 44,
          borderRadius: 14,
          background: active ? "linear-gradient(135deg, #58a6ff, #8cd0ff)" : "rgba(255,255,255,0.07)",
          color: active ? promoBlueDeep : theme.textMuted,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: theme.fontMono,
          fontWeight: 800,
          fontSize: 16,
        }}
      >
        {index + 1}
      </div>
      <div
        style={{
          color: theme.text,
          fontFamily: theme.fontSans,
          fontSize: 18,
          lineHeight: 1.45,
        }}
      >
        {text}
      </div>
    </div>
  );
};

const BacklogScene: React.FC<{
  eyebrow: string;
  title: string;
  body: string;
  columns: readonly string[];
}> = ({ eyebrow, title, body, columns }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = sceneOpacity(frame, durationInFrames);

  return (
    <AbsoluteFill style={{ opacity }}>
      <Background variant="soft" />
      <Particles count={16} color="rgba(88,166,255,0.42)" speed={0.18} />
      <AbsoluteFill style={{ padding: 60, display: "flex", alignItems: "center" }}>
        <AppShell section="Backlog" title="Imported sprint board">
          <div style={{ display: "grid", gridTemplateColumns: "0.9fr 1.1fr", gap: 24, flex: 1 }}>
            <Card
              className="ss-glass ss-fluid rounded-[28px]"
              padding={28}
              glow="rgba(88,166,255,0.12)"
              style={{ display: "flex", flexDirection: "column", gap: 22 }}
            >
              <SectionIntro eyebrow={eyebrow} title={title} body={body} width={620} />
              <CardDetailPanel />
            </Card>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(6, minmax(0, 1fr))", gap: 12 }}>
              {columns.map((column, index) => (
                <BoardColumn key={column} title={column} index={index} frame={frame} />
              ))}
            </div>
          </div>
        </AppShell>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const BoardColumn: React.FC<{ title: string; index: number; frame: number }> = ({
  title,
  index,
  frame,
}) => {
  const cards = [
    { label: "SS-2418", base: 0, path: [0, 1, 2, 3, 4] },
    { label: "SS-2421", base: 1, path: [0, 1, 2] },
    { label: "SS-2424", base: 2, path: [0, 1, 2, 3] },
  ];

  return (
    <div
      style={{
        borderRadius: 18,
        border: "1px solid rgba(88,166,255,0.12)",
        background: "rgba(8,14,30,0.84)",
        padding: 12,
        display: "flex",
        flexDirection: "column",
        gap: 10,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "4px 4px 10px",
          borderBottom: "1px solid rgba(88,166,255,0.12)",
        }}
      >
        <div
          style={{
            color: theme.text,
            fontFamily: theme.fontSans,
            fontSize: 16,
            fontWeight: 700,
          }}
        >
          {title}
        </div>
        <div
          style={{
            width: 24,
            height: 24,
            borderRadius: 8,
            background: "rgba(88,166,255,0.12)",
            color: promoBlueSoft,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: theme.fontMono,
            fontSize: 12,
          }}
        >
          »
        </div>
      </div>
      {cards.map((card) => (
        <TaskCard
          key={card.label}
          label={card.label}
          visible={card.path.includes(index)}
          active={currentCardColumn(frame, card.path) === index}
          blocked={title === "Planning" && card.label === "SS-2421"}
          summary={
            card.label === "SS-2418"
              ? "Importação Azure"
              : card.label === "SS-2421"
                ? "Configurar repo"
                : "Pipeline de testes"
          }
        />
      ))}
    </div>
  );
};

const currentCardColumn = (frame: number, path: number[]) => {
  const checkpoints = [0, 30, 60, 90, 120];
  let stage = 0;
  checkpoints.forEach((checkpoint, index) => {
    if (frame >= checkpoint) {
      stage = Math.min(index, path.length - 1);
    }
  });
  return path[stage];
};

const TaskCard: React.FC<{
  label: string;
  summary: string;
  visible: boolean;
  active?: boolean;
  blocked?: boolean;
}> = ({ label, summary, visible, active = false, blocked = false }) => (
  <div
    className={`ss-fluid flex min-h-[92px] flex-col gap-2 rounded-[14px] p-3 ${
      active
        ? "border border-ss-blue/26 bg-ss-blue/8 shadow-[0_0_26px_rgba(88,166,255,0.16)]"
        : "border border-white/8 bg-white/3"
    }`}
    style={{
      opacity: visible ? 1 : 0,
      transform: `scale(${active ? 1 : 0.98})`,
      display: visible ? "flex" : "none",
    }}
  >
    <div className="flex justify-between gap-2">
      <div
        className="font-mono text-sm font-bold text-ss-text"
      >
        {label}
      </div>
      <div
        className="rounded-full px-2 py-[3px] font-mono text-[11px]"
        style={{
          background: blocked ? "rgba(248,113,113,0.12)" : "rgba(52,211,153,0.12)",
          color: blocked ? theme.danger : theme.success,
        }}
      >
        {blocked ? "repo missing" : "ready"}
      </div>
    </div>
    <div
      className="font-sans text-[15px] leading-[1.35] text-ss-text"
    >
      {summary}
    </div>
    <div
      className="font-mono text-[12px] text-ss-muted"
    >
      arraste para mover · logs no card
    </div>
  </div>
);

const CardDetailPanel: React.FC = () => (
  <div
    className="ss-panel-border ss-fluid flex flex-col gap-4 rounded-[20px] p-[22px]"
  >
    <div className="flex justify-between gap-3">
      <div>
        <div
          className="font-sans text-[24px] font-bold text-ss-text"
        >
          SS-2418 · Importação da sprint Azure
        </div>
        <div
          className="mt-1.5 font-sans text-[16px] text-ss-muted"
        >
          Description, comments, links, attachments and source URL pulled into the card.
        </div>
      </div>
      <HeaderPill label="assigned to you" tone="blue" />
    </div>
    <DetailRow label="Source" value="Azure DevOps / Sprint 24 / Taskboard" />
    <DetailRow label="Repository" value="C:\\repos\\acme\\nebula-web" />
    <DetailRow label="Target branch" value="develop" />
    <DetailRow label="Latest move" value="Backlog → Planning by wesley@company.com" />
    <DetailRow label="History" value="created · imported · assigned · moved · tested" />
  </div>
);

const DetailRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <div className="grid grid-cols-[120px_1fr] gap-4">
    <div
      className="font-mono text-[13px] text-ss-muted"
    >
      {label}
    </div>
    <div
      className="font-mono text-[14px] leading-[1.45] text-ss-text"
    >
      {value}
    </div>
  </div>
);

const ExecutionScene: React.FC<{
  eyebrow: string;
  title: string;
  body: string;
  lines: readonly { prompt?: string; text: string }[];
}> = ({ eyebrow, title, body, lines }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = sceneOpacity(frame, durationInFrames);
  const terminalLines: TerminalLine[] = lines.map((line, index) => ({
    ...line,
    delay: index * 18,
    speed: index === lines.length - 1 ? 1.7 : 1.5,
    color: index === lines.length - 1 ? theme.success : index === 0 ? theme.text : promoBlueSoft,
  }));

  return (
    <AbsoluteFill style={{ opacity }}>
      <Background variant="deep" />
      <Particles count={20} color="rgba(88,166,255,0.42)" speed={0.22} />
      <AbsoluteFill style={{ padding: 60, display: "flex", alignItems: "center" }}>
        <AppShell section="Runs" title="Task execution and live logs">
          <div style={{ display: "grid", gridTemplateColumns: "0.9fr 1.1fr", gap: 24, flex: 1 }}>
            <Card
              className="ss-glass ss-fluid rounded-[28px]"
              padding={28}
              glow="rgba(88,166,255,0.12)"
              style={{ display: "flex", flexDirection: "column", gap: 24 }}
            >
              <SectionIntro eyebrow={eyebrow} title={title} body={body} width={620} />
              <PipelineRail frame={frame} />
            </Card>
            <div style={{ display: "grid", gridTemplateRows: "1fr auto", gap: 18 }}>
              <div style={{ display: "flex", justifyContent: "center", alignItems: "center" }}>
                <Terminal
                  className="ss-glass ss-fluid rounded-[24px]"
                  title="~/sendsprint — run SS-2418"
                  lines={terminalLines}
                  width={980}
                  height={430}
                  startDelay={12}
                />
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(0, 1fr))", gap: 12 }}>
                <ExecutionBadge title="Tokens" value="182k" />
                <ExecutionBadge title="Model" value="Codex" />
                <ExecutionBadge title="Evidence" value="7 files" />
                <ExecutionBadge title="Status" value="Review" />
              </div>
            </div>
          </div>
        </AppShell>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const PipelineRail: React.FC<{ frame: number }> = ({ frame }) => {
  const items = [
    "Architecture mapped",
    "Planning generated",
    "Coding in worktree",
    "Tests and evidence",
    "Human review pending",
  ];
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {items.map((item, index) => {
        const active = frame > index * 16 + 18;
        return (
          <div
            key={item}
            style={{
              display: "grid",
              gridTemplateColumns: "44px 1fr",
              gap: 14,
              alignItems: "center",
              padding: "14px 16px",
              borderRadius: 16,
              background: active ? "rgba(88,166,255,0.08)" : "rgba(255,255,255,0.03)",
              border: active ? "1px solid rgba(88,166,255,0.18)" : "1px solid rgba(255,255,255,0.08)",
            }}
          >
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 14,
                background: active ? "linear-gradient(135deg, #58a6ff, #8cd0ff)" : "rgba(255,255,255,0.07)",
                color: active ? promoBlueDeep : theme.textMuted,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: theme.fontMono,
                fontWeight: 800,
                fontSize: 16,
              }}
            >
              {active ? "✓" : index + 1}
            </div>
            <div
              style={{
                color: theme.text,
                fontFamily: theme.fontSans,
                fontSize: 18,
                fontWeight: active ? 700 : 500,
              }}
            >
              {item}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const ExecutionBadge: React.FC<{ title: string; value: string }> = ({ title, value }) => (
  <div
    className="ss-panel-border ss-fluid flex flex-col gap-1.5 rounded-[18px] p-4"
  >
    <div
      className="font-mono text-[12px] text-ss-muted"
    >
      {title}
    </div>
    <div
      className="font-sans text-[20px] font-bold text-ss-text"
    >
      {value}
    </div>
  </div>
);

const ManagerScene: React.FC<{
  eyebrow: string;
  title: string;
  body: string;
  metrics: readonly { label: string; value: string; delta: string }[];
}> = ({ eyebrow, title, body, metrics }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = sceneOpacity(frame, durationInFrames);

  return (
    <AbsoluteFill style={{ opacity }}>
      <Background variant="soft" />
      <Particles count={18} color="rgba(88,166,255,0.4)" speed={0.16} />
      <AbsoluteFill style={{ padding: 60, display: "flex", alignItems: "center" }}>
        <AppShell section="Manager" title="Operational visibility for the whole company">
          <div style={{ display: "grid", gridTemplateColumns: "0.92fr 1.08fr", gap: 24, flex: 1 }}>
            <Card
              className="ss-glass ss-fluid rounded-[28px]"
              padding={28}
              glow="rgba(88,166,255,0.12)"
              style={{ display: "flex", flexDirection: "column", gap: 22 }}
            >
              <SectionIntro eyebrow={eyebrow} title={title} body={body} width={620} />
              <div style={{ display: "grid", gridTemplateColumns: "repeat(2, minmax(0, 1fr))", gap: 12 }}>
                {metrics.map((metric, index) => (
                  <MetricTile key={metric.label} {...metric} delay={index * 8} />
                ))}
              </div>
            </Card>
            <Card
              className="ss-glass-soft ss-fluid rounded-[28px]"
              padding={24}
              glow="rgba(88,166,255,0.12)"
              style={{ display: "grid", gridTemplateRows: "auto auto 1fr", gap: 16 }}
            >
              <SectionLabel text="TEAM ACTIVITY" />
              <TeamActivityRow name="Ana Costa" task="SS-2418 · review humana" model="Codex" status="review" />
              <TeamActivityRow name="Pedro Lima" task="SS-2424 · pipeline de testes" model="Claude" status="testing" />
              <TeamActivityRow name="Júlia Nunes" task="SS-2429 · backlog import" model="Playwright" status="intake" />
              <TeamActivityRow name="Renato Alves" task="SS-2433 · deploy branch dev" model="Hermes" status="deploy" />
            </Card>
          </div>
        </AppShell>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const MetricTile: React.FC<{
  label: string;
  value: string;
  delta: string;
  delay: number;
}> = ({ label, value, delta, delay }) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [delay, delay + 16], [0, 1], {
    extrapolateRight: "clamp",
  });
  return (
    <div
      className="ss-panel-border ss-fluid flex flex-col gap-2 rounded-[18px] p-[18px]"
      style={{
        opacity,
      }}
    >
      <div
        className="font-mono text-[12px] text-ss-muted"
      >
        {label}
      </div>
      <div
        className="font-sans text-[34px] font-extrabold text-ss-text"
      >
        {value}
      </div>
      <div
        className="font-mono text-[13px] text-ss-blue-soft"
      >
        {delta}
      </div>
    </div>
  );
};

const TeamActivityRow: React.FC<{
  name: string;
  task: string;
  model: string;
  status: string;
}> = ({ name, task, model, status }) => (
  <div
    className="ss-glass-soft ss-fluid grid grid-cols-[1fr_120px_90px] items-center gap-4 rounded-[16px] px-[18px] py-4"
  >
    <div className="flex flex-col gap-1">
      <div
        className="font-sans text-[18px] font-bold text-ss-text"
      >
        {name}
      </div>
      <div
        className="font-sans text-[15px] leading-[1.45] text-ss-muted"
      >
        {task}
      </div>
    </div>
    <div
      className="font-mono text-[14px] text-ss-blue-soft"
    >
      {model}
    </div>
    <div
      className="justify-self-start rounded-full bg-emerald-400/12 px-3 py-2 font-mono text-[12px] text-emerald-300"
    >
      {status}
    </div>
  </div>
);

const OutroScene: React.FC<{
  title: string;
  body: string;
  cta: string;
}> = ({ title, body, cta }) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const opacity = sceneOpacity(frame, durationInFrames);
  const scale = interpolate(frame, [0, 36], [0.94, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ opacity }}>
      <Background variant="deep" />
      <AbsoluteFill
        style={{
          background:
            "radial-gradient(circle at 50% 32%, rgba(88,166,255,0.22), transparent 28%), radial-gradient(circle at 68% 60%, rgba(140,208,255,0.14), transparent 24%)",
        }}
      />
      <Particles count={26} color="rgba(88,166,255,0.48)" speed={0.2} />
      <AbsoluteFill
        style={{
          padding: 88,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          transform: `scale(${scale})`,
        }}
      >
        <Card
          className="ss-glass ss-fluid rounded-[36px]"
          width={1200}
          padding={40}
          glow="rgba(88,166,255,0.2)"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 20,
            textAlign: "center",
            background:
              "linear-gradient(180deg, rgba(10,18,36,0.92), rgba(7,12,26,0.94))",
          }}
        >
          <Logo size={110} />
          <div
            style={{
              color: theme.text,
              fontFamily: theme.fontSans,
              fontSize: 72,
              fontWeight: 900,
              lineHeight: 1.02,
              maxWidth: 980,
            }}
          >
            {title}
          </div>
          <div
            style={{
              color: theme.textMuted,
              fontFamily: theme.fontSans,
              fontSize: 24,
              lineHeight: 1.5,
              maxWidth: 860,
            }}
          >
            {body}
          </div>
          <div
            style={{
              marginTop: 8,
              padding: "16px 24px",
              borderRadius: 16,
              background: "linear-gradient(135deg, #58a6ff, #8cd0ff)",
              color: promoBlueDeep,
              fontFamily: theme.fontSans,
              fontSize: 22,
              fontWeight: 900,
            }}
          >
            {cta}
          </div>
        </Card>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
