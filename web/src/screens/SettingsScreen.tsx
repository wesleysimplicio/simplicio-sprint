import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage } from "../api/client";
import type { AuthStatus, VersionCheckResponse } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Settings">;

export const SettingsScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session } = useSession();
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [versionCheck, setVersionCheck] = useState<VersionCheckResponse | null>(null);
  const [checkingVersion, setCheckingVersion] = useState(false);
  const [versionError, setVersionError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setStatus(await api.authStatus());
        setStatusError(null);
      } catch (error) {
        setStatusError(getApiErrorMessage(error));
      }
    })();
  }, [api]);

  const checkForUpdates = async () => {
    setCheckingVersion(true);
    setVersionError(null);
    setVersionCheck(null);
    try {
      setVersionCheck(await api.checkVersion());
    } catch (error) {
      setVersionError(getApiErrorMessage(error));
    } finally {
      setCheckingVersion(false);
    }
  };

  return (
    <Screen
      title="Configuracoes"
      subtitle="Parametros locais, backend conectado e contexto persistido do CLI."
      footer={
        <View style={{ gap: 10 }}>
          <Button
            title="Verificar update SendSprint"
            variant="secondary"
            onPress={checkForUpdates}
            loading={checkingVersion}
          />
          <Button
            title="Trocar provider"
            variant="secondary"
            onPress={() => nav.navigate("Provider")}
          />
          <Button title="Reautenticar" onPress={() => nav.navigate("Auth")} />
        </View>
      }
    >
      <Card>
        <Text style={styles.label}>BACKEND</Text>
        <Text style={styles.value}>{session.backendUrl}</Text>
        {statusError ? <Text style={styles.error}>{statusError}</Text> : null}
      </Card>

      <Card>
        <Text style={styles.label}>UPDATE SENDSPRINT</Text>
        <Text style={styles.value}>
          {versionCheck
            ? versionCheck.status === "unavailable"
              ? "Nao foi possivel verificar updates agora."
              : versionCheck.update_available
              ? `Update disponivel: ${versionCheck.latest_version}`
              : `Atualizado: ${versionCheck.current_version}`
            : "Clique para verificar a versao publicada no PyPI."}
        </Text>
        {versionCheck ? (
          <Text style={styles.meta}>
            Instalado {versionCheck.current_version}
            {versionCheck.latest_version ? ` | PyPI ${versionCheck.latest_version}` : ""} |{" "}
            {versionCheck.message}
          </Text>
        ) : null}
        {versionError ? <Text style={styles.error}>{versionError}</Text> : null}
      </Card>

      <Card>
        <Text style={styles.label}>PROVIDER PADRAO</Text>
        <Text style={styles.value}>{status?.default_provider ?? session.provider ?? "nao definido"}</Text>
      </Card>

      <Card>
        <Text style={styles.label}>AZURE DEVOPS</Text>
        <Text style={styles.value}>
          {status?.providers.azuredevops.account ?? "nao configurado"}
        </Text>
        <Text style={styles.meta}>{status?.providers.azuredevops.team_path ?? "sem team path"}</Text>
        <Text style={styles.meta}>
          {status?.providers.azuredevops.iteration_path ?? "sem iteration path"}
        </Text>
      </Card>

      <Card>
        <Text style={styles.label}>JIRA</Text>
        <Text style={styles.value}>{status?.providers.jira.account ?? "nao configurado"}</Text>
      </Card>

      <Card>
        <Text style={styles.label}>GITHUB</Text>
        <Text style={styles.value}>
          {status?.providers.github.configured ? "CLI autenticado" : "nao autenticado"}
        </Text>
        <Text style={styles.meta}>
          Exposto na navegacao web; intake completo ainda depende do backend de
          issues/projects.
        </Text>
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
  error: {
    color: theme.danger,
    fontSize: 12,
    marginTop: 6,
    lineHeight: 18,
  },
});
