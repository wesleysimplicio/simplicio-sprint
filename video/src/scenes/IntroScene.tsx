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

export const IntroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const s = useStrings();

  const fadeOut = interpolate(
    frame,
    [durationInFrames - 18, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const subtitleSpring = spring({
    frame: frame - 50,
    fps,
    config: { damping: 22, stiffness: 130 },
  });

  return (
    <AbsoluteFill style={{ opacity: fadeOut }}>
      <Background />
      <Particles count={70} />
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          gap: 36,
          padding: 80,
        }}
      >
        <Logo size={220} />
        <div style={{ marginTop: 12 }}>
          <AnimatedText
            text="SendSprint"
            delay={20}
            size={140}
            weight={900}
            gradient
            letterStagger={3}
          />
        </div>
        <div
          style={{
            transform: `translateY(${interpolate(subtitleSpring, [0, 1], [20, 0])}px)`,
            opacity: subtitleSpring,
            fontFamily: theme.fontSans,
            fontSize: 36,
            color: theme.textMuted,
            letterSpacing: 2,
            textTransform: "uppercase",
          }}
        >
          {s.intro_subtitle}
        </div>
        <div
          style={{
            position: "absolute",
            bottom: 60,
            opacity: interpolate(frame, [70, 100], [0, 1], {
              extrapolateRight: "clamp",
            }),
            color: theme.textMuted,
            fontFamily: theme.fontMono,
            fontSize: 22,
            letterSpacing: 4,
          }}
        >
          {s.intro_tag}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
