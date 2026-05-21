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
  pending: "-",
  running: "...",
  ok: "OK",
  skipped: "--",
  failed: "X",
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
    gap: 10,
    paddingVertical: 8,
    paddingHorizontal: 10,
    borderRadius: theme.radius,
  },
  rowActive: {
    backgroundColor: "rgba(0,94,232,0.08)",
    borderWidth: 1,
    borderColor: "rgba(0,94,232,0.22)",
  },
  bullet: {
    width: 26,
    height: 26,
    borderRadius: 13,
    borderWidth: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  bulletText: {
    fontSize: 9,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  titleRow: {
    flexDirection: "row",
    alignItems: "baseline",
    gap: 8,
  },
  num: {
    color: theme.textMuted,
    fontFamily: theme.fontMono,
    fontSize: 10,
    letterSpacing: 0.6,
  },
  name: {
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  message: {
    color: theme.textMuted,
    fontSize: 11,
    marginTop: 2,
    fontFamily: theme.fontMono,
  },
});
