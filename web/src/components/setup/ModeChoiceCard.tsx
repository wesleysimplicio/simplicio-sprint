import React from "react";
import { StyleSheet, Text, View } from "react-native";
import type { ProjectMode } from "../../api/types";
import { Card } from "../Card";
import { theme } from "../../theme";

type Props = {
  mode: ProjectMode;
  selected: boolean;
  title: string;
  description: string;
  meta: string;
  onPress: () => void;
};

export const ModeChoiceCard: React.FC<Props> = ({
  mode,
  selected,
  title,
  description,
  meta,
  onPress,
}) => (
  <Card onPress={onPress} selected={selected} style={styles.card}>
    <View style={styles.row}>
      <View style={[styles.badge, selected && styles.badgeSelected]}>
        <Text style={[styles.badgeText, selected && styles.badgeTextSelected]}>
          {mode === "single" ? "1" : "N"}
        </Text>
      </View>
      <View style={styles.copy}>
        <Text style={styles.title}>{title}</Text>
        <Text style={styles.description}>{description}</Text>
        <Text style={styles.meta}>{meta}</Text>
      </View>
      {selected ? <Text style={styles.check}>OK</Text> : null}
    </View>
  </Card>
);

const styles = StyleSheet.create({
  card: {
    flexGrow: 1,
    minWidth: 250,
  },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  badge: {
    width: 42,
    height: 42,
    borderRadius: 21,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  badgeSelected: {
    backgroundColor: theme.primary,
    borderColor: theme.primary,
  },
  badgeText: {
    color: theme.primary,
    fontWeight: "900",
    fontSize: 16,
  },
  badgeTextSelected: {
    color: "#ffffff",
  },
  copy: {
    flex: 1,
    gap: 3,
  },
  title: {
    color: theme.text,
    fontWeight: "800",
    fontSize: 16,
  },
  description: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 18,
  },
  meta: {
    color: theme.primary,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  check: {
    color: theme.primary,
    fontWeight: "800",
    fontSize: 12,
  },
});
