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
          <Card style={styles.tableCard}>
            <View style={styles.tableHeader}>
              <Text style={styles.label}>PROVIDERS CONECTADOS</Text>
              <Button title="+ Adicionar conexao" onPress={() => nav.navigate("Provider")} />
            </View>
            <ConnectionRow
              provider="Jira"
              account={status?.providers.jira.account ?? "suaempresa.atlassian.net"}
              status={status?.providers.jira.configured ? "Conectado" : "Pendente"}
              onTest={() => nav.navigate("Auth")}
            />
            <ConnectionRow
              provider="Azure DevOps"
              account={status?.providers.azuredevops.account ?? "dev.azure.com/sua-organizacao"}
              status={status?.providers.azuredevops.configured ? "Conectado" : "Pendente"}
              onTest={() => nav.navigate("Auth")}
            />
            <ConnectionRow
              provider="GitHub"
              account={status?.providers.github.configured ? "github.com/autenticado" : "github.com/suaempresa"}
              status={status?.providers.github.configured ? "Conectado" : "Pendente"}
              onTest={() => nav.navigate("Provider")}
            />
            {statusError ? <Text style={styles.error}>{statusError}</Text> : null}
          </Card>

          <Card style={styles.tableCard}>
            <Text style={styles.label}>MODELOS DE IA</Text>
            <ModelRow name="Modelo padrao" provider="OpenAI" context="128k" status="Ativo" />
            <ModelRow name="Modelo secundario" provider="Anthropic" context="200k" status="Standby" />
            <Text style={styles.meta}>Backend: {session.backendUrl}</Text>
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

const ConnectionRow: React.FC<{
  provider: string;
  account: string;
  status: string;
  onTest: () => void;
}> = ({ provider, account, status, onTest }) => (
  <View style={styles.tableRow}>
    <Text style={styles.tableProvider}>{provider}</Text>
    <Text style={styles.tableAccount} numberOfLines={1}>{account}</Text>
    <View style={styles.statusCell}>
      <View style={[styles.statusDot, status !== "Conectado" && styles.statusDotPending]} />
      <Text style={[styles.statusText, status !== "Conectado" && styles.statusTextPending]}>{status}</Text>
    </View>
    <Pressable onPress={onTest} style={styles.rowAction}>
      <Text style={styles.rowActionText}>Testar</Text>
    </Pressable>
  </View>
);

const ModelRow: React.FC<{
  name: string;
  provider: string;
  context: string;
  status: string;
}> = ({ name, provider, context, status }) => (
  <View style={styles.tableRow}>
    <Text style={styles.tableProvider}>{name}</Text>
    <Text style={styles.tableAccount}>{provider}</Text>
    <Text style={styles.tableAccount}>{context}</Text>
    <View style={styles.statusCell}>
      <View style={[styles.statusDot, status !== "Ativo" && styles.statusDotPending]} />
      <Text style={[styles.statusText, status !== "Ativo" && styles.statusTextPending]}>{status}</Text>
    </View>
  </View>
);

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
  tableCard: {
    gap: 0,
  },
  tableHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    marginBottom: 6,
  },
  tableRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  tableProvider: {
    flex: 1,
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
  },
  tableAccount: {
    flex: 2,
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  statusCell: {
    width: 110,
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  statusDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: theme.success,
  },
  statusDotPending: {
    backgroundColor: theme.textMuted,
  },
  statusText: {
    color: theme.success,
    fontSize: 11,
    fontWeight: "700",
  },
  statusTextPending: {
    color: theme.textMuted,
  },
  rowAction: {
    minWidth: 72,
    borderRadius: 7,
    borderWidth: 1,
    borderColor: theme.border,
    paddingVertical: 5,
    alignItems: "center",
  },
  rowActionText: {
    color: theme.text,
    fontSize: 11,
    fontWeight: "700",
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
