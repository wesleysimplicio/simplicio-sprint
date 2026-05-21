import React from "react";
import {
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { theme } from "../theme";

export type TerminalLine = {
  prompt?: string;
  text: string;
  color?: string;
  delay?: number;
  speed?: number;
};

type Props = {
  title?: string;
  lines: TerminalLine[];
  width?: number;
  height?: number;
  startDelay?: number;
  showCursor?: boolean;
  className?: string;
};

export const Terminal: React.FC<Props> = ({
  title = "~/sendsprint — claude code",
  lines,
  width = 980,
  height = 520,
  startDelay = 0,
  showCursor = true,
  className,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const open = spring({
    frame: frame - startDelay,
    fps,
    config: { damping: 18, stiffness: 130, mass: 0.7 },
  });

  const scale = interpolate(open, [0, 1], [0.92, 1]);
  const opacity = interpolate(open, [0, 1], [0, 1], {
    extrapolateRight: "clamp",
  });
  const y = interpolate(open, [0, 1], [30, 0]);

  return (
    <div
      className={className}
      style={{
        width,
        height,
        background: "rgba(8, 11, 26, 0.92)",
        borderRadius: 18,
        border: `1px solid ${theme.border}`,
        boxShadow:
          "0 30px 80px rgba(0,0,0,0.55), 0 0 0 1px rgba(255,255,255,0.04) inset, 0 0 60px rgba(124, 92, 255, 0.18)",
        backdropFilter: "blur(8px)",
        transform: `translateY(${y}px) scale(${scale})`,
        opacity,
        overflow: "hidden",
        display: "flex",
        flexDirection: "column",
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 10,
          padding: "14px 18px",
          borderBottom: `1px solid ${theme.border}`,
          background: "rgba(255,255,255,0.03)",
        }}
      >
        <Dot color="#ff5f56" />
        <Dot color="#ffbd2e" />
        <Dot color="#27c93f" />
        <div
          style={{
            marginLeft: 14,
            fontFamily: theme.fontMono,
            fontSize: 18,
            color: theme.textMuted,
          }}
        >
          {title}
        </div>
      </div>
      <div
        style={{
          flex: 1,
          padding: "22px 26px",
          fontFamily: theme.fontMono,
          fontSize: 22,
          lineHeight: 1.55,
          color: theme.text,
          display: "flex",
          flexDirection: "column",
          gap: 8,
        }}
      >
        {lines.map((line, i) => (
          <TerminalLineView
            key={i}
            line={line}
            startFrame={startDelay + (line.delay ?? 0)}
            isLast={i === lines.length - 1}
            showCursor={showCursor}
          />
        ))}
      </div>
    </div>
  );
};

const Dot: React.FC<{ color: string }> = ({ color }) => (
  <div
    style={{
      width: 14,
      height: 14,
      borderRadius: "50%",
      background: color,
      boxShadow: `0 0 8px ${color}55`,
    }}
  />
);

const TerminalLineView: React.FC<{
  line: TerminalLine;
  startFrame: number;
  isLast: boolean;
  showCursor: boolean;
}> = ({ line, startFrame, isLast, showCursor }) => {
  const frame = useCurrentFrame();
  const speed = line.speed ?? 1.5;
  const elapsed = Math.max(0, frame - startFrame);
  const charsTyped = Math.min(line.text.length, Math.floor(elapsed * speed));
  const visibleText = line.text.slice(0, charsTyped);
  const visible = elapsed > 0;
  const cursorBlink = isLast && showCursor && Math.floor(frame / 15) % 2 === 0;

  if (!visible) return <div style={{ height: 30 }} />;

  return (
    <div style={{ display: "flex", gap: 12, alignItems: "baseline" }}>
      {line.prompt ? (
        <span style={{ color: theme.accent }}>{line.prompt}</span>
      ) : null}
      <span style={{ color: line.color ?? theme.text }}>
        {visibleText}
        {cursorBlink && charsTyped >= line.text.length ? (
          <span style={{ color: theme.primarySoft }}>▍</span>
        ) : null}
      </span>
    </div>
  );
};
