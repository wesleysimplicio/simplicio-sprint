import {
  DefaultTheme as RNDefaultTheme,
  NavigationContainer,
} from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import type { RunMode } from "./api/types";
import { AuthScreen } from "./screens/AuthScreen";
import { CompanyAdminScreen } from "./screens/CompanyAdminScreen";
import { CompanyHealthScreen } from "./screens/CompanyHealthScreen";
import { ConnectScreen } from "./screens/ConnectScreen";
import { DashboardScreen } from "./screens/DashboardScreen";
import { ManagerScreen } from "./screens/ManagerScreen";
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
  Sprints: undefined;
  SprintDetail: { sprintId: string };
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

export const Navigation: React.FC = () => (
  <NavigationContainer theme={navTheme}>
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
      <Stack.Screen name="Sprints" component={SprintsScreen} />
      <Stack.Screen name="SprintDetail" component={SprintDetailScreen} />
      <Stack.Screen name="Run" component={RunScreen} />
      <Stack.Screen name="Result" component={ResultScreen} />
    </Stack.Navigator>
  </NavigationContainer>
);
