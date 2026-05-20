import React from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { theme } from "../theme";

type Props = {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  scroll?: boolean;
  footer?: React.ReactNode;
};

export const Screen: React.FC<Props> = ({
  title,
  subtitle,
  children,
  scroll = true,
  footer,
}) => {
  const Body = scroll ? ScrollView : View;
  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <StatusBar barStyle="dark-content" />
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.flex}
      >
        <Body
          style={styles.flex}
          contentContainerStyle={scroll ? styles.scroll : undefined}
          keyboardShouldPersistTaps="handled"
        >
          {title ? <Text style={styles.title}>{title}</Text> : null}
          {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
          <View style={{ height: 12 }} />
          {children}
        </Body>
        {footer ? <View style={styles.footer}>{footer}</View> : null}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg },
  flex: { flex: 1 },
  scroll: {
    paddingHorizontal: 20,
    paddingTop: 8,
    paddingBottom: 32,
    gap: 14,
  },
  title: {
    color: theme.text,
    fontSize: 30,
    fontWeight: "800",
    letterSpacing: -0.5,
  },
  subtitle: {
    color: theme.textMuted,
    fontSize: 15,
    lineHeight: 22,
  },
  footer: {
    paddingHorizontal: 20,
    paddingBottom: 16,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: theme.border,
    backgroundColor: "rgba(255,255,255,0.92)",
    gap: 10,
  },
});
