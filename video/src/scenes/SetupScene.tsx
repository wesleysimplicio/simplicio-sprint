import React from "react";
import {
  AbsoluteFill,
  interpolate,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { Background } from "../components/Background";
import { Particles } from "../components/Particles";
import { Terminal, TerminalLine } from "../components/Terminal";
import { AnimatedText } from "../components/AnimatedText";
import { Card } from "../components/Card";
import { theme } from "../theme";
import { useStrings } from "../i18n";

export const SetupScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const t = useStrings();
  const installLines: TerminalLine[] = [
    { prompt: "$", text: 'pip install -e ".[dev]"', delay: 0, speed: 1.6 },
    { prompt: "$", text: "playwright install chromium", delay: 30, speed: 1.6 },
    { prompt: "$", text: "sendsprint init", color: theme.primarySoft, delay: 60, speed: 1.5 },
    { prompt: "✓", text: t.setup_msg_stack_detected, color: theme.success, delay: 88 },
    { prompt: "$", text: "sendsprint login jira", color: theme.primarySoft, delay: 110, speed: 1.5 },
    { prompt: "✓", text: t.setup_msg_creds_saved, color: theme.success, delay: 140 },
  ];
  const STEPS_SHORT = t.setup_steps.map((entry, i) => ({
    n: i + 1,
    title: entry.title,
    desc: entry.desc,
  }));
  const fadeIn = interpolate(frame, [0, 14], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 18, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
      <Background variant="warm" />
      <Particles count={30} color="rgba(255,138,61,0.5)" speed={0.25} />
      <AbsoluteFill
        style={{
          padding: 80,
          display: "grid",
          gridTemplateColumns: "1fr 1.05fr",
          alignItems: "center",
          gap: 60,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>
          <div
            style={{
              color: theme.accentWarm,
              fontFamily: theme.fontMono,
              letterSpacing: 6,
              fontSize: 22,
            }}
          >
            {t.setup_eyebrow}
          </div>
          <AnimatedText
            text={t.setup_title}
            size={84}
            weight={800}
            gradient
            align="left"
            letterStagger={1.4}
          />
          <div
            style={{
              color: theme.textMuted,
              fontFamily: theme.fontSans,
              fontSize: 26,
              maxWidth: 560,
            }}
          >
            {t.setup_lede}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            {STEPS_SHORT.map((s, i) => (
              <SetupStep
                key={s.n}
                num={s.n}
                title={s.title}
                desc={s.desc}
                delay={36 + i * 14}
              />
            ))}
          </div>
        </div>

        <div style={{ display: "flex", justifyContent: "center" }}>
          <Terminal
            title={t.setup_install_title}
            lines={installLines}
            startDelay={20}
            width={820}
            height={520}
          />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const SetupStep: React.FC<{
  num: number;
  title: string;
  desc: string;
  delay: number;
}> = ({ num, title, desc, delay }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [delay, delay + 18], [0, 1], {
    extrapolateRight: "clamp",
  });
  const x = interpolate(frame, [delay, delay + 22], [-20, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      style={{
        opacity: o,
        transform: `translateX(${x}px)`,
        display: "flex",
        gap: 18,
        alignItems: "center",
        padding: "14px 18px",
        background: "rgba(255,138,61,0.08)",
        border: "1px solid rgba(255,138,61,0.35)",
        borderRadius: 14,
      }}
    >
      <div
        style={{
          width: 46,
          height: 46,
          borderRadius: 12,
          background: theme.gradientWarm,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "white",
          fontFamily: theme.fontMono,
          fontWeight: 800,
          fontSize: 22,
          boxShadow: "0 8px 24px rgba(255,138,61,0.45)",
        }}
      >
        {num}
      </div>
      <div>
        <div
          style={{
            fontFamily: theme.fontSans,
            fontSize: 24,
            fontWeight: 700,
            color: theme.text,
          }}
        >
          {title}
        </div>
        <div
          style={{
            fontFamily: theme.fontMono,
            fontSize: 18,
            color: theme.textMuted,
            marginTop: 2,
          }}
        >
          {desc}
        </div>
      </div>
    </div>
  );
};
