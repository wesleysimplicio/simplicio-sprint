import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage } from "../api/client";
import type { AuthStatus, VersionCheckResponse } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Settings">;
type SettingsTab = "connections" | "models" | "execution" | "updates";

export const SettingsScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session } = useSession();
  const [status, setStatus] = useState<AuthStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [versionCheck, setVersionCheck] = useState<VersionCheckResponse | null>(null);
  const [checkingVersion, setCheckingVersion] = useState(false);
  const [versionError, setVersionError] = useState<string | null>(null);
  const [tab, setTab] = useState<SettingsTab>("connections");

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
      chrome="app"
      eyebrow="Web 12 - Settings / Connections"
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
          <Button title="Trocar provider" variant="secondary" onPress={() => nav.navigate("Provider")} />
          <Button title="Reautenticar" onPress={() => nav.navigate("Auth")} />
        </View>
      }
    >
      <View style={styles.tabRow}>
        {[
          ["connections", "Conexoes"],
          ["models", "Modelos"],
          ["execution", "Execucao"],
          ["updates", "Updates"],
        ].map(([key, label]) => (
          <Pressable
            key={key}
            onPress={() => setTab(key as SettingsTab)}
            style={[styles.tab, tab === key && styles.tabActive]}
          >
            <Text style={[styles.tabText, tab === key && styles.tabTextActive]}>{label}</Text>
          </Pressable>
        ))}
      </View>

      {tab === "connections" ? (
        <>
          <Card>
            <Text style={styles.label}>BACKEND</Text>
            <Text style={styles.value}>{session.backendUrl}</Text>
            {statusError ? <Text style={styles.error}>{statusError}</Text> : null}
          </Card>

          <View style={styles.grid}>
            <Card style={styles.panel}>
              <Text style={styles.label}>AZURE DEVOPS</Text>
              <Text style={styles.value}>{status?.providers.azuredevops.account ?? "nao configurado"}</Text>
              <Text style={styles.meta}>{status?.providers.azuredevops.team_path ?? "sem team path"}</Text>
              <Text style={styles.meta}>{status?.providers.azuredevops.iteration_path ?? "sem iteration path"}</Text>
            </Card>

            <Card style={styles.panel}>
              <Text style={styles.label}>JIRA</Text>
              <Text style={styles.value}>{status?.providers.jira.account ?? "nao configurado"}</Text>
              <Text style={styles.meta}>Provider padrao: {status?.default_provider ?? session.provider ?? "nao definido"}</Text>
            </Card>
          </View>

          <Card>
            <Text style={styles.label}>GITHUB</Text>
            <Text style={styles.value}>
              {status?.providers.github.configured ? "CLI autenticado" : "nao autenticado"}
            </Text>
            <Text style={styles.meta}>
              Exposto na navegacao web; intake completo ainda depende do backend de issues e projects.
            </Text>
          </Card>
        </>
      ) : null}

      {tab === "models" ? (
        <View style={styles.grid}>
          <Card style={styles.panel}>
            <Text style={styles.label}>CHAT E PROVIDERS</Text>
            <Text style={styles.value}>OpenRouter / Claude / Codex / Ollama</Text>
            <Text style={styles.meta}>
              O shell ja reserva esta area para providers gerenciados, chaveamento por tarefa e LLM local.
            </Text>
          </Card>
          <Card style={styles.panel}>
            <Text style={styles.label}>BROWSER FALLBACKS</Text>
            <Text style={styles.value}>Playwright primeiro</Text>
            <Text style={styles.meta}>
              Claude, Codex, Hermes e OpenClaw entram como fallback de captura quando o backend nao resolve sozinho.
            </Text>
          </Card>
        </View>
      ) : null}

      {tab === "execution" ? (
        <View style={styles.grid}>
          <Card style={styles.panel}>
            <Text style={styles.label}>EXECUTION POLICY</Text>
            <Text style={styles.value}>{session.projectSetup.mode}</Text>
            <Text style={styles.meta}>
              Repos locais registrados: {session.projectSetup.repositories.length}
            </Text>
          </Card>
          <Card style={styles.panel}>
            <Text style={styles.label}>WORKSPACE</Text>
            <Text style={styles.value}>{session.currentSprint?.sprintName ?? "Nenhuma sprint ativa"}</Text>
            <Text style={styles.meta}>Usuario atual: {session.appUser?.email ?? "local-operator"}</Text>
          </Card>
        </View>
      ) : null}

      {tab === "updates" ? (
        <Card>
          <Text style={styles.label}>UPDATE SENDSPRINT</Text>
          <Text style={styles.value}>
            {versionCheck
              ? versionCheck.status === "unavailable"
                ? "Nao foi possivel verificar updates agora."
                : versionCheck.update_available
                  ? `Update disponivel: ${versionCheck.latest_version}`
                  : `Atualizado: ${versionCheck.current_version}`
              : "Clique no rodape para verificar a versao publicada no PyPI."}
          </Text>
          {versionCheck ? (
            <Text style={styles.meta}>
              Instalado {versionCheck.current_version}
              {versionCheck.latest_version ? ` | PyPI ${versionCheck.latest_version}` : ""} | {versionCheck.message}
            </Text>
          ) : null}
          {versionError ? <Text style={styles.error}>{versionError}</Text> : null}
        </Card>
      ) : null}
    </Screen>
  );
};

const styles = StyleSheet.create({
  tabRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  tab: {
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surfaceAlt,
  },
  tabActive: {
    backgroundColor: "rgba(44,107,237,0.10)",
    borderColor: "rgba(44,107,237,0.24)",
  },
  tabText: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "700",
  },
  tabTextActive: {
    color: theme.primary,
  },
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  panel: {
    flex: 1,
    minWidth: 300,
  },
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
