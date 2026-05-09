import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { theme } from "../theme";

type Props = {
  title: string;
  onPress: () => void;
  variant?: "primary" | "secondary" | "ghost" | "danger";
  loading?: boolean;
  disabled?: boolean;
  icon?: string;
};

export const Button: React.FC<Props> = ({
  title,
  onPress,
  variant = "primary",
  loading,
  disabled,
  icon,
}) => {
  const isDisabled = disabled || loading;
  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        styles[variant],
        pressed && !isDisabled && styles.pressed,
        isDisabled && styles.disabled,
      ]}
    >
      <View style={styles.row}>
        {loading ? (
          <ActivityIndicator color={variant === "primary" ? "white" : theme.text} />
        ) : (
          <>
            {icon ? <Text style={styles.icon}>{icon}</Text> : null}
            <Text style={[styles.label, variant === "ghost" && styles.labelGhost]}>
              {title}
            </Text>
          </>
        )}
      </View>
    </Pressable>
  );
};

const styles = StyleSheet.create({
  base: {
    paddingVertical: 14,
    paddingHorizontal: 22,
    borderRadius: theme.radius,
    alignItems: "center",
  },
  primary: {
    backgroundColor: theme.primary,
    shadowColor: theme.primary,
    shadowOpacity: 0.45,
    shadowRadius: 14,
    shadowOffset: { width: 0, height: 8 },
    elevation: 6,
  },
  secondary: {
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  ghost: {
    backgroundColor: "transparent",
  },
  danger: {
    backgroundColor: theme.danger,
  },
  pressed: { opacity: 0.85, transform: [{ scale: 0.99 }] },
  disabled: { opacity: 0.4 },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  icon: { color: theme.text, fontSize: 18 },
  label: { color: theme.text, fontSize: 16, fontWeight: "700" },
  labelGhost: { color: theme.primarySoft },
});
