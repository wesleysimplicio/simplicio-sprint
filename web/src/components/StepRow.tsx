import React from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { theme } from "../theme";

type Props = {
  num: number;
  name: string;
  status: "pending" | "running" | "ok" | "skipped" | "failed";
  message?: string;
};

const COLORS: Record<Props["status"], string> = {
  pending: theme.textMuted,
  running: theme.primary,
  ok: theme.success,
  skipped: theme.warning,
  failed: theme.danger,
};

const ICONS: Record<Props["status"], string> = {
  pending: "•",
  running: "↻",
  ok: "✓",
  skipped: "—",
  failed: "✗",
};

export const StepRow: React.FC<Props> = ({ num, name, status, message }) => {
  const color = COLORS[status];
  return (
    <View style={[styles.row, status === "running" && styles.rowActive]}>
      <View style={[styles.bullet, { borderColor: color }]}>
        {status === "running" ? (
          <ActivityIndicator size="small" color={color} />
        ) : (
          <Text style={[styles.bulletText, { color }]}>{ICONS[status]}</Text>
        )}
      </View>
      <View style={{ flex: 1 }}>
        <View style={styles.titleRow}>
          <Text style={styles.num}>STEP {String(num).padStart(2, "0")}</Text>
          <Text style={[styles.name, { color: status === "pending" ? theme.textMuted : theme.text }]}>
            {name}
          </Text>
        </View>
        {message ? <Text style={styles.message}>{message}</Text> : null}
      </View>
    </View>
  );
};

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    gap: 12,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: theme.radius,
  },
  rowActive: {
    backgroundColor: "rgba(124,92,255,0.1)",
    borderWidth: 1,
    borderColor: "rgba(124,92,255,0.4)",
  },
  bullet: {
    width: 32,
    height: 32,
    borderRadius: 16,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },
  bulletText: { fontSize: 16, fontWeight: "700" },
  titleRow: { flexDirection: "row", alignItems: "baseline", gap: 8 },
  num: {
    color: theme.textMuted,
    fontFamily: theme.fontMono,
    fontSize: 11,
    letterSpacing: 1,
  },
  name: { fontSize: 15, fontWeight: "600" },
  message: {
    color: theme.textMuted,
    fontSize: 13,
    marginTop: 2,
    fontFamily: theme.fontMono,
  },
});
