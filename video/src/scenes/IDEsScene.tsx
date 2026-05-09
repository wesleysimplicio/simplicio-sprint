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

const IDES = [
  { name: "Claude Code", color: "#cd7f32" },
  { name: "GitHub Copilot", color: "#9ca3af" },
  { name: "Codex CLI", color: "#22d3ee" },
  { name: "Cursor", color: "#7c5cff" },
  { name: "Windsurf", color: "#34d399" },
  { name: "Kiro", color: "#fbbf24" },
  { name: "Zed", color: "#a78bff" },
  { name: "Cline", color: "#f87171" },
  { name: "Continue", color: "#22d3ee" },
  { name: "Aider", color: "#7c5cff" },
  { name: "Sourcegraph Cody", color: "#34d399" },
  { name: "Hermes", color: "#ff8a3d" },
];

export const IDEsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const s = useStrings();

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
      <Particles count={45} color="rgba(34,211,238,0.55)" speed={0.3} />
      <AbsoluteFill
        style={{
          padding: 90,
          alignItems: "center",
          justifyContent: "center",
          gap: 50,
        }}
      >
        <div style={{ textAlign: "center" }}>
          <div
            style={{
              color: theme.accent,
              fontFamily: theme.fontMono,
              letterSpacing: 6,
              fontSize: 22,
              marginBottom: 14,
            }}
          >
            {s.ides_eyebrow}
          </div>
          <AnimatedText
            text={s.ides_title}
            size={72}
            weight={800}
            gradient
            letterStagger={1.2}
          />
          <div
            style={{
              marginTop: 16,
              color: theme.textMuted,
              fontSize: 28,
              fontFamily: theme.fontSans,
              opacity: interpolate(frame, [30, 60], [0, 1], {
                extrapolateRight: "clamp",
              }),
            }}
          >
            {s.ides_lede}
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 18,
            width: "100%",
            maxWidth: 1500,
          }}
        >
          {IDES.map((ide, i) => (
            <IDETile
              key={ide.name}
              name={ide.name}
              color={ide.color}
              delay={50 + i * 6}
            />
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const IDETile: React.FC<{ name: string; color: string; delay: number }> = ({
  name,
  color,
  delay,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 15, stiffness: 150 },
  });
  const o = interpolate(s, [0, 1], [0, 1], { extrapolateRight: "clamp" });
  const scale = interpolate(s, [0, 1], [0.8, 1]);
  const initial = name
    .split(" ")
    .map((w) => w[0])
    .slice(0, 2)
    .join("");

  return (
    <div
      style={{
        opacity: o,
        transform: `scale(${scale})`,
        display: "flex",
        alignItems: "center",
        gap: 16,
        padding: "18px 22px",
        borderRadius: 16,
        background: "rgba(15,21,48,0.7)",
        border: `1px solid ${color}55`,
        boxShadow: `0 0 30px ${color}22`,
      }}
    >
      <div
        style={{
          width: 50,
          height: 50,
          borderRadius: 12,
          background: `linear-gradient(135deg, ${color}, ${color}99)`,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: theme.fontMono,
          fontWeight: 800,
          color: "white",
          fontSize: 20,
        }}
      >
        {initial}
      </div>
      <div
        style={{
          fontFamily: theme.fontSans,
          fontSize: 22,
          fontWeight: 600,
          color: theme.text,
        }}
      >
        {name}
      </div>
    </div>
  );
};
