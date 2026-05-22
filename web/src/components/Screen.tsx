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
import { Icon, type IconName } from "./Icon";

export type ChromeKind = "auth" | "app" | "manager";

type Props = {
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  scroll?: boolean;
  footer?: React.ReactNode;
  chrome?: ChromeKind;
  eyebrow?: string;
  actions?: React.ReactNode;
  contentMaxWidth?: number;
  contentPadding?: boolean;
};

type NavItem = {
  label: string;
  icon: IconName;
  route: string;
  aliases?: string[];
};

const OPERATOR_NAV: NavItem[] = [
  { label: "Início", icon: "home", route: "Dashboard", aliases: ["Connect", "Dashboard"] },
  { label: "Sprints", icon: "sprint", route: "Sprints", aliases: ["Sprints"] },
  { label: "Execuções", icon: "play", route: "Dashboard", aliases: ["Run", "Result"] },
  { label: "Backlog", icon: "kanban", route: "SprintDetail", aliases: ["SprintDetail"] },
  { label: "Projetos", icon: "folder", route: "ProjectSetup", aliases: ["ProjectSetup"] },
  { label: "Conexões", icon: "link", route: "Provider", aliases: ["Provider", "Auth"] },
  { label: "Modelos", icon: "model", route: "Settings", aliases: [] },
  { label: "Configurações", icon: "settings", route: "Settings", aliases: ["Settings"] },
];

const MANAGER_NAV: NavItem[] = [
  { label: "Visão geral", icon: "home", route: "CompanyHealth", aliases: ["CompanyHealth"] },
  { label: "Operações", icon: "sliders", route: "Manager", aliases: ["Manager"] },
  { label: "Projetos", icon: "folder", route: "ProjectSetup", aliases: ["ProjectSetup"] },
  { label: "Backlog", icon: "kanban", route: "SprintDetail", aliases: ["SprintDetail"] },
  { label: "Execuções", icon: "play", route: "Dashboard", aliases: ["Dashboard", "Run", "Result"] },
  { label: "Pessoas", icon: "users", route: "CompanyAdmin", aliases: [] },
  { label: "Relatórios", icon: "chart", route: "Reports", aliases: ["Reports"] },
  { label: "Portfólio", icon: "pie", route: "Portfolio", aliases: ["Portfolio"] },
  { label: "Suporte", icon: "headset", route: "Support", aliases: ["Support"] },
  { label: "Admin", icon: "shield", route: "CompanyAdmin", aliases: ["CompanyAdmin"] },
  { label: "Configurações", icon: "settings", route: "Settings", aliases: ["Settings"] },
];

export const Screen: React.FC<Props> = ({
  title,
  subtitle,
  children,
  scroll = true,
  footer,
  chrome = "app",
  eyebrow,
  actions,
  contentMaxWidth = 1280,
  contentPadding = true,
}) => {
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { session, setAppUser, setOperatorToken } = useSession();
  const { width } = useWindowDimensions();
  const Body = scroll ? ScrollView : View;
  const isWeb = Platform.OS === "web";
  const showSidebar = chrome !== "auth" && isWeb && width >= 1024;
  const compact = isWeb && width < 760;
  const currentRoute = route.name as string;
  const isAuthChrome = chrome === "auth";
  const navItems = chrome === "manager" ? MANAGER_NAV : OPERATOR_NAV;
  const showInlineHeader = Boolean(title || subtitle || eyebrow || actions);

  const bodyStyle = scroll
    ? styles.flex
    : [styles.flex, styles.scroll, compact && styles.scrollCompact];
  const bodyContentStyle = scroll
    ? [
        styles.scroll,
        { maxWidth: contentMaxWidth },
        !contentPadding && styles.scrollNoPad,
        compact && styles.scrollCompact,
      ]
    : undefined;

  const handleLogout = async () => {
    await setOperatorToken(null);
    await setAppUser(null);
    navigation.dispatch(
      CommonActions.reset({ index: 0, routes: [{ name: "Connect" }] }),
    );
  };

  const profileName =
    chrome === "manager"
      ? session.appUser?.displayName ?? "Fernanda Silva"
      : session.appUser?.displayName ?? session.appUser?.email ?? "Fernando Silva";
  const profileRole = chrome === "manager" ? "Gestora" : "Admin";

  return (
    <SafeAreaView style={styles.safe} edges={["top", "bottom"]}>
      <StatusBar barStyle="dark-content" />
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : undefined}
        style={styles.flex}
      >
        {isAuthChrome ? (
          <View style={styles.authShell}>
            <View style={styles.authInner}>{children}</View>
          </View>
        ) : (
          <View style={styles.shell}>
            {showSidebar ? (
              <Sidebar
                items={navItems}
                currentRoute={currentRoute}
                onNavigate={(target) => navigateShellItem(navigation, target)}
                profileName={profileName}
                profileRole={profileRole}
                onLogout={() => void handleLogout()}
              />
            ) : null}

            <View style={styles.main}>
              {showSidebar ? <TopBar /> : null}

              <Body
                style={bodyStyle}
                contentContainerStyle={bodyContentStyle}
                keyboardShouldPersistTaps="handled"
                showsVerticalScrollIndicator={false}
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
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
};

const TopBar: React.FC = () => (
  <View style={styles.topBar}>
    <View style={{ flex: 1 }} />
    <View style={styles.topBarRight}>
      <Pressable style={styles.iconButton}>
        <Icon name="bell" size={16} color={theme.textMuted} />
      </Pressable>
      <View style={styles.topAvatar}>
        <Icon name="user" size={14} color={theme.primary} />
      </View>
    </View>
  </View>
);

const Sidebar: React.FC<{
  items: NavItem[];
  currentRoute: string;
  onNavigate: (route: string) => void;
  profileName: string;
  profileRole: string;
  onLogout: () => void;
}> = ({ items, currentRoute, onNavigate, profileName, profileRole, onLogout }) => (
  <View style={styles.sidebar}>
    <View style={styles.brandBlock}>
      <View style={styles.brandBadge}>
        <Icon name="logo" size={18} color="#fff" />
      </View>
      <Text style={styles.brandName}>SendSprint</Text>
    </View>

    <View style={styles.navStack}>
      {items.map((item) => {
        const active =
          item.aliases?.includes(currentRoute) ?? currentRoute === item.route;
        return (
          <Pressable
            key={item.label}
            onPress={() => onNavigate(item.route)}
            style={({ pressed }) => [
              styles.navItem,
              active && styles.navItemActive,
              pressed && !active && { opacity: 0.78 },
            ]}
          >
            <Icon
              name={item.icon}
              size={16}
              color={active ? theme.primary : theme.textMuted}
            />
            <Text style={[styles.navLabel, active && styles.navLabelActive]}>
              {item.label}
            </Text>
          </Pressable>
        );
      })}
    </View>

    <View style={styles.sidebarFooter}>
      <Pressable style={styles.helpItem}>
        <Icon name="help" size={16} color={theme.textMuted} />
        <Text style={styles.helpLabel}>Ajuda</Text>
      </Pressable>

      <View style={styles.operatorCard}>
        <View style={styles.operatorAvatar}>
          <Text style={styles.operatorAvatarText}>{initials(profileName)}</Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={styles.operatorName} numberOfLines={1}>
            {profileName}
          </Text>
          <Text style={styles.operatorMeta} numberOfLines={1}>
            {profileRole}
          </Text>
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Sair"
          testID="logout-button"
          onPress={onLogout}
          style={styles.logoutIconButton}
        >
          <Icon name="external" size={13} color={theme.textMuted} />
        </Pressable>
      </View>
    </View>
  </View>
);

const ROUTE_GUARDS: Record<string, string> = {
  SprintDetail: "Dashboard",
};

const navigateShellItem = (navigation: any, route: string) => {
  if (route === "SprintDetail") {
    const state = navigation.getState?.();
    const sprintId =
      state?.routes?.find((entry: any) => entry.name === "SprintDetail")?.params
        ?.sprintId ?? null;
    if (sprintId) {
      navigation.navigate("SprintDetail", { sprintId });
      return;
    }
    navigation.navigate(ROUTE_GUARDS.SprintDetail);
    return;
  }
  navigation.navigate(route);
};

const initials = (value?: string | null): string => {
  if (!value) return "FS";
  const parts = value.replace(/@.*/, "").split(/[.\s_-]+/).filter(Boolean);
  return (
    (parts[0]?.[0] ?? "F").toUpperCase() + (parts[1]?.[0] ?? "S").toUpperCase()
  );
};

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: theme.bg },
  flex: { flex: 1 },
  shell: {
    flex: 1,
    flexDirection: "row",
  },
  authShell: {
    flex: 1,
    backgroundColor: theme.bg,
    alignItems: "center",
    justifyContent: "center",
    padding: 20,
  },
  authInner: {
    width: "100%",
    maxWidth: 1200,
  },
  sidebar: {
    width: 220,
    paddingHorizontal: 14,
    paddingTop: 24,
    paddingBottom: 18,
    borderRightWidth: 1,
    borderRightColor: theme.border,
    backgroundColor: theme.surface,
  },
  brandBlock: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 4,
    marginBottom: 28,
  },
  brandBadge: {
    width: 32,
    height: 32,
    borderRadius: 9,
    backgroundColor: theme.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  brandName: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "800",
    fontFamily: theme.fontSans,
    letterSpacing: -0.2,
  },
  navStack: {
    gap: 2,
  },
  navItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 10,
    paddingVertical: 9,
    borderRadius: 8,
  },
  navItemActive: {
    backgroundColor: theme.primaryFaint,
  },
  navLabel: {
    color: theme.textMuted,
    fontSize: 13,
    fontWeight: "500",
    fontFamily: theme.fontSans,
  },
  navLabelActive: {
    color: theme.primary,
    fontWeight: "600",
  },
  sidebarFooter: {
    marginTop: "auto",
    gap: 12,
  },
  helpItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  helpLabel: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  operatorCard: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    paddingHorizontal: 8,
    paddingVertical: 8,
  },
  operatorAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: theme.primaryFaint,
    alignItems: "center",
    justifyContent: "center",
  },
  operatorAvatarText: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: "800",
    fontFamily: theme.fontSans,
  },
  operatorName: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  operatorMeta: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
    marginTop: 1,
  },
  logoutIconButton: {
    width: 26,
    height: 26,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 6,
  },
  main: {
    flex: 1,
    backgroundColor: theme.bg,
  },
  topBar: {
    minHeight: 56,
    paddingHorizontal: 22,
    flexDirection: "row",
    alignItems: "center",
    borderBottomWidth: 1,
    borderBottomColor: theme.border,
    backgroundColor: theme.surface,
  },
  topBarRight: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  iconButton: {
    width: 32,
    height: 32,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
  },
  topAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: theme.primaryFaint,
    alignItems: "center",
    justifyContent: "center",
  },
  scroll: {
    width: "100%",
    alignSelf: "center",
    paddingHorizontal: 28,
    paddingTop: 24,
    paddingBottom: 32,
    gap: 16,
  },
  scrollNoPad: {
    paddingHorizontal: 0,
    paddingTop: 0,
    paddingBottom: 0,
  },
  scrollCompact: {
    paddingHorizontal: 14,
  },
  headerBlock: {
    flexDirection: "row",
    alignItems: "flex-start",
    justifyContent: "space-between",
    gap: 18,
    marginBottom: 6,
  },
  eyebrow: {
    color: theme.primary,
    fontSize: 10,
    letterSpacing: 1.4,
    fontWeight: "800",
    textTransform: "uppercase",
    marginBottom: 6,
    fontFamily: theme.fontSans,
  },
  title: {
    color: theme.text,
    fontSize: 22,
    fontWeight: "800",
    fontFamily: theme.fontSans,
    letterSpacing: -0.3,
  },
  subtitle: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 6,
    maxWidth: 760,
    fontFamily: theme.fontSans,
  },
  headerActions: {
    alignItems: "flex-end",
  },
  footer: {
    width: "100%",
    alignSelf: "center",
    paddingHorizontal: 28,
    paddingBottom: 18,
    paddingTop: 14,
    borderTopWidth: 1,
    borderTopColor: theme.border,
    backgroundColor: theme.surface,
    alignItems: "flex-end",
    gap: 8,
  },
});
