export const theme = {
  bg: "#f8fafc",
  bgDeep: "#f1f5f9",
  surface: "#ffffff",
  surfaceAlt: "#f6f9fd",
  border: "#e2e8f0",
  text: "#0f172a",
  textMuted: "#64748b",
  primary: "#005ee8",
  primarySoft: "#2b7cf6",
  accent: "#38a9f7",
  accentWarm: "#f59e0b",
  success: "#16a34a",
  warning: "#d97706",
  danger: "#dc2626",
  fontSans: "Inter, Segoe UI, Helvetica Neue, Arial, sans-serif",
  fontMono: "Menlo, Consolas, monospace",
  radius: 8,
  spacing: (n: number) => n * 4,
} as const;

export type Theme = typeof theme;
