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
import { Card } from "../components/Card";
import { AnimatedText } from "../components/AnimatedText";
import { theme } from "../theme";
import { useStrings } from "../i18n";

export const WhatIsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const s = useStrings();
  const features = s.what_features;

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
      <Background variant="deep" />
      <Particles count={40} />
      <AbsoluteFill
        style={{
          alignItems: "center",
          justifyContent: "center",
          padding: 80,
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
            {s.what_eyebrow}
          </div>
          <AnimatedText
            text={s.what_title}
            size={76}
            weight={800}
            delay={6}
            gradient
            letterStagger={1.2}
          />
          <div
            style={{
              marginTop: 18,
              color: theme.textMuted,
              fontSize: 30,
              fontFamily: theme.fontSans,
              opacity: interpolate(frame, [40, 70], [0, 1], {
                extrapolateRight: "clamp",
              }),
            }}
          >
            {s.what_lede}
          </div>
        </div>

        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(4, 1fr)",
            gap: 28,
            width: "100%",
            maxWidth: 1500,
            marginTop: 20,
          }}
        >
          {features.map((f, i) => (
            <FeatureCard
              key={f.title}
              emoji={f.emoji}
              title={f.title}
              desc={f.desc}
              delay={70 + i * 10}
            />
          ))}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const FeatureCard: React.FC<{
  emoji: string;
  title: string;
  desc: string;
  delay: number;
}> = ({ emoji, title, desc, delay }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 18, stiffness: 130 },
  });
  const scale = interpolate(s, [0, 1], [0.85, 1]);
  const float = Math.sin((frame - delay) / 24) * 4;

  return (
    <Card
      delay={delay}
      style={{
        textAlign: "center",
        transform: `translateY(${float}px) scale(${scale})`,
      }}
    >
      <div style={{ fontSize: 60 }}>{emoji}</div>
      <div
        style={{
          fontFamily: theme.fontSans,
          fontSize: 30,
          fontWeight: 700,
          color: theme.text,
          marginTop: 10,
        }}
      >
        {title}
      </div>
      <div
        style={{
          fontFamily: theme.fontMono,
          fontSize: 18,
          color: theme.textMuted,
          marginTop: 6,
        }}
      >
        {desc}
      </div>
    </Card>
  );
};
