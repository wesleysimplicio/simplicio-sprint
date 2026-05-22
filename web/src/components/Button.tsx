import React from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { theme } from "../theme";
import { Icon, type IconName } from "./Icon";

type Variant = "primary" | "secondary" | "ghost" | "danger" | "outline";

type Size = "sm" | "md" | "lg";

type Props = {
  title: string;
  onPress: () => void;
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  disabled?: boolean;
  iconLeft?: IconName;
  iconRight?: IconName;
  fullWidth?: boolean;
};

export const Button: React.FC<Props> = ({
  title,
  onPress,
  variant = "primary",
  size = "md",
  loading,
  disabled,
  iconLeft,
  iconRight,
  fullWidth,
}) => {
  const isDisabled = disabled || loading;
  const isLight = variant !== "primary" && variant !== "danger";
  const labelColor = isLight ? theme.text : "#ffffff";
  const labelColorOutline = variant === "outline" ? theme.primary : labelColor;
  const labelColorGhost = variant === "ghost" ? theme.primary : labelColor;
  const iconColor =
    variant === "outline" || variant === "ghost"
      ? theme.primary
      : variant === "primary" || variant === "danger"
        ? "#ffffff"
        : theme.text;

  return (
    <Pressable
      onPress={onPress}
      disabled={isDisabled}
      style={({ pressed }) => [
        styles.base,
        size === "sm" && styles.sm,
        size === "lg" && styles.lg,
        styles[variant],
        fullWidth && styles.fullWidth,
        pressed && !isDisabled && styles.pressed,
        isDisabled && styles.disabled,
      ]}
    >
      <View style={styles.row}>
        {loading ? (
          <ActivityIndicator
            color={
              variant === "primary" || variant === "danger" ? "#fff" : theme.primary
            }
            size="small"
          />
        ) : (
          <>
            {iconLeft ? (
              <Icon
                name={iconLeft}
                size={size === "lg" ? 16 : 14}
                color={iconColor}
              />
            ) : null}
            <Text
              style={[
                styles.label,
                size === "sm" && styles.labelSm,
                size === "lg" && styles.labelLg,
                {
                  color:
                    variant === "ghost"
                      ? labelColorGhost
                      : variant === "outline"
                        ? labelColorOutline
                        : labelColor,
                },
              ]}
            >
              {title}
            </Text>
            {iconRight ? (
              <Icon
                name={iconRight}
                size={size === "lg" ? 16 : 14}
                color={iconColor}
              />
            ) : null}
          </>
        )}
      </View>
    </Pressable>
  );
};

const styles = StyleSheet.create({
  base: {
    minHeight: 40,
    paddingVertical: 10,
    paddingHorizontal: 18,
    borderRadius: theme.radius,
    alignItems: "center",
    justifyContent: "center",
  },
  sm: {
    minHeight: 32,
    paddingVertical: 7,
    paddingHorizontal: 12,
    borderRadius: 7,
  },
  lg: {
    minHeight: 48,
    paddingVertical: 13,
    paddingHorizontal: 22,
  },
  fullWidth: { width: "100%" },
  primary: {
    backgroundColor: theme.primary,
  },
  secondary: {
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
  },
  outline: {
    backgroundColor: "transparent",
    borderWidth: 1,
    borderColor: theme.primary,
  },
  ghost: {
    backgroundColor: "transparent",
  },
  danger: {
    backgroundColor: theme.danger,
  },
  pressed: { opacity: 0.86 },
  disabled: { opacity: 0.45 },
  row: { flexDirection: "row", alignItems: "center", gap: 8 },
  label: {
    color: "#ffffff",
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
    letterSpacing: -0.1,
  },
  labelSm: { fontSize: 12 },
  labelLg: { fontSize: 14 },
});
