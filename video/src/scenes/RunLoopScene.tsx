import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Background } from "../components/Background";
import { Particles } from "../components/Particles";
import { AnimatedText } from "../components/AnimatedText";
import { theme } from "../theme";
import { useStrings } from "../i18n";

/**
 * Standalone explainer of the run loop: round 1 fails (regression detected),
 * fix-loop kicks in, round 2 passes, PR opens. Strings come from `useStrings`
 * so the same composition renders in pt or en.
 */

const STEP_NUMS = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];

// Frame timeline (30fps, total ~660 frames = 22s)
const T = {
  intro: { from: 0, to: 70 },
  round1: { from: 70, to: 320 },
  fixLoop: { from: 320, to: 410 },
  round2: { from: 410, to: 600 },
  outro: { from: 600, to: 660 },
};

type StepStatus = "pending" | "running" | "ok" | "failed";

function statusAt(frame: number, num: number, round: 1 | 2): StepStatus {
  if (round === 1) {
    const start = T.round1.from;
    const per = (T.round1.to - start) / 6;
    const local = (frame - start) / per;
    if (local < 0) return "pending";
    if (num < Math.floor(local)) return num === 5 ? "failed" : "ok";
    if (num === Math.floor(local) + 1) return "running";
    return "pending";
  }
  const start = T.round2.from;
  const per = (T.round2.to - start) / 7;
  const local = (frame - start) / per;
  if (local < 0) {
    if (num < 3) return "ok";
    return "pending";
  }
  const seq = [3, 4, 5, 6, 8, 9, 10];
  const cur = seq[Math.min(seq.length - 1, Math.floor(local))];
  const idx = seq.indexOf(num);
  if (idx === -1) {
    if (num < 3) return "ok";
    if (num === 7) return "ok";
    return "pending";
  }
  if (num < cur) return "ok";
  if (num === cur) return "running";
  return "pending";
}

export const RunLoopScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const inIntro = frame < T.round1.from;
  const inFix = frame >= T.fixLoop.from && frame < T.fixLoop.to;
  const round: 1 | 2 = frame < T.fixLoop.to ? 1 : 2;
  const inOutro = frame >= T.outro.from;

  return (
    <AbsoluteFill style={{ background: theme.bgDeep }}>
      <Background variant={inOutro ? "soft" : "deep"} />
      <Particles count={26} speed={0.18} />

      <AbsoluteFill style={{ padding: 60, gap: 24 }}>
        <Header round={round} inFix={inFix} inOutro={inOutro} />

        {inIntro ? (
          <Hero />
        ) : (
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1.05fr 1fr",
              gap: 40,
              flex: 1,
            }}
          >
            <StepsList frame={frame} round={round} inFix={inFix} />
            <RightPanel
              frame={frame}
              round={round}
              inFix={inFix}
              inOutro={inOutro}
              fps={fps}
            />
          </div>
        )}
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Header: React.FC<{ round: 1 | 2; inFix: boolean; inOutro: boolean }> = ({
  round,
  inFix,
  inOutro,
}) => {
  const s = useStrings();
  const tag = inOutro
    ? s.rl_delivered_label
    : inFix
      ? s.rl_fixloop_label
      : s.rl_round_label(round, 3);
  const color = inOutro
    ? theme.success
    : inFix
      ? theme.warning
      : round === 1
        ? theme.danger
        : theme.success;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 24 }}>
      <div
        style={{
          padding: "10px 18px",
          borderRadius: 999,
          background: `${color}33`,
          border: `1px solid ${color}`,
          color,
          fontFamily: theme.fontMono,
          fontSize: 18,
          letterSpacing: 4,
          fontWeight: 700,
        }}
      >
        ↻ {tag}
      </div>
      <div
        style={{
          color: theme.textMuted,
          fontFamily: theme.fontMono,
          letterSpacing: 2,
          fontSize: 16,
        }}
      >
        {s.rl_subtitle}
      </div>
    </div>
  );
};

const Hero: React.FC = () => {
  const s = useStrings();
  return (
    <div
      style={{
        flex: 1,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 18,
        textAlign: "center",
      }}
    >
      <div
        style={{
          color: theme.accent,
          fontFamily: theme.fontMono,
          letterSpacing: 6,
          fontSize: 22,
        }}
      >
        {s.rl_hero_eyebrow}
      </div>
      <AnimatedText
        text={s.rl_hero_title}
        size={120}
        weight={900}
        gradient
        letterStagger={2}
      />
      <div
        style={{
          color: theme.textMuted,
          fontFamily: theme.fontSans,
          fontSize: 28,
          maxWidth: 900,
          marginTop: 8,
        }}
      >
        {s.rl_hero_lede}
      </div>
    </div>
  );
};

const StepsList: React.FC<{ frame: number; round: 1 | 2; inFix: boolean }> = ({
  frame,
  round,
  inFix,
}) => {
  const s = useStrings();
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {STEP_NUMS.map((num) => {
        let st: StepStatus = "pending";
        if (round === 2) {
          const r1 = statusAt(frame, num, 1);
          const r2 = statusAt(frame, num, 2);
          if (r2 !== "pending") st = r2;
          else if (r1 === "ok" || r1 === "failed") st = r1;
          else st = "pending";
          if (num === 5 && r2 === "pending") st = "failed";
        } else {
          st = statusAt(frame, num, 1);
        }

        if (inFix && num === 7) st = "running";
        const colors: Record<StepStatus, string> = {
          pending: theme.textMuted,
          running: round === 1 ? theme.danger : theme.success,
          ok: theme.success,
          failed: theme.danger,
        };
        const col = colors[st];
        const icon =
          st === "ok" ? "✓" : st === "failed" ? "✗" : st === "running" ? "↻" : String(num);

        return (
          <div
            key={num}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 16,
              padding: "12px 18px",
              borderRadius: 14,
              background:
                st === "running" ? `linear-gradient(90deg, ${col}33, transparent)` : "transparent",
              border: st === "running" ? `1px solid ${col}88` : "1px solid transparent",
            }}
          >
            <div
              style={{
                width: 44,
                height: 44,
                borderRadius: 12,
                background: st === "pending" ? "rgba(255,255,255,0.05)" : col,
                color: st === "pending" ? theme.textMuted : "white",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: theme.fontMono,
                fontWeight: 800,
                fontSize: 18,
                boxShadow: st === "running" ? `0 0 24px ${col}88` : "none",
              }}
            >
              {icon}
            </div>
            <div
              style={{
                fontFamily: theme.fontSans,
                fontSize: 24,
                color: st === "pending" ? "rgba(241,244,255,0.55)" : theme.text,
                fontWeight: st === "running" ? 700 : 500,
              }}
            >
              {s.rl_step_names[num]}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const RightPanel: React.FC<{
  frame: number;
  round: 1 | 2;
  inFix: boolean;
  inOutro: boolean;
  fps: number;
}> = ({ frame, round, inFix, inOutro, fps }) => {
  if (inOutro) return <DeliveredCard frame={frame} fps={fps} />;
  if (inFix) return <FixLoopCard frame={frame} fps={fps} />;
  if (round === 1) return <RegressionCard frame={frame} round={1} failed fps={fps} />;
  return <RegressionCard frame={frame} round={2} failed={false} fps={fps} />;
};

const RegressionCard: React.FC<{
  frame: number;
  round: 1 | 2;
  failed: boolean;
  fps: number;
}> = ({ frame, round, failed, fps }) => {
  const s = useStrings();
  const sp = spring({
    frame: frame - (round === 1 ? T.round1.from : T.round2.from),
    fps,
    config: { damping: 18, stiffness: 130 },
  });
  const color = failed ? theme.danger : theme.success;
  const failingTests = [
    "test_dashboard.py::test_kpis_render",
    "test_dashboard.py::test_velocity_chart",
    "test_regression.py::test_signup_email_validation",
  ];
  return (
    <div
      style={{
        padding: 32,
        borderRadius: 20,
        background: "rgba(15,21,48,0.85)",
        border: `1px solid ${color}88`,
        boxShadow: `0 0 80px ${color}22`,
        opacity: sp,
        transform: `translateY(${interpolate(sp, [0, 1], [20, 0])}px)`,
        display: "flex",
        flexDirection: "column",
        gap: 18,
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div
          style={{
            padding: "6px 14px",
            background: color,
            color: "white",
            borderRadius: 999,
            fontFamily: theme.fontMono,
            fontSize: 14,
            fontWeight: 800,
            letterSpacing: 2,
          }}
        >
          ROUND {round}
        </div>
        <div
          style={{
            color,
            fontSize: 28,
            fontWeight: 700,
            fontFamily: theme.fontSans,
          }}
        >
          {failed ? s.rl_regression_failed : s.rl_regression_passed}
        </div>
      </div>
      <div
        style={{
          color: theme.textMuted,
          fontFamily: theme.fontMono,
          fontSize: 16,
        }}
      >
        {failed ? s.rl_regression_help_failed : s.rl_regression_help_passed}
      </div>
      {failed ? (
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {failingTests.map((t, i) => (
            <div
              key={t}
              style={{
                opacity: interpolate(
                  frame,
                  [T.round1.from + 30 + i * 14, T.round1.from + 60 + i * 14],
                  [0, 1],
                  { extrapolateRight: "clamp" },
                ),
                fontFamily: theme.fontMono,
                fontSize: 18,
                color: theme.danger,
                background: "rgba(248,113,113,0.1)",
                padding: "10px 14px",
                borderRadius: 10,
                border: `1px solid ${theme.danger}44`,
              }}
            >
              ✗ {t}
            </div>
          ))}
        </div>
      ) : (
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1fr 1fr",
            gap: 12,
          }}
        >
          {["login.png", "dashboard.png", "regression-pass.png", "coverage.png"].map(
            (name, i) => (
              <div
                key={name}
                style={{
                  height: 110,
                  borderRadius: 12,
                  background: `linear-gradient(135deg, ${theme.success}55, ${theme.success}22)`,
                  border: `1px solid ${theme.success}55`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: theme.fontMono,
                  fontSize: 14,
                  color: theme.success,
                  opacity: interpolate(
                    frame,
                    [T.round2.from + 60 + i * 12, T.round2.from + 90 + i * 12],
                    [0, 1],
                    { extrapolateRight: "clamp" },
                  ),
                }}
              >
                📸 {name}
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
};

const FixLoopCard: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const s = useStrings();
  const sp = spring({
    frame: frame - T.fixLoop.from,
    fps,
    config: { damping: 18, stiffness: 130 },
  });
  return (
    <div
      style={{
        padding: 32,
        borderRadius: 20,
        background: "rgba(15,21,48,0.85)",
        border: `1px solid ${theme.warning}88`,
        boxShadow: `0 0 80px ${theme.warning}22`,
        opacity: sp,
        display: "flex",
        flexDirection: "column",
        gap: 18,
      }}
    >
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <div style={{ fontSize: 36 }}>🔧</div>
        <div
          style={{
            color: theme.warning,
            fontSize: 32,
            fontWeight: 800,
            fontFamily: theme.fontSans,
          }}
        >
          {s.rl_fixloop_subtitle}
        </div>
      </div>
      <div
        style={{
          color: theme.textMuted,
          fontFamily: theme.fontMono,
          fontSize: 16,
        }}
      >
        {s.rl_fixloop_intro}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {s.rl_fixloop_patches.map((p, i) => (
          <div
            key={p}
            style={{
              fontFamily: theme.fontMono,
              fontSize: 17,
              color: theme.text,
              opacity: interpolate(
                frame,
                [T.fixLoop.from + 14 + i * 18, T.fixLoop.from + 36 + i * 18],
                [0, 1],
                { extrapolateRight: "clamp" },
              ),
              background: "rgba(251,191,36,0.08)",
              padding: "10px 14px",
              borderRadius: 10,
              borderLeft: `3px solid ${theme.warning}`,
            }}
          >
            {p}
          </div>
        ))}
      </div>
    </div>
  );
};

const DeliveredCard: React.FC<{ frame: number; fps: number }> = ({ frame, fps }) => {
  const s = useStrings();
  const sp = spring({
    frame: frame - T.outro.from,
    fps,
    config: { damping: 14, stiffness: 130 },
  });
  return (
    <div
      style={{
        padding: 36,
        borderRadius: 24,
        background: `linear-gradient(135deg, ${theme.success}33, ${theme.accent}22)`,
        border: `1px solid ${theme.success}88`,
        boxShadow: `0 0 100px ${theme.success}44`,
        opacity: sp,
        transform: `scale(${interpolate(sp, [0, 1], [0.85, 1])})`,
        display: "flex",
        flexDirection: "column",
        gap: 18,
      }}
    >
      <div style={{ fontSize: 64 }}>🎉</div>
      <div
        style={{
          color: theme.text,
          fontSize: 38,
          fontWeight: 800,
          fontFamily: theme.fontSans,
        }}
      >
        {s.rl_delivered_title}
      </div>
      <div
        style={{
          color: theme.textMuted,
          fontSize: 20,
          fontFamily: theme.fontSans,
        }}
      >
        {s.rl_delivered_summary}
      </div>
      <div
        style={{
          padding: "16px 20px",
          background: "rgba(0,0,0,0.4)",
          borderRadius: 12,
          fontFamily: theme.fontMono,
          fontSize: 18,
          color: theme.primarySoft,
        }}
      >
        ↗ github.com/example/repo/pull/4242
      </div>
    </div>
  );
};
