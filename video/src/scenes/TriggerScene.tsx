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
import { theme } from "../theme";
import { useStrings } from "../i18n";

const lineStyle = (i: number, total: number): Pick<TerminalLine, "color" | "delay" | "speed"> => {
  if (i === 0) return { color: theme.text, delay: 0, speed: 1.6 };
  if (i === total - 1) return { color: theme.success, delay: 36 + (i - 1) * 24 };
  return { color: theme.accent, delay: 36 + (i - 1) * 24 };
};

export const TriggerScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const s = useStrings();
  const triggers = s.trigger_chips;
  const lines: TerminalLine[] = s.trigger_lines.map((l, i) => ({
    prompt: l.prompt,
    text: l.text,
    ...lineStyle(i, s.trigger_lines.length),
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
      <Background variant="soft" />
      <Particles count={35} color="rgba(167,139,255,0.55)" speed={0.25} />
      <AbsoluteFill
        style={{
          padding: 80,
          display: "grid",
          gridTemplateColumns: "1fr 1.1fr",
          alignItems: "center",
          gap: 60,
        }}
      >
        <div style={{ display: "flex", flexDirection: "column", gap: 30 }}>
          <div
            style={{
              color: theme.accent,
              fontFamily: theme.fontMono,
              letterSpacing: 6,
              fontSize: 22,
            }}
          >
            {s.trigger_eyebrow}
          </div>
          <AnimatedText
            text={s.trigger_title}
            size={84}
            weight={800}
            gradient
            align="left"
            letterStagger={1.5}
          />
          <div
            style={{
              color: theme.textMuted,
              fontFamily: theme.fontSans,
              fontSize: 26,
              maxWidth: 620,
            }}
          >
            {s.trigger_lede}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
            {triggers.map((t, i) => (
              <TriggerChip key={t.phrase} delay={30 + i * 12} {...t} />
            ))}
          </div>
        </div>
        <div style={{ display: "flex", justifyContent: "center" }}>
          <Terminal lines={lines} startDelay={20} width={840} height={460} />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const TriggerChip: React.FC<{
  lang: string;
  phrase: string;
  delay: number;
}> = ({ lang, phrase, delay }) => {
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
        alignItems: "center",
        gap: 16,
        padding: "12px 20px",
        background: "rgba(124, 92, 255, 0.12)",
        border: "1px solid rgba(124,92,255,0.4)",
        borderRadius: 999,
        width: "fit-content",
      }}
    >
      <span
        style={{
          fontFamily: theme.fontMono,
          fontSize: 16,
          color: theme.primarySoft,
          background: "rgba(124,92,255,0.2)",
          padding: "4px 10px",
          borderRadius: 999,
          letterSpacing: 1,
        }}
      >
        {lang}
      </span>
      <span
        style={{
          fontFamily: theme.fontMono,
          fontSize: 26,
          color: theme.text,
        }}
      >
        “{phrase}”
      </span>
    </div>
  );
};
