import React, { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { theme } from "../theme";
import { Icon, type IconName } from "./Icon";

type Props = {
  label?: string;
  value: string;
  onChangeText: (v: string) => void;
  placeholder?: string;
  secureTextEntry?: boolean;
  autoCapitalize?: "none" | "sentences" | "words" | "characters";
  keyboardType?: "default" | "email-address" | "url" | "numeric";
  monospace?: boolean;
  hint?: string;
  trailingIcon?: IconName;
  onTrailingPress?: () => void;
  iconLeft?: IconName;
  multiline?: boolean;
  numberOfLines?: number;
  inlineLabelRight?: React.ReactNode;
};

export const Input: React.FC<Props> = ({
  label,
  value,
  onChangeText,
  placeholder,
  secureTextEntry,
  autoCapitalize = "none",
  keyboardType = "default",
  monospace,
  hint,
  trailingIcon,
  onTrailingPress,
  iconLeft,
  multiline,
  numberOfLines,
  inlineLabelRight,
}) => {
  const [focused, setFocused] = useState(false);
  const [reveal, setReveal] = useState(false);
  const isSecret = !!secureTextEntry;
  const obscured = isSecret && !reveal;
  const showEyeToggle = isSecret;

  return (
    <View style={styles.wrap}>
      {label ? (
        <View style={styles.labelRow}>
          <Text style={styles.label}>{label}</Text>
          {inlineLabelRight ? <View>{inlineLabelRight}</View> : null}
        </View>
      ) : null}
      <View
        style={[
          styles.inputWrap,
          focused && styles.inputWrapFocused,
          multiline && styles.inputWrapMulti,
        ]}
      >
        {iconLeft ? (
          <View style={styles.iconLeft}>
            <Icon name={iconLeft} size={15} color={theme.textMuted} />
          </View>
        ) : null}
        <TextInput
          accessibilityLabel={label ?? placeholder}
          value={value}
          onChangeText={onChangeText}
          placeholder={placeholder}
          placeholderTextColor={theme.textSoft}
          secureTextEntry={obscured}
          autoCapitalize={autoCapitalize}
          autoCorrect={false}
          keyboardType={keyboardType}
          multiline={multiline}
          numberOfLines={numberOfLines}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          style={[
            styles.input,
            monospace && { fontFamily: theme.fontMono, fontSize: 12 },
            iconLeft ? { paddingLeft: 0 } : null,
            multiline && { textAlignVertical: "top", minHeight: 80 },
          ]}
        />
        {showEyeToggle ? (
          <Pressable
            onPress={() => setReveal((r) => !r)}
            style={styles.iconRight}
            accessibilityLabel="Mostrar/esconder"
          >
            <Icon name="eye" size={15} color={theme.textMuted} />
          </Pressable>
        ) : trailingIcon ? (
          <Pressable
            onPress={onTrailingPress}
            style={styles.iconRight}
            disabled={!onTrailingPress}
          >
            <Icon name={trailingIcon} size={15} color={theme.textMuted} />
          </Pressable>
        ) : null}
      </View>
      {hint ? <Text style={styles.hint}>{hint}</Text> : null}
    </View>
  );
};

export const SelectInput: React.FC<{
  label?: string;
  value: string;
  placeholder?: string;
  onPress?: () => void;
}> = ({ label, value, placeholder, onPress }) => (
  <View style={styles.wrap}>
    {label ? <Text style={styles.label}>{label}</Text> : null}
    <Pressable style={styles.selectWrap} onPress={onPress} disabled={!onPress}>
      <Text style={[styles.selectValue, !value && styles.selectPlaceholder]}>
        {value || placeholder}
      </Text>
      <Icon name="chevron-down" size={15} color={theme.textMuted} />
    </Pressable>
  </View>
);

const styles = StyleSheet.create({
  wrap: { gap: 6, flexShrink: 1 },
  labelRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  label: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  inputWrap: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radius,
    paddingHorizontal: 12,
    minHeight: 40,
  },
  inputWrapFocused: {
    borderColor: theme.primary,
  },
  inputWrapMulti: {
    alignItems: "flex-start",
    paddingVertical: 10,
  },
  input: {
    flex: 1,
    color: theme.text,
    paddingVertical: 9,
    fontSize: 13,
    fontFamily: theme.fontSans,
    ...(({ outlineStyle: "none" } as unknown) as object),
  },
  iconLeft: {
    marginRight: 8,
  },
  iconRight: {
    marginLeft: 8,
    padding: 4,
  },
  hint: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
    marginTop: 2,
  },
  selectWrap: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radius,
    paddingHorizontal: 12,
    minHeight: 40,
  },
  selectValue: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  selectPlaceholder: {
    color: theme.textSoft,
  },
});
