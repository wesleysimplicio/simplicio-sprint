import React from "react";
import {
  AbsoluteFill,
  Img,
  Sequence,
  interpolate,
  staticFile,
  useCurrentFrame,
} from "remotion";
import { LangContext, type Lang } from "./i18n";
import { FPS, theme } from "./theme";

export const BEFORE_AFTER_DURATION = 1410;

type Copy = {
  title: string;
  subtitle: string;
  painTitle: string;
  pain: string[];
  empathyTitle: string;
  empathy: string;
  solutionTitle: string;
  solution: string[];
  metricsTitle: string;
  metrics: string[];
  closeTitle: string;
  closeText: string;
};

const COPY: Record<Lang, Copy> = {
  en: {
    title: "Before and after SendSprint",
    subtitle:
      "The same sprint, the same team. Less manual coordination. More delivered PRs.",
    painTitle: "Before: sprint delivery is scattered",
    pain: [
      "Stories wait in Jira or Azure DevOps.",
      "Developers manually discover context, branches, tests, evidence, and PRs.",
      "Managers ask for status because the flow is invisible.",
    ],
    empathyTitle: "The problem is not the team",
    empathy:
      "Good engineers lose hours to handoffs, duplicated checks, broken context, and repeated status work.",
    solutionTitle: "After: SendSprint turns work into a delivery lane",
    solution: [
      "Preflight validates sprint, repos, credentials, and hierarchy risks.",
      "Dry-run shows branches, target PRs, confidence, and routing before changes.",
      "Resume state prevents duplicate delivery when a run is interrupted.",
      "Tests, evidence, security, commit, PR, and review move through one loop.",
    ],
    metricsTitle: "What changes inside the company",
    metrics: [
      "Less coordination debt",
      "Fewer backlog and branch mistakes",
      "PRs with evidence by default",
      "A repeatable path from sprint to develop",
    ],
    closeTitle: "SendSprint is not another dashboard",
    closeText:
      "It is an execution layer for sprint delivery: read, plan, validate, implement, test, and open the PR.",
  },
  pt: {
    title: "Antes e depois do SendSprint",
    subtitle:
      "A mesma sprint, o mesmo time. Menos coordenacao manual. Mais PRs entregues.",
    painTitle: "Antes: a entrega da sprint fica espalhada",
    pain: [
      "Stories ficam paradas no Jira ou Azure DevOps.",
      "Devs descobrem contexto, branch, testes, evidencias e PR manualmente.",
      "Gestores perguntam status porque o fluxo nao esta visivel.",
    ],
    empathyTitle: "O problema nao e o time",
    empathy:
      "Bons engenheiros perdem horas com handoffs, checks duplicados, contexto quebrado e status repetido.",
    solutionTitle: "Depois: SendSprint transforma trabalho em esteira",
    solution: [
      "Preflight valida sprint, repos, credenciais e riscos de hierarquia.",
      "Dry-run mostra branches, PRs, confianca e roteamento antes de alterar.",
      "Estado resumivel evita duplicidade quando a execucao para no meio.",
      "Testes, evidencias, seguranca, commit, PR e review entram em um loop.",
    ],
    metricsTitle: "O que muda na empresa",
    metrics: [
      "Menos divida de coordenacao",
      "Menos erro de backlog e branch",
      "PRs com evidencia por padrao",
      "Um caminho repetivel da sprint para develop",
    ],
    closeTitle: "SendSprint nao e mais um dashboard",
    closeText:
      "E uma camada de execucao para entregar sprint: ler, planejar, validar, implementar, testar e abrir PR.",
  },
};

type Props = {
  lang?: Lang;
};

export const SendSprintBeforeAfter: React.FC<Props> = ({ lang = "pt" }) => {
  return (
    <LangContext.Provider value={lang}>
      <AbsoluteFill style={{ background: "#020617", color: theme.text, fontFamily: theme.fontSans }}>
        <Glow />
        <Sequence from={0} durationInFrames={180}>
          <Hero copy={COPY[lang]} />
        </Sequence>
        <Sequence from={180} durationInFrames={240}>
          <PainScene copy={COPY[lang]} />
        </Sequence>
        <Sequence from={420} durationInFrames={210}>
          <EmpathyScene copy={COPY[lang]} />
        </Sequence>
        <Sequence from={630} durationInFrames={360}>
          <SolutionScene copy={COPY[lang]} />
        </Sequence>
        <Sequence from={990} durationInFrames={240}>
          <MetricsScene copy={COPY[lang]} />
        </Sequence>
        <Sequence from={1230} durationInFrames={180}>
          <CloseScene copy={COPY[lang]} />
        </Sequence>
      </AbsoluteFill>
    </LangContext.Provider>
  );
};

const useIn = (start = 0, end = 24) => {
  const frame = useCurrentFrame();
  return interpolate(frame, [start, end], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
};

const Glow: React.FC = () => (
  <AbsoluteFill
    style={{
      background:
        "radial-gradient(circle at 15% 20%, rgba(248,113,113,.22), transparent 26%), radial-gradient(circle at 83% 15%, rgba(34,211,238,.28), transparent 30%), radial-gradient(circle at 50% 95%, rgba(52,211,153,.22), transparent 30%)",
    }}
  />
);

const Hero: React.FC<{ copy: Copy }> = ({ copy }) => {
  const frame = useCurrentFrame();
  const enter = useIn();
  const imageScale = interpolate(frame, [0, 180], [1.08, 1.0], { extrapolateRight: "clamp" });
  return (
    <AbsoluteFill>
      <Img
        src={staticFile("sendsprint-productivity-before-after.png")}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          transform: `scale(${imageScale})`,
          opacity: 0.42,
          filter: "saturate(1.08) contrast(1.08)",
        }}
      />
      <Overlay />
      <div style={{ ...centerColumn, opacity: enter, transform: `translateY(${(1 - enter) * 28}px)` }}>
        <Kicker>PRODUCTIVITY MULTIPLIER</Kicker>
        <h1 style={heroTitle}>{copy.title}</h1>
        <p style={heroSubtitle}>{copy.subtitle}</p>
      </div>
    </AbsoluteFill>
  );
};

const PainScene: React.FC<{ copy: Copy }> = ({ copy }) => {
  const enter = useIn();
  return (
    <AbsoluteFill style={{ padding: 92 }}>
      <SplitLabel left="WITHOUT" right="WITH" />
      <div style={twoColumns}>
        <Panel tone="danger" style={{ opacity: enter }}>
          <h2 style={sectionTitle}>{copy.painTitle}</h2>
          <BulletList items={copy.pain} tone="danger" />
        </Panel>
        <MiniVisual image="sendsprint-productivity-before-after.png" crop="right" />
      </div>
    </AbsoluteFill>
  );
};

const EmpathyScene: React.FC<{ copy: Copy }> = ({ copy }) => {
  const enter = useIn();
  return (
    <AbsoluteFill style={{ alignItems: "center", justifyContent: "center", padding: 140 }}>
      <Panel style={{ width: 1320, opacity: enter, transform: `scale(${0.96 + enter * 0.04})` }}>
        <Kicker>EMPATHY</Kicker>
        <h2 style={{ ...sectionTitle, fontSize: 76 }}>{copy.empathyTitle}</h2>
        <p style={{ ...paragraph, fontSize: 38, lineHeight: 1.35 }}>{copy.empathy}</p>
      </Panel>
    </AbsoluteFill>
  );
};

const SolutionScene: React.FC<{ copy: Copy }> = ({ copy }) => {
  const frame = useCurrentFrame();
  const enter = useIn();
  const pulse = interpolate(Math.sin(frame / 12), [-1, 1], [0.88, 1]);
  return (
    <AbsoluteFill style={{ padding: 84 }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1.1fr", gap: 48, height: "100%" }}>
        <Panel tone="success" style={{ opacity: enter }}>
          <h2 style={sectionTitle}>{copy.solutionTitle}</h2>
          <BulletList items={copy.solution} tone="success" />
        </Panel>
        <div style={{ position: "relative", borderRadius: 44, overflow: "hidden", border: `1px solid ${theme.border}` }}>
          <Img
            src={staticFile("sendsprint-productivity-engine.png")}
            style={{ width: "100%", height: "100%", objectFit: "cover", opacity: 0.8 }}
          />
          <div style={{ ...engineBadge, transform: `scale(${pulse})` }}>SPRINT - BRANCH - TEST - PR</div>
        </div>
      </div>
    </AbsoluteFill>
  );
};

const MetricsScene: React.FC<{ copy: Copy }> = ({ copy }) => {
  const enter = useIn();
  return (
    <AbsoluteFill style={{ padding: 96 }}>
      <Kicker>OUTCOME</Kicker>
      <h2 style={sectionTitle}>{copy.metricsTitle}</h2>
      <div style={metricGrid}>
        {copy.metrics.map((metric, index) => (
          <div
            key={metric}
            style={{
              ...metricCard,
              opacity: interpolate(enter, [0, 1], [0, 1]),
              transform: `translateY(${(1 - enter) * (32 + index * 8)}px)`,
            }}
          >
            <span style={metricNumber}>{String(index + 1).padStart(2, "0")}</span>
            <span>{metric}</span>
          </div>
        ))}
      </div>
    </AbsoluteFill>
  );
};

const CloseScene: React.FC<{ copy: Copy }> = ({ copy }) => {
  const enter = useIn();
  return (
    <AbsoluteFill style={{ justifyContent: "center", padding: 120 }}>
      <div style={{ width: 1120, opacity: enter }}>
        <Kicker>SOLUTION</Kicker>
        <h2 style={{ ...sectionTitle, fontSize: 76 }}>{copy.closeTitle}</h2>
        <p style={{ ...paragraph, width: 980 }}>{copy.closeText}</p>
      </div>
      <div style={cta}>sendsprint sprint --dry-run -&gt; run -&gt; PR</div>
    </AbsoluteFill>
  );
};

const Overlay: React.FC = () => (
  <AbsoluteFill
    style={{
      background:
        "linear-gradient(90deg, rgba(2,6,23,.92), rgba(2,6,23,.62) 46%, rgba(2,6,23,.78))",
    }}
  />
);

const SplitLabel: React.FC<{ left: string; right: string }> = ({ left, right }) => (
  <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 24 }}>
    <Kicker>{left} SENDSPRINT</Kicker>
    <Kicker>{right} SENDSPRINT</Kicker>
  </div>
);

const BulletList: React.FC<{ items: string[]; tone?: "success" | "danger" }> = ({ items, tone }) => (
  <div style={{ display: "grid", gap: 22, marginTop: 34 }}>
    {items.map((item) => (
      <div key={item} style={bulletRow}>
        <span style={{ ...dot, background: tone === "danger" ? theme.danger : theme.success }} />
        <span>{item}</span>
      </div>
    ))}
  </div>
);

const Panel: React.FC<React.PropsWithChildren<{ tone?: "success" | "danger"; style?: React.CSSProperties }>> = ({
  children,
  tone,
  style,
}) => (
  <div
    style={{
      padding: 52,
      borderRadius: 38,
      border: `1px solid ${tone === "danger" ? "rgba(248,113,113,.34)" : tone === "success" ? "rgba(52,211,153,.34)" : theme.border}`,
      background:
        tone === "danger"
          ? "linear-gradient(145deg, rgba(127,29,29,.42), rgba(15,23,42,.76))"
          : tone === "success"
            ? "linear-gradient(145deg, rgba(6,78,59,.44), rgba(15,23,42,.76))"
            : "linear-gradient(145deg, rgba(15,23,42,.88), rgba(30,41,59,.72))",
      boxShadow: "0 34px 100px rgba(0,0,0,.35)",
      ...style,
    }}
  >
    {children}
  </div>
);

const MiniVisual: React.FC<{ image: string; crop: "left" | "right" }> = ({ image, crop }) => (
  <div style={{ borderRadius: 38, overflow: "hidden", border: `1px solid ${theme.border}`, minHeight: 720 }}>
    <Img
      src={staticFile(image)}
      style={{
        width: "100%",
        height: "100%",
        objectFit: "cover",
        objectPosition: crop === "left" ? "left center" : "right center",
        filter: crop === "left" ? "grayscale(.15) contrast(1.15)" : "saturate(1.15)",
      }}
    />
  </div>
);

const centerColumn: React.CSSProperties = {
  position: "absolute",
  left: 112,
  top: 210,
  width: 1050,
};

const twoColumns: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 42,
  height: 780,
};

const heroTitle: React.CSSProperties = {
  margin: "20px 0 0",
  fontSize: 108,
  lineHeight: 0.94,
  letterSpacing: "-5px",
  fontWeight: 900,
};

const heroSubtitle: React.CSSProperties = {
  marginTop: 34,
  width: 880,
  color: theme.textMuted,
  fontSize: 34,
  lineHeight: 1.35,
};

const sectionTitle: React.CSSProperties = {
  margin: 0,
  fontSize: 58,
  lineHeight: 1,
  letterSpacing: "-2px",
};

const paragraph: React.CSSProperties = {
  marginTop: 28,
  color: theme.textMuted,
  fontSize: 32,
  lineHeight: 1.35,
};

const bulletRow: React.CSSProperties = {
  display: "grid",
  gridTemplateColumns: "22px 1fr",
  gap: 18,
  alignItems: "start",
  color: "#e5e7eb",
  fontSize: 30,
  lineHeight: 1.25,
};

const dot: React.CSSProperties = {
  width: 14,
  height: 14,
  borderRadius: 99,
  marginTop: 12,
  boxShadow: "0 0 26px currentColor",
};

const metricGrid: React.CSSProperties = {
  marginTop: 48,
  display: "grid",
  gridTemplateColumns: "1fr 1fr",
  gap: 30,
};

const metricCard: React.CSSProperties = {
  minHeight: 180,
  padding: 38,
  borderRadius: 34,
  background: "rgba(15,23,42,.78)",
  border: `1px solid ${theme.border}`,
  display: "grid",
  gap: 18,
  fontSize: 34,
  fontWeight: 750,
};

const metricNumber: React.CSSProperties = {
  color: theme.accent,
  fontSize: 22,
  letterSpacing: "4px",
};

const engineBadge: React.CSSProperties = {
  position: "absolute",
  left: 42,
  bottom: 42,
  padding: "20px 28px",
  borderRadius: 999,
  background: "rgba(2,6,23,.82)",
  border: "1px solid rgba(34,211,238,.42)",
  color: "#dffbff",
  fontFamily: theme.fontMono,
  fontSize: 24,
  letterSpacing: "2px",
};

const cta: React.CSSProperties = {
  position: "absolute",
  right: 120,
  bottom: 100,
  padding: "24px 32px",
  borderRadius: 26,
  background: "linear-gradient(135deg, rgba(34,211,238,.22), rgba(52,211,153,.18))",
  border: "1px solid rgba(34,211,238,.35)",
  fontFamily: theme.fontMono,
  fontSize: 26,
};

const Kicker: React.FC<React.PropsWithChildren> = ({ children }) => (
  <div
    style={{
      color: theme.accent,
      fontFamily: theme.fontMono,
      fontSize: 22,
      letterSpacing: "5px",
      fontWeight: 700,
    }}
  >
    {children}
  </div>
);

