import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { theme } from "../theme";

type Props = {
  delay?: number;
  width?: number | string;
  padding?: number;
  glow?: string;
  className?: string;
  children: React.ReactNode;
  style?: React.CSSProperties;
};

export const Card: React.FC<Props> = ({
  delay = 0,
  width = "auto",
  padding = 28,
  glow = "rgba(124, 92, 255, 0.35)",
  className,
  children,
  style,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const s = spring({
    frame: frame - delay,
    fps,
    config: { damping: 18, stiffness: 140, mass: 0.6 },
  });
  const scale = interpolate(s, [0, 1], [0.9, 1]);
  const y = interpolate(s, [0, 1], [30, 0]);
  const opacity = interpolate(s, [0, 1], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <div
      className={className}
      style={{
        width,
        padding,
        borderRadius: 18,
        background:
          "linear-gradient(180deg, rgba(255,255,255,0.04), rgba(255,255,255,0.015))",
        border: `1px solid ${theme.border}`,
        boxShadow: `0 25px 60px rgba(0,0,0,0.45), 0 0 60px ${glow}`,
        backdropFilter: "blur(8px)",
        transform: `translateY(${y}px) scale(${scale})`,
        opacity,
        ...style,
      }}
    >
      {children}
    </div>
  );
};
