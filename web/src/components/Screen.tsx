import React from "react";
import {
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
  Pressable,
} from "react-native";
import { useNavigation, useRoute } from "@react-navigation/native";
import { SafeAreaView } from "react-native-safe-area-context";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Props = {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  scroll?: boolean;
  footer?: React.ReactNode;
  chrome?: "app" | "auth";
  eyebrow?: string;
  actions?: React.ReactNode;
};

export const Screen: React.FC<Props> = ({
  title,
  subtitle,
  children,
  scroll = true,
  footer,
  chrome = "app",
  eyebrow,
  actions,
}) => {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { session } = useSession();
  const { width } = useWindowDimensions();
  const Body = scroll ? ScrollView : View;
  const showSidebar = chrome === "app" && Platform.OS === "web" && width >= 1100;
  const compact = Platform.OS === "web" && width < 860;
  const currentRoute = route.name as string;
  const isAuthChrome = chrome === "auth";

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <StatusBar barStyle="dark-content" />
      <View style={styles.bgGlowTop} />
      <View style={styles.bgGlowBottom} />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.flex}>
        <View style={styles.shell}>
          {showSidebar ? (
            <View style={styles.sidebar}>
              <View style={styles.brandBlock}>
                <View style={styles.brandBadge}>
                  <Text style={styles.brandBadgeText}>S</Text>
                </View>
                <View>
                  <Text style={styles.brandName}>SendSprint</Text>
                  <Text style={styles.brandMeta}>Local Delivery Plane</Text>
                </View>
              </View>

              <View style={styles.navStack}>
                {NAV_ITEMS.map((item) => {
                  const active = isRouteActive(item.route, currentRoute);
                  return (
                    <Pressable
                      key={item.label}
                      onPress={() => navigateShellItem(navigation, item.route)}
                      style={({ pressed }) => [
                        styles.navItem,
                        active && styles.navItemActive,
                        pressed && !active && { opacity: 0.82 },
                      ]}
                    >
                      <Text style={[styles.navGlyph, active && styles.navGlyphActive]}>{item.glyph}</Text>
                      <Text style={[styles.navLabel, active && styles.navLabelActive]}>{item.label}</Text>
                    </Pressable>
                  );
                })}
              </View>

              <View style={styles.sidebarFooter}>
                <Text style={styles.sidebarHelp}>Ajuda</Text>
                <View style={styles.operatorCard}>
                  <View style={styles.operatorAvatar}>
                    <Text style={styles.operatorAvatarText}>FS</Text>
                  </View>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.operatorName}>
                      {session.appUser?.displayName ?? session.appUser?.email ?? "Operador local"}
                    </Text>
                    <Text style={styles.operatorMeta}>
                      {session.currentSprint?.sprintName ?? "Shell ativa"}
                    </Text>
                  </View>
                </View>
              </View>
            </View>
          ) : null}

          <View style={[styles.main, isAuthChrome && styles.mainAuth]}>
            <View style={[styles.mainInner, isAuthChrome && styles.mainInnerAuth]}>
              <Body
                style={styles.flex}
                contentContainerStyle={[
                  styles.scroll,
                  isAuthChrome && styles.scrollAuth,
                  compact && styles.scrollCompact,
                ]}
                keyboardShouldPersistTaps="handled"
              >
                {(title || subtitle || eyebrow || actions) ? (
                  <View style={styles.headerBlock}>
                    <View style={{ flex: 1 }}>
                      {eyebrow ? <Text style={styles.eyebrow}>{eyebrow}</Text> : null}
                      {title ? <Text style={styles.title}>{title}</Text> : null}
                      {subtitle ? <Text style={styles.subtitle}>{subtitle}</Text> : null}
                    </View>
                    {actions ? <View style={styles.headerActions}>{actions}</View> : null}
                  </View>
                ) : null}
                {children}
              </Body>
              {footer ? <View style={styles.footer}>{footer}</View> : null}
            </View>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const NAV_ITEMS = [
  { label: "Inicio", glyph: "o", route: "Dashboard" },
  { label: "Conexoes", glyph: "o", route: "Provider" },
  { label: "Sprints", glyph: "o", route: "Sprints" },
  { label: "Backlog", glyph: "o", route: "SprintDetail" },
  { label: "Projetos", glyph: "o", route: "ProjectSetup" },
  { label: "Manager", glyph: "o", route: "Manager" },
  { label: "Saude", glyph: "o", route: "CompanyHealth" },
  { label: "Suporte", glyph: "o", route: "Support" },
  { label: "Reports", glyph: "o", route: "Reports" },
  { label: "Admin", glyph: "o", route: "CompanyAdmin" },
  { label: "Configuracoes", glyph: "o", route: "Settings" },
] as const;

const ROUTE_ALIASES: Record<(typeof NAV_ITEMS)[number]["route"], string[]> = {
  Dashboard: ["Connect", "Dashboard"],
  Provider: ["Provider", "Auth"],
  Sprints: ["Sprints"],
  SprintDetail: ["SprintDetail", "Run", "Result"],
  ProjectSetup: ["ProjectSetup"],
  Manager: ["Manager"],
  CompanyHealth: ["CompanyHealth"],
  Support: ["Support"],
  Reports: ["Reports"],
  CompanyAdmin: ["CompanyAdmin"],
  Settings: ["Settings"],
};

const isRouteActive = (route: (typeof NAV_ITEMS)[number]["route"], currentRoute: string) =>
  ROUTE_ALIASES[route]?.includes(currentRoute) ?? false;

const navigateShellItem = (navigation: any, route: (typeof NAV_ITEMS)[number]["route"]) => {
  if (route === "SprintDetail") {
    const state = navigation.getState?.();
    const sprintId =
      state?.routes?.find((entry: any) => entry.name === "SprintDetail")?.params?.sprintId ?? null;
    if (sprintId) {
      navigation.navigate("SprintDetail", { sprintId });
      return;
    }
    navigation.navigate("Dashboard");
    return;
  }
  navigation.navigate(route);
};

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg },
  flex: { flex: 1 },
  shell: {
    flex: 1,
    flexDirection: "row",
  },
  bgGlowTop: {
    position: "absolute",
    top: -80,
    right: -40,
    width: 320,
    height: 320,
    borderRadius: 999,
    backgroundColor: "rgba(44,107,237,0.10)",
  },
  bgGlowBottom: {
    position: "absolute",
    left: -100,
    bottom: -120,
    width: 340,
    height: 340,
    borderRadius: 999,
    backgroundColor: "rgba(109,200,255,0.10)",
  },
  sidebar: {
    width: 220,
    paddingHorizontal: 18,
    paddingTop: 18,
    paddingBottom: 18,
    borderRightWidth: 1,
    borderRightColor: "rgba(215,228,245,0.9)",
    backgroundColor: "rgba(250,252,255,0.92)",
  },
  brandBlock: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 6,
  },
  brandBadge: {
    width: 34,
    height: 34,
    borderRadius: 10,
    backgroundColor: theme.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  brandBadgeText: {
    color: "#fff",
    fontWeight: "800",
    fontSize: 18,
  },
  brandName: {
    color: theme.text,
    fontSize: 17,
    fontWeight: "800",
  },
  brandMeta: {
    color: theme.textMuted,
    fontSize: 11,
    marginTop: 2,
  },
  navStack: {
    marginTop: 24,
    gap: 4,
  },
  navItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: 12,
  },
  navItemActive: {
    backgroundColor: "rgba(44,107,237,0.10)",
  },
  navGlyph: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "900",
  },
  navGlyphActive: {
    color: theme.primary,
  },
  navLabel: {
    color: theme.textMuted,
    fontSize: 13,
    fontWeight: "700",
  },
  navLabelActive: {
    color: theme.primary,
  },
  sidebarFooter: {
    marginTop: "auto",
    gap: 10,
    paddingHorizontal: 6,
  },
  sidebarHelp: {
    color: theme.textMuted,
    fontSize: 12,
  },
  operatorCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    padding: 10,
    borderRadius: 14,
    backgroundColor: "rgba(255,255,255,0.9)",
    borderWidth: 1,
    borderColor: theme.border,
  },
  operatorAvatar: {
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: theme.surfaceAlt,
    alignItems: "center",
    justifyContent: "center",
  },
  operatorAvatarText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: "800",
  },
  operatorName: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
  },
  operatorMeta: {
    color: theme.textMuted,
    fontSize: 11,
  },
  main: {
    flex: 1,
  },
  mainAuth: {
    alignItems: "center",
    justifyContent: "center",
  },
  mainInner: {
    flex: 1,
  },
  mainInnerAuth: {
    width: "100%",
    maxWidth: 1280,
  },
  scroll: {
    width: "100%",
    maxWidth: 1180,
    alignSelf: "center",
    paddingHorizontal: 24,
    paddingTop: 18,
    paddingBottom: 32,
    gap: 14,
  },
  scrollAuth: {
    maxWidth: 1280,
    paddingTop: 28,
    paddingBottom: 28,
  },
  scrollCompact: {
    paddingHorizontal: 18,
  },
  headerBlock: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 16,
    marginBottom: 2,
  },
  eyebrow: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
    textTransform: "uppercase",
    marginBottom: 8,
  },
  title: {
    color: theme.text,
    fontSize: 34,
    fontWeight: "800",
    letterSpacing: -0.9,
  },
  subtitle: {
    color: theme.textMuted,
    fontSize: 15,
    lineHeight: 22,
    marginTop: 8,
    maxWidth: 760,
  },
  headerActions: {
    alignItems: "flex-end",
  },
  footer: {
    width: "100%",
    maxWidth: 1180,
    alignSelf: "center",
    paddingHorizontal: 24,
    paddingBottom: 18,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: "rgba(215,228,245,0.9)",
    backgroundColor: "rgba(255,255,255,0.78)",
    gap: 10,
  },
});
