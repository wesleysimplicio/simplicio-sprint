import {
  NavigationContainer,
  DefaultTheme as RNDefaultTheme,
} from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { Pressable, StyleSheet, Text } from "react-native";
import { theme } from "./theme";
import { ConnectScreen } from "./screens/ConnectScreen";
import { DashboardScreen } from "./screens/DashboardScreen";
import { ProviderScreen } from "./screens/ProviderScreen";
import { AuthScreen } from "./screens/AuthScreen";
import { ProjectSetupScreen } from "./screens/ProjectSetupScreen";
import { SettingsScreen } from "./screens/SettingsScreen";
import { SprintsScreen } from "./screens/SprintsScreen";
import { SprintDetailScreen } from "./screens/SprintDetailScreen";
import { RunScreen } from "./screens/RunScreen";
import { ResultScreen } from "./screens/ResultScreen";
import type { RunMode } from "./api/types";

export type RootStackParamList = {
  Connect: undefined;
  Dashboard: undefined;
  Provider: undefined;
  Auth: undefined;
  ProjectSetup: undefined;
  Settings: undefined;
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
      screenOptions={({ navigation, route }) => ({
        headerStyle: { backgroundColor: theme.bg },
        headerTitleStyle: { color: theme.text, fontWeight: "700" },
        headerTintColor: theme.primary,
        contentStyle: { backgroundColor: theme.bg },
        headerRight:
          route.name === "ProjectSetup"
            ? undefined
            : () => (
                <Pressable
                  onPress={() => navigation.navigate("ProjectSetup")}
                  style={({ pressed }) => [styles.setupLink, pressed && { opacity: 0.75 }]}
                >
                  <Text style={styles.setupLinkText}>Setup</Text>
                </Pressable>
              ),
      })}
    >
      <Stack.Screen name="Connect" component={ConnectScreen} options={{ title: "SendSprint" }} />
      <Stack.Screen name="Dashboard" component={DashboardScreen} options={{ title: "Dashboard" }} />
      <Stack.Screen name="Provider" component={ProviderScreen} options={{ title: "Conectar" }} />
      <Stack.Screen name="Auth" component={AuthScreen} options={{ title: "Autenticar" }} />
      <Stack.Screen
        name="ProjectSetup"
        component={ProjectSetupScreen}
        options={{ title: "Project setup" }}
      />
      <Stack.Screen name="Settings" component={SettingsScreen} options={{ title: "Configurações" }} />
      <Stack.Screen name="Sprints" component={SprintsScreen} options={{ title: "Sprints ativas" }} />
      <Stack.Screen
        name="SprintDetail"
        component={SprintDetailScreen}
        options={{ title: "Itens da sprint" }}
      />
      <Stack.Screen name="Run" component={RunScreen} options={{ title: "Execução" }} />
      <Stack.Screen name="Result" component={ResultScreen} options={{ title: "Entregue" }} />
    </Stack.Navigator>
  </NavigationContainer>
);

const styles = StyleSheet.create({
  setupLink: {
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 999,
    backgroundColor: theme.surfaceAlt,
    borderWidth: 1,
    borderColor: theme.border,
  },
  setupLinkText: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: "800",
  },
});
