import React from "react";
import { Pressable, StyleSheet, View, ViewStyle } from "react-native";
import { theme } from "../theme";

type Props = {
  children: React.ReactNode;
  onPress?: () => void;
  selected?: boolean;
  style?: ViewStyle | ViewStyle[];
};

export const Card: React.FC<Props> = ({ children, onPress, selected, style }) => {
  const content = (
    <View
      style={[
        styles.card,
        selected && styles.selected,
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
        style={({ pressed }) => [pressed && { opacity: 0.85 }]}
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
    padding: 16,
    borderWidth: 1,
    borderColor: theme.border,
    gap: 6,
    shadowColor: "#91b4dc",
    shadowOpacity: 0.14,
    shadowRadius: 16,
    shadowOffset: { width: 0, height: 8 },
    elevation: 3,
  },
  selected: {
    borderColor: theme.primary,
    shadowColor: theme.primary,
    shadowOpacity: 0.16,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 4 },
    elevation: 4,
  },
});
