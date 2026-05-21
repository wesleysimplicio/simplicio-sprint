import React from "react";
import {
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StatusBar,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import { CommonActions, useNavigation, useRoute } from "@react-navigation/native";
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
  const { session, setAppUser, setOperatorToken } = useSession();
  const { width } = useWindowDimensions();
  const Body = scroll ? ScrollView : View;
  const showSidebar = chrome === "app" && Platform.OS === "web" && width >= 1100;
  const compact = Platform.OS === "web" && width < 860;
  const currentRoute = route.name as string;
  const isAuthChrome = chrome === "auth";
  const showInlineHeader = Boolean(title || subtitle || eyebrow || actions);
  const bodyStyle = scroll
    ? styles.flex
    : [
        styles.flex,
        styles.scroll,
        isAuthChrome && styles.scrollAuth,
        compact && styles.scrollCompact,
      ];
  const bodyContentStyle = scroll
    ? [
        styles.scroll,
        isAuthChrome && styles.scrollAuth,
        compact && styles.scrollCompact,
      ]
    : undefined;

  const handleLogout = async () => {
    await setOperatorToken(null);
    await setAppUser(null);
    navigation.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: "Connect" }],
      }),
    );
  };

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <StatusBar barStyle="dark-content" />
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.flex}>
        <View style={styles.shell}>
          {showSidebar ? (
            <View style={styles.sidebar}>
              <View style={styles.brandBlock}>
                <View style={styles.brandBadge}>
                  <Text style={styles.brandBadgeText}>S</Text>
                </View>
                <View style={{ flex: 1 }}>
                  <Text style={styles.brandName} numberOfLines={1}>SendSprint</Text>
                  <Text style={styles.brandMeta} numberOfLines={1}>AI Sprint Delivery</Text>
                </View>
              </View>

              <View style={styles.navStack}>
                {NAV_ITEMS.map((item) => {
                  const active = isRouteActive(item.route, currentRoute);
                  return (
                    <Pressable
                      key={`${item.route}-${item.label}`}
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
                    <Text style={styles.operatorAvatarText}>{initials(session.appUser?.displayName ?? session.appUser?.email)}</Text>
                  </View>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={styles.operatorName} numberOfLines={1}>
                      {session.appUser?.displayName ?? session.appUser?.email ?? "Operador local"}
                    </Text>
                    <Text style={styles.operatorMeta} numberOfLines={1}>
                      {session.currentSprint?.sprintName ?? "Shell ativa"}
                    </Text>
                  </View>
                </View>
                <Pressable
                  testID="logout-button"
                  accessibilityRole="button"
                  accessibilityLabel="Sair"
                  onPress={() => void handleLogout()}
                  style={({ pressed }) => [styles.logoutButton, pressed && { opacity: 0.78 }]}
                >
                  <Text style={styles.logoutText}>Sair</Text>
                </Pressable>
              </View>
            </View>
          ) : null}

          <View style={[styles.main, isAuthChrome && styles.mainAuth]}>
            {!isAuthChrome && showSidebar ? (
              <View style={styles.topBar}>
                <View style={styles.topBarLeft}>
                  <Text style={styles.topBarTitle} numberOfLines={1}>SendSprint workspace</Text>
                  <Text style={styles.topBarSubtitle} numberOfLines={1}>Control plane local</Text>
                </View>
                <View style={styles.topBarRight}>
                  <View style={styles.statusDot} />
                  <Text style={styles.topBarMeta}>Atualizado agora</Text>
                  <View style={styles.bellCircle}>
                    <Text style={styles.bellText}>!</Text>
                  </View>
                </View>
              </View>
            ) : null}

            <View style={[styles.mainInner, isAuthChrome && styles.mainInnerAuth]}>
              <Body
                style={bodyStyle}
                contentContainerStyle={bodyContentStyle}
                keyboardShouldPersistTaps="handled"
              >
                {showInlineHeader ? (
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
  { label: "Inicio", glyph: "H", route: "Dashboard" },
  { label: "Sprints", glyph: "S", route: "Sprints" },
  { label: "Execucoes", glyph: "R", route: "Dashboard" },
  { label: "Backlog", glyph: "B", route: "SprintDetail" },
  { label: "Projetos", glyph: "P", route: "ProjectSetup" },
  { label: "Conexoes", glyph: "C", route: "Provider" },
  { label: "Modelos IA", glyph: "M", route: "Settings" },
  { label: "Manager", glyph: "G", route: "Manager" },
  { label: "Saude", glyph: "+", route: "CompanyHealth" },
  { label: "Portfolio", glyph: "F", route: "Portfolio" },
  { label: "Suporte", glyph: "?", route: "Support" },
  { label: "Reports", glyph: "A", route: "Reports" },
  { label: "Admin", glyph: "K", route: "CompanyAdmin" },
  { label: "Configuracoes", glyph: "*", route: "Settings" },
] as const;

const ROUTE_ALIASES: Record<(typeof NAV_ITEMS)[number]["route"], string[]> = {
  Dashboard: ["Connect", "Dashboard"],
  Provider: ["Provider", "Auth"],
  Sprints: ["Sprints"],
  SprintDetail: ["SprintDetail", "Run", "Result"],
  ProjectSetup: ["ProjectSetup"],
  Manager: ["Manager"],
  CompanyHealth: ["CompanyHealth"],
  Portfolio: ["Portfolio"],
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

const initials = (value?: string | null): string => {
  if (!value) return "FS";
  const parts = value.replace(/@.*/, "").split(/[.\s_-]+/).filter(Boolean);
  return (parts[0]?.[0] ?? "F").toUpperCase() + (parts[1]?.[0] ?? "S").toUpperCase();
};

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg },
  flex: { flex: 1 },
  shell: {
    flex: 1,
    flexDirection: "row",
  },
  sidebar: {
    width: 176,
    paddingHorizontal: 14,
    paddingTop: 20,
    paddingBottom: 14,
    borderRightWidth: 1,
    borderRightColor: theme.border,
    backgroundColor: "#ffffff",
  },
  brandBlock: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 0,
  },
  brandBadge: {
    width: 32,
    height: 32,
    borderRadius: 9,
    backgroundColor: theme.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  brandBadgeText: {
    color: "#fff",
    fontWeight: "800",
    fontSize: 16,
    fontFamily: theme.fontSans,
  },
  brandName: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  brandMeta: {
    color: theme.textMuted,
    fontSize: 10,
    marginTop: 1,
    fontFamily: theme.fontSans,
  },
  navStack: {
    marginTop: 34,
    gap: 5,
  },
  navItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 10,
    paddingVertical: 9,
    borderRadius: 8,
  },
  navItemActive: {
    backgroundColor: "rgba(0,94,232,0.08)",
  },
  navGlyph: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "900",
    letterSpacing: 0,
    width: 16,
    textAlign: "center",
    fontFamily: theme.fontSans,
  },
  navGlyphActive: {
    color: theme.primary,
  },
  navLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  navLabelActive: {
    color: theme.primary,
  },
  sidebarFooter: {
    marginTop: "auto",
    gap: 10,
    paddingHorizontal: 0,
  },
  sidebarHelp: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  operatorCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    padding: 9,
    borderRadius: 8,
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  operatorAvatar: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#e8f1ff",
    alignItems: "center",
    justifyContent: "center",
  },
  operatorAvatarText: {
    color: theme.primary,
    fontSize: 10,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  operatorName: {
    color: theme.text,
    fontSize: 11,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  operatorMeta: {
    color: theme.textMuted,
    fontSize: 10,
    fontFamily: theme.fontSans,
  },
  logoutButton: {
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(0,94,232,0.18)",
    backgroundColor: "rgba(0,94,232,0.06)",
    paddingVertical: 8,
  },
  logoutText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: "800",
    fontFamily: theme.fontSans,
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
  topBar: {
    minHeight: 58,
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
    backgroundColor: "#ffffff",
    paddingHorizontal: 22,
    paddingVertical: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 14,
  },
  topBarLeft: {
    flex: 1,
    minWidth: 0,
  },
  topBarTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  topBarSubtitle: {
    color: theme.textMuted,
    fontSize: 11,
    marginTop: 2,
    fontFamily: theme.fontSans,
  },
  topBarRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: theme.success,
  },
  topBarMeta: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  bellCircle: {
    width: 24,
    height: 24,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: theme.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.surface,
  },
  bellText: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  scroll: {
    width: "100%",
    maxWidth: 1440,
    alignSelf: "center",
    paddingHorizontal: 24,
    paddingTop: 22,
    paddingBottom: 22,
    gap: 14,
  },
  scrollAuth: {
    maxWidth: 1280,
    paddingTop: 22,
    paddingBottom: 22,
  },
  scrollCompact: {
    paddingHorizontal: 12,
  },
  headerBlock: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 18,
    marginBottom: 2,
  },
  eyebrow: {
    color: theme.primary,
    fontSize: 10,
    letterSpacing: 1.6,
    fontWeight: "800",
    textTransform: "uppercase",
    marginBottom: 6,
    fontFamily: theme.fontSans,
  },
  title: {
    color: theme.text,
    fontSize: 24,
    fontWeight: "800",
    letterSpacing: 0,
    fontFamily: theme.fontSans,
  },
  subtitle: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 5,
    maxWidth: 760,
    fontFamily: theme.fontSans,
  },
  headerActions: {
    alignItems: "flex-end",
  },
  footer: {
    width: "100%",
    maxWidth: 1440,
    alignSelf: "center",
    paddingHorizontal: 24,
    paddingBottom: 12,
    paddingTop: 10,
    borderTopWidth: 1,
    borderTopColor: theme.border,
    backgroundColor: "#ffffff",
    alignItems: "flex-end",
    gap: 8,
  },
});
