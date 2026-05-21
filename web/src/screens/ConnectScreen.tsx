import { CommonActions, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage } from "../api/client";
import type { AuthBootstrap, Provider } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Input } from "../components/Input";
import { Screen } from "../components/Screen";
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
  const [remember, setRemember] = useState(true);
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
        permissions: {
          canRunAllBacklog: user.permissions?.can_run_all_backlog ?? true,
        },
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
      chrome="auth"
      eyebrow="Web 01 - App Login"
      title="SendSprint"
      subtitle="Entre com email e senha da assinatura. Nesta fase local todos os usuarios autenticados continuam ativos, mas o fluxo ja segue o shell comercial planejado."
      footer={
        <View style={styles.footerActions}>
          <Button
            title={busy ? "Entrando..." : "Entrar"}
            onPress={handleLogin}
            loading={busy}
            disabled={booting || !email.trim() || !password.trim()}
          />
          <Button
            title="Entrar com Microsoft"
            onPress={handleLogin}
            variant="secondary"
            disabled={booting}
          />
        </View>
      }
    >
      <View style={styles.split}>
        <Card style={styles.loginCard}>
          <Text style={styles.kicker}>LOGIN SENDSPRINT</Text>
          <Text style={styles.brand}>SendSprint</Text>
          <Text style={styles.brandSub}>AI Sprint Delivery Control Plane</Text>
          <View style={{ height: 18 }} />
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
          <View style={styles.preferenceRow}>
            <Pressable onPress={() => setRemember((current) => !current)} style={styles.checkboxRow}>
              <View style={[styles.checkbox, remember && styles.checkboxActive]}>
                {remember ? <Text style={styles.checkboxMark}>x</Text> : null}
              </View>
              <Text style={styles.preferenceText}>Manter sessao neste workspace</Text>
            </Pressable>
            <Pressable>
              <Text style={styles.inlineLink}>Esqueci a senha</Text>
            </Pressable>
          </View>
          <Text style={styles.metaText}>
            Login do app primeiro. Conexao com provider, importacao da sprint e fallback por browser acontecem depois do botao Iniciar.
          </Text>
          <Text style={styles.sideHint}>
            SSO Azure e gestao de assinatura entram aqui sem trocar o fluxo principal.
          </Text>
        </Card>

        <Card style={styles.backendCard}>
          <Text style={styles.kicker}>STATUS DO BACKEND LOCAL</Text>
          <Text style={styles.sideTitle}>Tudo pronto para o shell web</Text>
          <Text style={styles.copy}>
            O backend local valida o endpoint, recupera o token operador e exibe a disponibilidade do plano de controle antes do onboarding da sprint.
          </Text>
          <Input
            label="API"
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
            <View style={styles.statusList}>
              <StatusLine label="Control Plane" value="Online" tone="success" />
              <StatusLine label="Auth Local" value="Online" tone="success" />
              <StatusLine
                label="Profile cache"
                value={session.appUser?.email ? "Hydrated" : "Waiting login"}
              />
              <StatusLine
                label="Operator token"
                value={status?.operator_token ? "Ready" : "Pending"}
                tone={status?.operator_token ? "success" : "default"}
              />
              <StatusLine label="Provider padrao" value={status?.default_provider ?? "nenhum"} />
              <StatusLine
                label="GitHub CLI"
                value={status?.providers.github.configured ? "Ready" : "Pending"}
              />
              <StatusLine label="Versao" value="local" />
            </View>
          )}
        </Card>
      </View>
    </Screen>
  );
};

const StatusLine: React.FC<{
  label: string;
  value: string;
  tone?: "default" | "success";
}> = ({ label, value, tone = "default" }) => (
  <View style={styles.statusLine}>
    <Text style={styles.statusLineLabel}>{label}</Text>
    <Text style={[styles.statusLineValue, tone === "success" && styles.statusLineValueSuccess]}>
      {value}
    </Text>
  </View>
);

const styles = StyleSheet.create({
  split: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 18,
    alignItems: "stretch",
  },
  loginCard: {
    flex: 1,
    minWidth: 320,
    paddingHorizontal: 28,
    paddingVertical: 28,
  },
  backendCard: {
    width: 360,
    minWidth: 320,
    backgroundColor: "rgba(255,255,255,0.88)",
    justifyContent: "center",
    paddingHorizontal: 24,
    paddingVertical: 24,
  },
  kicker: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  brand: {
    color: theme.text,
    fontSize: 32,
    fontWeight: "800",
    marginTop: 8,
  },
  brandSub: {
    color: theme.textMuted,
    fontSize: 14,
    marginTop: 6,
  },
  footerActions: {
    gap: 10,
  },
  copy: {
    color: theme.textMuted,
    fontSize: 14,
    lineHeight: 21,
  },
  sideTitle: {
    color: theme.text,
    fontSize: 22,
    lineHeight: 28,
    fontWeight: "800",
    marginTop: 6,
    marginBottom: 8,
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
  errorText: {
    color: theme.danger,
    fontSize: 12,
    fontFamily: theme.fontMono,
    lineHeight: 18,
  },
  metaText: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 10,
    lineHeight: 18,
  },
  sideHint: {
    color: theme.primary,
    fontSize: 12,
    marginTop: 10,
    lineHeight: 18,
  },
  preferenceRow: {
    marginTop: 2,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    flexWrap: "wrap",
  },
  checkboxRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 6,
    borderWidth: 1,
    borderColor: theme.border,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: theme.surfaceAlt,
  },
  checkboxActive: {
    backgroundColor: "rgba(44,107,237,0.14)",
    borderColor: theme.primary,
  },
  checkboxMark: {
    color: theme.primary,
    fontSize: 11,
    fontWeight: "800",
  },
  preferenceText: {
    color: theme.textMuted,
    fontSize: 12,
  },
  inlineLink: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: "700",
  },
  statusList: {
    gap: 10,
    marginTop: 10,
  },
  statusLine: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
    paddingBottom: 10,
    borderBottomWidth: 1,
    borderBottomColor: "rgba(215,228,245,0.9)",
  },
  statusLineLabel: {
    color: theme.textMuted,
    fontSize: 12,
  },
  statusLineValue: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
    fontFamily: theme.fontMono,
  },
  statusLineValueSuccess: {
    color: theme.success,
  },
});
