import {
  DefaultTheme as RNDefaultTheme,
  type InitialState,
  NavigationContainer,
} from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { Platform } from "react-native";
import type { RunMode } from "./api/types";
import { AuthScreen } from "./screens/AuthScreen";
import { CompanyAdminScreen } from "./screens/CompanyAdminScreen";
import { CompanyHealthScreen } from "./screens/CompanyHealthScreen";
import { ConnectScreen } from "./screens/ConnectScreen";
import { DashboardScreen } from "./screens/DashboardScreen";
import { ManagerScreen } from "./screens/ManagerScreen";
import { PortfolioScreen } from "./screens/PortfolioScreen";
import { ProjectSetupScreen } from "./screens/ProjectSetupScreen";
import { ProviderScreen } from "./screens/ProviderScreen";
import { ReportsScreen } from "./screens/ReportsScreen";
import { ResultScreen } from "./screens/ResultScreen";
import { RunScreen } from "./screens/RunScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { SprintDetailScreen } from "./screens/SprintDetailScreen";
import { SprintsScreen } from "./screens/SprintsScreen";
import { SupportCenterScreen } from "./screens/SupportCenterScreen";
import { theme } from "./theme";

export type RootStackParamList = {
  Connect: undefined;
  Dashboard: undefined;
  Provider: undefined;
  Auth: undefined;
  ProjectSetup: undefined;
  Settings: undefined;
  Manager: undefined;
  CompanyHealth: undefined;
  Support: undefined;
  Reports: undefined;
  CompanyAdmin: undefined;
  Portfolio: undefined;
  Sprints: undefined;
  SprintDetail: { sprintId: string; openItemKey?: string | null; detailTab?: string | null };
  Run: { sprintId: string; mode: RunMode; itemKeys: string[] };
  Result: { runId: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

const navTheme = {
  ...RNDefaultTheme,
  colors: {
    ...RNDefaultTheme.colors,
    background: theme.bg,
    card: theme.bg,
    text: theme.text,
    border: theme.border,
    primary: theme.primary,
  },
};

const SIMPLE_SCREENS: Array<keyof RootStackParamList> = [
  "Connect",
  "Dashboard",
  "Provider",
  "Auth",
  "ProjectSetup",
  "Settings",
  "Manager",
  "CompanyHealth",
  "Support",
  "Reports",
  "CompanyAdmin",
  "Portfolio",
  "Sprints",
];

const parseMode = (value: string | null): RunMode =>
  value === "all" || value === "mine" || value === "selected" ? value : "selected";

const buildInitialStateFromLocation = (): InitialState | undefined => {
  if (Platform.OS !== "web" || typeof window === "undefined") return undefined;
  const params = new URLSearchParams(window.location.search);
  const screen = params.get("screen");
  if (!screen) return undefined;

  if ((SIMPLE_SCREENS as string[]).includes(screen)) {
    return {
      routes: [{ name: screen as keyof RootStackParamList }],
    } as InitialState;
  }

  if (screen === "SprintDetail") {
    return {
      routes: [
        {
          name: "SprintDetail",
          params: {
            sprintId: params.get("sprintId") ?? "mock-sprint",
            openItemKey: params.get("openItemKey"),
            detailTab: params.get("detailTab"),
          },
        },
      ],
    } as InitialState;
  }

  if (screen === "Run") {
    return {
      routes: [
        {
          name: "Run",
          params: {
            sprintId: params.get("sprintId") ?? "mock-sprint",
            mode: parseMode(params.get("mode")),
            itemKeys: (params.get("itemKeys") ?? "")
              .split(",")
              .map((item) => item.trim())
              .filter(Boolean),
          },
        },
      ],
    } as InitialState;
  }

  if (screen === "Result") {
    return {
      routes: [
        {
          name: "Result",
          params: {
            runId: params.get("runId") ?? "mock-run",
          },
        },
      ],
    } as InitialState;
  }

  return undefined;
};

export const Navigation: React.FC = () => {
  const initialState = React.useMemo(buildInitialStateFromLocation, []);

  return (
  <NavigationContainer theme={navTheme} initialState={initialState}>
    <Stack.Navigator
      initialRouteName="Connect"
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: theme.bg },
      }}
    >
      <Stack.Screen name="Connect" component={ConnectScreen} />
      <Stack.Screen name="Dashboard" component={DashboardScreen} />
      <Stack.Screen name="Provider" component={ProviderScreen} />
      <Stack.Screen name="Auth" component={AuthScreen} />
      <Stack.Screen name="ProjectSetup" component={ProjectSetupScreen} />
      <Stack.Screen name="Settings" component={SettingsScreen} />
      <Stack.Screen name="Manager" component={ManagerScreen} />
      <Stack.Screen name="CompanyHealth" component={CompanyHealthScreen} />
      <Stack.Screen name="Support" component={SupportCenterScreen} />
      <Stack.Screen name="Reports" component={ReportsScreen} />
      <Stack.Screen name="CompanyAdmin" component={CompanyAdminScreen} />
      <Stack.Screen name="Portfolio" component={PortfolioScreen} />
      <Stack.Screen name="Sprints" component={SprintsScreen} />
      <Stack.Screen name="SprintDetail" component={SprintDetailScreen} />
      <Stack.Screen name="Run" component={RunScreen} />
      <Stack.Screen name="Result" component={ResultScreen} />
    </Stack.Navigator>
  </NavigationContainer>
  );
};
