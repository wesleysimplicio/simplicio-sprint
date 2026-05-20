import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { AuthStatus } from "../api/types";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Settings">;

export const SettingsScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session } = useSession();
  const [status, setStatus] = useState<AuthStatus | null>(null);

  useEffect(() => {
    (async () => {
      setStatus(await api.authStatus());
    })();
  }, []);

  return (
    <Screen
      title="Configurações"
      subtitle="Parâmetros locais, backend conectado e contexto persistido do CLI."
      footer={
        <View style={{ gap: 10 }}>
          <Button title="Trocar provider" variant="secondary" onPress={() => nav.navigate("Provider")} />
          <Button title="Reautenticar" onPress={() => nav.navigate("Auth")} />
        </View>
      }
    >
      <Card>
        <Text style={styles.label}>BACKEND</Text>
        <Text style={styles.value}>{session.backendUrl}</Text>
      </Card>

      <Card>
        <Text style={styles.label}>PROVIDER PADRÃO</Text>
        <Text style={styles.value}>{status?.default_provider ?? session.provider ?? "não definido"}</Text>
      </Card>

      <Card>
        <Text style={styles.label}>AZURE DEVOPS</Text>
        <Text style={styles.value}>{status?.providers.azuredevops.account ?? "não configurado"}</Text>
        <Text style={styles.meta}>{status?.providers.azuredevops.team_path ?? "sem team path"}</Text>
        <Text style={styles.meta}>{status?.providers.azuredevops.iteration_path ?? "sem iteration path"}</Text>
      </Card>

      <Card>
        <Text style={styles.label}>JIRA</Text>
        <Text style={styles.value}>{status?.providers.jira.account ?? "não configurado"}</Text>
      </Card>

      <Card>
        <Text style={styles.label}>GITHUB</Text>
        <Text style={styles.value}>{status?.providers.github.configured ? "CLI autenticado" : "não autenticado"}</Text>
        <Text style={styles.meta}>Exposto na navegação web; intake completo ainda depende do backend de issues/projects.</Text>
      </Card>
    </Screen>
  );
};

const styles = StyleSheet.create({
  label: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  value: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "700",
    marginTop: 8,
  },
  meta: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 4,
    lineHeight: 18,
  },
});
