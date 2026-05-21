import { CommonActions, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage } from "../api/client";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { Screen } from "../components/Screen";
import type { AuthBootstrap, Provider } from "../api/types";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Connect">;

export const ConnectScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const {
    api,
    session,
    setAccount,
    setAdoTeamPath,
    setAppUser,
    setBackendUrl,
    setOperatorToken,
    setProvider,
  } = useSession();
  const [url, setUrl] = useState(session.backendUrl);
  const [email, setEmail] = useState(session.appUser?.email ?? "");
  const [password, setPassword] = useState("");
  const [booting, setBooting] = useState(true);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<AuthBootstrap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const redirected = useRef(false);

  useEffect(() => {
    void bootstrap();
  }, []);

  const bootstrap = async () => {
    setBooting(true);
    setError(null);
    try {
      api.setBaseUrl(url);
      const bootstrapState = await api.authBootstrap();
      api.setOperatorToken(bootstrapState.operator_token);
      await setOperatorToken(bootstrapState.operator_token);
      setStatus(bootstrapState);
      if (session.appUser?.active && !redirected.current) {
        redirected.current = true;
        await hydrateKnownProvider(bootstrapState);
        goDashboard();
      }
    } catch (e) {
      setError(getApiErrorMessage(e));
      setStatus(null);
    } finally {
      setBooting(false);
    }
  };

  const hydrateKnownProvider = async (bootstrapState: AuthBootstrap) => {
    const resolvedProvider = resolveConfiguredProvider(bootstrapState);
    if (!resolvedProvider) return;
    await setProvider(resolvedProvider);
    if (resolvedProvider === "azuredevops") {
      await setAccount(bootstrapState.providers.azuredevops.account ?? null);
      await setAdoTeamPath(bootstrapState.providers.azuredevops.team_path ?? null);
      return;
    }
    await setAccount(bootstrapState.providers.jira.account ?? null);
    await setAdoTeamPath(null);
  };

  const resolveConfiguredProvider = (bootstrapState: AuthBootstrap): Provider | null => {
    if (
      bootstrapState.default_provider === "azuredevops" &&
      bootstrapState.azuredevops_configured
    ) {
      return "azuredevops";
    }
    if (bootstrapState.default_provider === "jira" && bootstrapState.jira_configured) {
      return "jira";
    }
    if (bootstrapState.azuredevops_configured) return "azuredevops";
    if (bootstrapState.jira_configured) return "jira";
    return null;
  };

  const goDashboard = () => {
    nav.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: "Dashboard" }],
      }),
    );
  };

  const handleLogin = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      await setBackendUrl(url);
      api.setBaseUrl(url);
      const bootstrapState = await api.authBootstrap();
      api.setOperatorToken(bootstrapState.operator_token);
      await setOperatorToken(bootstrapState.operator_token);
      const user = await api.loginApp({ email, password });
      await setAppUser({
        email: user.email,
        active: user.active,
        displayName: user.display_name ?? null,
      });
      await hydrateKnownProvider(bootstrapState);
      setStatus(bootstrapState);
      goDashboard();
    } catch (e) {
      setError(getApiErrorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen
      title="SendSprint"
      subtitle="Entre com email e senha da assinatura. Nesta fase local todos os usuarios autenticados ficam ativos."
      footer={
        <Button
          title={busy ? "Entrando..." : "Entrar"}
          onPress={handleLogin}
          loading={busy}
          disabled={booting}
        />
      }
    >
      <Card style={styles.hero}>
        <Text style={styles.kicker}>LOCAL CONTROL PLANE</Text>
        <Text style={styles.title}>Entrega de sprint com shell orientado por chat</Text>
        <Text style={styles.copy}>
          O login do app valida o acesso ao SendSprint. A conexao com Jira, Azure DevOps ou GitHub
          acontece depois, a partir do botao iniciar.
        </Text>
      </Card>

      <Input
        label="Email"
        value={email}
        onChangeText={setEmail}
        placeholder="voce@empresa.com"
        keyboardType="email-address"
      />
      <Input
        label="Senha"
        value={password}
        onChangeText={setPassword}
        placeholder="********"
        secureTextEntry
      />

      <Card style={styles.backendCard}>
        <Text style={styles.backendLabel}>BACKEND LOCAL</Text>
        <Input
          label="URL do backend"
          value={url}
          onChangeText={setUrl}
          placeholder="http://127.0.0.1:8765"
          keyboardType="url"
          autoCapitalize="none"
          monospace
        />
        {booting ? (
          <View style={styles.statusRow}>
            <ActivityIndicator color={theme.primary} size="small" />
            <Text style={styles.statusText}>Validando endpoint e recuperando token local...</Text>
          </View>
        ) : error ? (
          <Text style={styles.errorText}>{error}</Text>
        ) : (
          <Text style={styles.okText}>
            Backend pronto. Provider padrao: {status?.default_provider ?? "nenhum"}.
          </Text>
        )}
      </Card>
    </Screen>
  );
};

const styles = StyleSheet.create({
  hero: {
    backgroundColor: "#eef5ff",
    gap: 8,
  },
  kicker: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
  },
  title: {
    color: theme.text,
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
  },
  copy: {
    color: theme.textMuted,
    fontSize: 14,
    lineHeight: 21,
  },
  backendCard: {
    gap: 10,
  },
  backendLabel: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  statusRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  statusText: {
    color: theme.textMuted,
    fontSize: 12,
  },
  okText: {
    color: theme.success,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  errorText: {
    color: theme.danger,
    fontSize: 12,
    fontFamily: theme.fontMono,
    lineHeight: 18,
  },
});
