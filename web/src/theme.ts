export const theme = {
  bg: "#f5f9ff",
  bgDeep: "#e9f2ff",
  surface: "#ffffff",
  surfaceAlt: "#eef5ff",
  border: "#d7e4f5",
  text: "#12304f",
  textMuted: "#6c86a3",
  primary: "#2c6bed",
  primarySoft: "#5f97ff",
  accent: "#6dc8ff",
  accentWarm: "#ffb56a",
  success: "#1ea97c",
  warning: "#c18a17",
  danger: "#cf5161",
  fontMono: "Menlo",
  radius: 18,
  spacing: (n: number) => n * 4,
} as const;

export type Theme = typeof theme;
