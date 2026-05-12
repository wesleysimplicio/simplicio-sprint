export const theme = {
  bg: "#070b1a",
  bgDeep: "#03050d",
  surface: "#0f1530",
  surfaceAlt: "#141d3f",
  border: "rgba(120, 145, 255, 0.18)",
  text: "#f1f4ff",
  textMuted: "#9aa3c7",
  primary: "#7c5cff",
  primarySoft: "#a78bff",
  accent: "#22d3ee",
  accentWarm: "#ff8a3d",
  success: "#34d399",
  warning: "#fbbf24",
  danger: "#f87171",
  fontMono: "Menlo",
  radius: 14,
  spacing: (n: number) => n * 4,
} as const;

export type Theme = typeof theme;
