import {
  NavigationContainer,
  DarkTheme as RNDarkTheme,
} from "@react-navigation/native";
import { createNativeStackNavigator } from "@react-navigation/native-stack";
import React from "react";
import { theme } from "./theme";
import { ConnectScreen } from "./screens/ConnectScreen";
import { ProviderScreen } from "./screens/ProviderScreen";
import { AuthScreen } from "./screens/AuthScreen";
import { SprintsScreen } from "./screens/SprintsScreen";
import { SprintDetailScreen } from "./screens/SprintDetailScreen";
import { RunScreen } from "./screens/RunScreen";
import { ResultScreen } from "./screens/ResultScreen";
import type { RunMode } from "./api/types";

export type RootStackParamList = {
  Connect: undefined;
  Provider: undefined;
  Auth: undefined;
  Sprints: undefined;
  SprintDetail: { sprintId: string };
  Run: { sprintId: string; mode: RunMode; itemKeys: string[] };
  Result: { runId: string };
};

const Stack = createNativeStackNavigator<RootStackParamList>();

const navTheme = {
  ...RNDarkTheme,
  colors: {
    ...RNDarkTheme.colors,
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
        headerStyle: { backgroundColor: theme.bg },
        headerTitleStyle: { color: theme.text, fontWeight: "700" },
        headerTintColor: theme.primarySoft,
        contentStyle: { backgroundColor: theme.bg },
      }}
    >
      <Stack.Screen name="Connect" component={ConnectScreen} options={{ title: "SendSprint" }} />
      <Stack.Screen name="Provider" component={ProviderScreen} options={{ title: "Conectar" }} />
      <Stack.Screen name="Auth" component={AuthScreen} options={{ title: "Autenticar" }} />
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
