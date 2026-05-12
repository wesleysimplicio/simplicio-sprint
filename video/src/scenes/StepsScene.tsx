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
import { StepIcon, IconKey } from "../components/StepIcon";
import { theme } from "../theme";
import { useStrings, type Strings } from "../i18n";

type Step = {
  num: number;
  title: string;
  desc: string;
  icon: IconKey;
  accent: string;
  details: string[];
};

const ICONS: IconKey[] = [
  "sprint",
  "architecture",
  "build",
  "lint",
  "test",
  "security",
  "loop",
  "commit",
  "pr",
  "review",
];

const ACCENTS = [
  "#7c5cff",
  "#22d3ee",
  "#34d399",
  "#a78bff",
  "#fbbf24",
  "#f87171",
  "#ff8a3d",
  "#22d3ee",
  "#7c5cff",
  "#34d399",
];

const buildSteps = (s: Strings): Step[] =>
  s.steps.map((entry, i) => ({
    num: i + 1,
    title: entry.title,
    desc: entry.desc,
    icon: ICONS[i],
    accent: ACCENTS[i],
    details: entry.details,
  }));

const HEADER_FRAMES = 50;
const STEP_FRAMES = 55;

export const StepsScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const strings = useStrings();
  const STEPS = buildSteps(strings);

  const fadeIn = interpolate(frame, [0, 14], [0, 1], {
    extrapolateRight: "clamp",
  });
  const fadeOut = interpolate(
    frame,
    [durationInFrames - 18, durationInFrames],
    [1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" },
  );

  const stepIndex = Math.min(
    STEPS.length - 1,
    Math.max(0, Math.floor((frame - HEADER_FRAMES) / STEP_FRAMES)),
  );
  const localStepFrame = frame - HEADER_FRAMES - stepIndex * STEP_FRAMES;
  const stepEntry = spring({
    frame: localStepFrame,
    fps,
    config: { damping: 18, stiffness: 140 },
  });

  return (
    <AbsoluteFill style={{ opacity: fadeIn * fadeOut }}>
      <Background variant="deep" />
      <Particles count={28} speed={0.2} />
      <AbsoluteFill style={{ padding: "60px 80px", display: "flex", flexDirection: "column" }}>
        <Header />
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "1.05fr 1fr",
            gap: 60,
            flex: 1,
            marginTop: 30,
          }}
        >
          <StepsList steps={STEPS} currentIndex={stepIndex} />
          <StepFocus
            step={STEPS[stepIndex]}
            entry={stepEntry}
            localFrame={localStepFrame}
            progressLabel={strings.steps_progress_label}
          />
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

const Header: React.FC = () => {
  const s = useStrings();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 28 }}>
      <div
        style={{
          padding: "10px 18px",
          borderRadius: 999,
          background: "rgba(124,92,255,0.18)",
          color: theme.primarySoft,
          fontFamily: theme.fontMono,
          letterSpacing: 4,
          fontSize: 20,
        }}
      >
        {s.steps_eyebrow}
      </div>
      <AnimatedText
        text={s.steps_title}
        size={64}
        weight={800}
        gradient
        align="left"
        letterStagger={1}
      />
    </div>
  );
};

const StepsList: React.FC<{ steps: Step[]; currentIndex: number }> = ({
  steps,
  currentIndex,
}) => {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {steps.map((s, i) => {
        const active = i === currentIndex;
        const done = i < currentIndex;
        return (
          <div
            key={s.num}
            style={{
              display: "flex",
              alignItems: "center",
              gap: 18,
              padding: "12px 18px",
              borderRadius: 14,
              background: active
                ? `linear-gradient(90deg, ${s.accent}33, transparent)`
                : "transparent",
              border: active
                ? `1px solid ${s.accent}88`
                : "1px solid transparent",
              transition: "all 0.2s",
            }}
          >
            <div
              style={{
                width: 46,
                height: 46,
                borderRadius: 12,
                background: done
                  ? theme.success
                  : active
                    ? s.accent
                    : "rgba(255,255,255,0.05)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                color: done || active ? "white" : theme.textMuted,
                fontFamily: theme.fontMono,
                fontWeight: 700,
                fontSize: 22,
                boxShadow: active ? `0 0 24px ${s.accent}88` : "none",
              }}
            >
              {done ? "✓" : s.num}
            </div>
            <div
              style={{
                fontFamily: theme.fontSans,
                fontSize: 28,
                fontWeight: active ? 700 : 500,
                color: active
                  ? theme.text
                  : done
                    ? theme.textMuted
                    : "rgba(241,244,255,0.55)",
              }}
            >
              {s.title}
            </div>
          </div>
        );
      })}
    </div>
  );
};

const StepFocus: React.FC<{
  step: Step;
  entry: number;
  localFrame: number;
  progressLabel: string;
}> = ({ step, entry, localFrame, progressLabel }) => {
  const opacity = interpolate(entry, [0, 1], [0, 1], {
    extrapolateRight: "clamp",
  });
  const x = interpolate(entry, [0, 1], [40, 0]);
  const float = Math.sin(localFrame / 14) * 5;

  return (
    <div
      key={step.num}
      style={{
        position: "relative",
        opacity,
        transform: `translateX(${x}px)`,
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: -30,
          background: `radial-gradient(circle at 50% 40%, ${step.accent}55, transparent 65%)`,
          filter: "blur(40px)",
        }}
      />
      <div
        style={{
          position: "relative",
          padding: 40,
          borderRadius: 24,
          background: "rgba(15,21,48,0.85)",
          border: `1px solid ${step.accent}66`,
          boxShadow: `0 30px 80px rgba(0,0,0,0.55), 0 0 60px ${step.accent}33`,
          display: "flex",
          flexDirection: "column",
          gap: 24,
          backdropFilter: "blur(8px)",
          minHeight: 460,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
          <div
            style={{
              width: 110,
              height: 110,
              borderRadius: 28,
              background: `linear-gradient(135deg, ${step.accent}, ${step.accent}aa)`,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transform: `translateY(${float}px)`,
              boxShadow: `0 18px 40px ${step.accent}55`,
            }}
          >
            <StepIcon name={step.icon} size={70} color="white" />
          </div>
          <div>
            <div
              style={{
                fontFamily: theme.fontMono,
                fontSize: 22,
                color: step.accent,
                letterSpacing: 4,
              }}
            >
              STEP {String(step.num).padStart(2, "0")}
            </div>
            <div
              style={{
                fontFamily: theme.fontSans,
                fontSize: 52,
                fontWeight: 800,
                color: theme.text,
                marginTop: 4,
              }}
            >
              {step.title}
            </div>
          </div>
        </div>
        <div
          style={{
            fontFamily: theme.fontSans,
            fontSize: 30,
            color: theme.textMuted,
          }}
        >
          {step.desc}
        </div>
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 12,
            marginTop: 6,
          }}
        >
          {step.details.map((d, i) => (
            <DetailLine key={d} text={d} delay={i * 8} />
          ))}
        </div>
        <ProgressBar accent={step.accent} num={step.num} label={progressLabel} />
      </div>
    </div>
  );
};

const DetailLine: React.FC<{ text: string; delay: number }> = ({
  text,
  delay,
}) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [delay + 8, delay + 24], [0, 1], {
    extrapolateRight: "clamp",
    extrapolateLeft: "clamp",
  });
  return (
    <div
      style={{
        opacity: o,
        display: "flex",
        alignItems: "center",
        gap: 14,
        fontFamily: theme.fontMono,
        fontSize: 24,
        color: theme.text,
      }}
    >
      <span
        style={{
          width: 8,
          height: 8,
          borderRadius: "50%",
          background: theme.accent,
          boxShadow: `0 0 12px ${theme.accent}aa`,
        }}
      />
      {text}
    </div>
  );
};

const ProgressBar: React.FC<{ accent: string; num: number; label: string }> = ({
  accent,
  num,
  label,
}) => {
  const pct = (num / 10) * 100;
  return (
    <div style={{ marginTop: "auto" }}>
      <div
        style={{
          height: 6,
          background: "rgba(255,255,255,0.07)",
          borderRadius: 999,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: `linear-gradient(90deg, ${accent}, ${accent}88)`,
            boxShadow: `0 0 12px ${accent}cc`,
          }}
        />
      </div>
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 8,
          fontFamily: theme.fontMono,
          fontSize: 16,
          color: theme.textMuted,
        }}
      >
        <span>{label}</span>
        <span>{num}/10</span>
      </div>
    </div>
  );
};
