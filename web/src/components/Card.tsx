import React from "react";
import { Pressable, StyleSheet, View, ViewStyle } from "react-native";
import { theme } from "../theme";

type Variant = "default" | "muted" | "accent" | "flat";

type Props = {
  children: React.ReactNode;
  onPress?: () => void;
  selected?: boolean;
  variant?: Variant;
  padding?: number;
  style?: ViewStyle | ViewStyle[];
};

export const Card: React.FC<Props> = ({
  children,
  onPress,
  selected,
  variant = "default",
  padding,
  style,
}) => {
  const content = (
    <View
      style={[
        styles.card,
        variant === "muted" && styles.muted,
        variant === "accent" && styles.accent,
        variant === "flat" && styles.flat,
        selected && styles.selected,
        padding !== undefined && { padding },
        ...(Array.isArray(style) ? style : style ? [style] : []),
      ]}
    >
      {children}
    </View>
  );

  if (onPress) {
    return (
      <Pressable
        onPress={onPress}
        style={({ pressed }) => [pressed && { opacity: 0.92 }]}
      >
        {content}
      </Pressable>
    );
  }
  return content;
};

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 18,
    borderWidth: 1,
    borderColor: theme.border,
    gap: 8,
  },
  muted: {
    backgroundColor: theme.surfaceAlt,
  },
  accent: {
    backgroundColor: theme.primaryFaint,
    borderColor: "rgba(30, 99, 236, 0.18)",
  },
  flat: {
    borderColor: "transparent",
    backgroundColor: "transparent",
  },
  selected: {
    borderColor: theme.primary,
    borderWidth: 1.5,
  },
});
