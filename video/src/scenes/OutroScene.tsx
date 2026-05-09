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
import { Logo } from "../components/Logo";
import { AnimatedText } from "../components/AnimatedText";
import { theme } from "../theme";
import { useStrings } from "../i18n";

export const OutroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const t = useStrings();

  const ctaSpring = spring({
    frame: frame - 60,
    fps,
    config: { damping: 16, stiffness: 130 },
  });
  const fadeIn = interpolate(frame, [0, 18], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 24, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  return (
    <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
      <Background />
      <Particles count={80} color="rgba(167,139,255,0.7)" speed={0.5} />
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          padding: 80,
          gap: 36,
        }}
      >
        <Logo size={170} delay={0} />
        <AnimatedText
          text={t.outro_title}
          size={96}
          weight={900}
          gradient
          delay={20}
          letterStagger={1.5}
        />
        <div
          style={{
            transform: `scale(${interpolate(ctaSpring, [0, 1], [0.85, 1])})`,
            opacity: ctaSpring,
            display: "flex",
            gap: 20,
            alignItems: "center",
            padding: "22px 44px",
            borderRadius: 999,
            background: theme.gradient,
            color: "white",
            fontFamily: theme.fontSans,
            fontWeight: 800,
            fontSize: 38,
            letterSpacing: 1,
            boxShadow: "0 30px 80px rgba(124,92,255,0.55)",
          }}
        >
          <span style={{ fontFamily: theme.fontMono, opacity: 0.85 }}>›</span>
          {t.outro_cta}
        </div>
        <div
          style={{
            opacity: interpolate(frame, [90, 130], [0, 1], {
              extrapolateRight: "clamp",
            }),
            display: "flex",
            gap: 28,
            color: theme.textMuted,
            fontFamily: theme.fontMono,
            fontSize: 22,
            marginTop: 12,
          }}
        >
          <span>github.com/wesleysimplicio/sendsprint</span>
          <span style={{ opacity: 0.4 }}>•</span>
          <span>skills/claude/SKILL.md</span>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
