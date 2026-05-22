import { CommonActions, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useRef, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage } from "../api/client";
import type { AuthBootstrap, Provider } from "../api/types";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Icon } from "../components/Icon";
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
  const [email, setEmail] = useState(session.appUser?.email ?? "");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<AuthBootstrap | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const redirected = useRef(false);

  useEffect(() => {
    void bootstrap();
  }, []);

  const bootstrap = async () => {
    setError(null);
    try {
      api.setBaseUrl(session.backendUrl);
      const bootstrapState = await api.authBootstrap();
      api.setOperatorToken(bootstrapState.operator_token);
      await setOperatorToken(bootstrapState.operator_token);
      setStatus(bootstrapState);
      setBackendOnline(true);
      if (session.appUser?.active && !redirected.current) {
        redirected.current = true;
        await hydrateKnownProvider(bootstrapState);
        goDashboard();
      }
    } catch (e) {
      setError(getApiErrorMessage(e));
      setBackendOnline(false);
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

  const resolveConfiguredProvider = (
    bootstrapState: AuthBootstrap,
  ): Provider | null => {
    if (
      bootstrapState.default_provider === "azuredevops" &&
      bootstrapState.azuredevops_configured
    ) {
      return "azuredevops";
    }
    if (
      bootstrapState.default_provider === "jira" &&
      bootstrapState.jira_configured
    ) {
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
      await setBackendUrl(session.backendUrl);
      api.setBaseUrl(session.backendUrl);
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

  const isCompact = Platform.OS === "web" ? false : true;

  return (
    <Screen chrome="auth">
      <View style={[styles.split, isCompact && styles.splitCompact]}>
        <Card style={styles.loginCard} padding={48}>
          <View style={styles.brandRow}>
            <View style={styles.brandBadge}>
              <Icon name="logo" size={26} color="#fff" />
            </View>
            <View>
              <Text style={styles.brandTitle}>SendSprint</Text>
              <Text style={styles.brandTagline}>
                AI Sprint Delivery Control Plane
              </Text>
            </View>
          </View>

          <View style={{ height: 32 }} />

          <Input
            label="E-mail"
            value={email}
            onChangeText={setEmail}
            placeholder="voce@empresa.com"
            keyboardType="email-address"
          />
          <View style={{ height: 14 }} />
          <Input
            label="Senha"
            value={password}
            onChangeText={setPassword}
            placeholder="••••••••••"
            secureTextEntry
            inlineLabelRight={
              <Pressable>
                <Text style={styles.forgotLink}>Esqueceu a senha?</Text>
              </Pressable>
            }
          />

          <View style={styles.rememberRow}>
            <Pressable
              onPress={() => setRemember((v) => !v)}
              style={styles.checkboxRow}
            >
              <View
                style={[styles.checkbox, remember && styles.checkboxActive]}
              >
                {remember ? (
                  <Icon name="check" size={11} color="#fff" />
                ) : null}
              </View>
              <Text style={styles.checkboxLabel}>Lembrar de mim</Text>
            </Pressable>
          </View>

          <Button
            title={busy ? "Entrando…" : "Entrar"}
            onPress={handleLogin}
            loading={busy}
            size="lg"
            fullWidth
            disabled={!email.trim() || !password.trim()}
          />

          <View style={styles.divider}>
            <View style={styles.dividerLine} />
            <Text style={styles.dividerText}>ou continue com SSO</Text>
            <View style={styles.dividerLine} />
          </View>

          <Button
            title="Entrar com Microsoft"
            onPress={handleLogin}
            variant="secondary"
            size="lg"
            iconLeft="microsoft"
            fullWidth
          />

          {error ? <Text style={styles.errorText}>{error}</Text> : null}

          <Text style={styles.legalText}>
            © 2026 SendSprint. Todos os direitos reservados.
          </Text>
        </Card>

        <Card style={styles.statusCard} padding={28}>
          <Text style={styles.statusTitle}>Status do Backend Local</Text>
          <View style={styles.statusBadge}>
            <View
              style={[
                styles.statusDot,
                {
                  backgroundColor:
                    backendOnline === false ? theme.danger : theme.success,
                },
              ]}
            />
            <Text
              style={[
                styles.statusBadgeText,
                {
                  color: backendOnline === false ? theme.danger : theme.success,
                },
              ]}
            >
              {backendOnline === false ? "Offline" : "Online"}
            </Text>
          </View>
          <Text style={styles.statusSubtitle}>
            {backendOnline === false
              ? "Não foi possível alcançar o backend local."
              : "Tudo funcionando normalmente."}
          </Text>

          <View style={styles.statusList}>
            <StatusRow
              label="API"
              value="Online"
              tone={backendOnline === false ? "danger" : "success"}
            />
            <StatusRow
              label="Banco de Dados"
              value="Online"
              tone={backendOnline === false ? "danger" : "success"}
            />
            <StatusRow
              label="Fila (Jobs)"
              value="Online"
              tone={backendOnline === false ? "danger" : "success"}
            />
            <StatusRow
              label="Armazenamento"
              value="Online"
              tone={backendOnline === false ? "danger" : "success"}
            />
          </View>

          <View style={styles.statusDivider} />

          <View style={styles.statusMetaRow}>
            <Text style={styles.statusMetaLabel}>Ambiente</Text>
            <Text style={styles.statusMetaValue}>local</Text>
          </View>
          <View style={styles.statusMetaRow}>
            <Text style={styles.statusMetaLabel}>Versão</Text>
            <Text style={styles.statusMetaValue}>v0.9.0</Text>
          </View>
          <View style={styles.statusMetaRow}>
            <Text style={styles.statusMetaLabel}>Uptime</Text>
            <Text style={styles.statusMetaValue}>2h 14m 32s</Text>
          </View>

          <Button
            title="Ver detalhes dos serviços"
            onPress={() => void bootstrap()}
            variant="secondary"
            size="md"
            fullWidth
          />

          <View style={styles.statusFooter}>
            <View style={styles.statusFooterItem}>
              <Icon name="doc" size={13} color={theme.textMuted} />
              <Text style={styles.statusFooterText}>Docs</Text>
            </View>
            <View style={styles.statusFooterItem}>
              <Icon name="settings" size={13} color={theme.textMuted} />
              <Text style={styles.statusFooterText}>Status</Text>
              <View
                style={[
                  styles.statusDot,
                  {
                    backgroundColor:
                      backendOnline === false ? theme.danger : theme.success,
                  },
                ]}
              />
            </View>
          </View>

          {status?.operator_token ? (
            <Text style={styles.tokenHint}>
              Token operador: pronto
            </Text>
          ) : null}
        </Card>
      </View>
    </Screen>
  );
};

const StatusRow: React.FC<{
  label: string;
  value: string;
  tone: "success" | "danger" | "default";
}> = ({ label, value, tone }) => (
  <View style={styles.statusRow}>
    <Text style={styles.statusRowLabel}>{label}</Text>
    <View style={styles.statusRowValueWrap}>
      <View
        style={[
          styles.statusDot,
          {
            backgroundColor:
              tone === "danger"
                ? theme.danger
                : tone === "success"
                  ? theme.success
                  : theme.textMuted,
          },
        ]}
      />
      <Text
        style={[
          styles.statusRowValue,
          {
            color:
              tone === "danger"
                ? theme.danger
                : tone === "success"
                  ? theme.success
                  : theme.textMuted,
          },
        ]}
      >
        {value}
      </Text>
    </View>
  </View>
);

const styles = StyleSheet.create({
  split: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 24,
    alignItems: "stretch",
    justifyContent: "center",
  },
  splitCompact: {
    flexDirection: "column",
  },
  loginCard: {
    flex: 1,
    maxWidth: 520,
    minWidth: 360,
    justifyContent: "center",
  },
  statusCard: {
    width: 340,
    minWidth: 320,
    gap: 14,
  },
  brandRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
  },
  brandBadge: {
    width: 56,
    height: 56,
    borderRadius: 14,
    backgroundColor: theme.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  brandTitle: {
    color: theme.text,
    fontSize: 28,
    fontWeight: "800",
    fontFamily: theme.fontSans,
    letterSpacing: -0.5,
  },
  brandTagline: {
    color: theme.textMuted,
    fontSize: 13,
    fontFamily: theme.fontSans,
    marginTop: 2,
  },
  forgotLink: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  rememberRow: {
    flexDirection: "row",
    alignItems: "center",
    paddingVertical: 4,
    marginTop: 6,
    marginBottom: 4,
  },
  checkboxRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  checkbox: {
    width: 18,
    height: 18,
    borderRadius: 5,
    borderWidth: 1,
    borderColor: theme.borderStrong,
    backgroundColor: theme.surface,
    alignItems: "center",
    justifyContent: "center",
  },
  checkboxActive: {
    backgroundColor: theme.primary,
    borderColor: theme.primary,
  },
  checkboxLabel: {
    color: theme.text,
    fontSize: 13,
    fontFamily: theme.fontSans,
  },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    marginVertical: 10,
  },
  dividerLine: {
    flex: 1,
    height: 1,
    backgroundColor: theme.border,
  },
  dividerText: {
    color: theme.textMuted,
    fontSize: 11,
    fontFamily: theme.fontSans,
  },
  errorText: {
    color: theme.danger,
    fontSize: 12,
    fontFamily: theme.fontMono,
    lineHeight: 18,
    marginTop: 8,
  },
  legalText: {
    color: theme.textSoft,
    fontSize: 11,
    fontFamily: theme.fontSans,
    textAlign: "center",
    marginTop: 18,
  },
  statusTitle: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  statusBadge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
  statusBadgeText: {
    fontSize: 13,
    fontWeight: "700",
    fontFamily: theme.fontSans,
  },
  statusSubtitle: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
    marginTop: -4,
  },
  statusList: {
    gap: 10,
    marginTop: 6,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  statusRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  statusRowLabel: {
    color: theme.text,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  statusRowValueWrap: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  statusRowValue: {
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  statusDivider: {
    height: 1,
    backgroundColor: theme.border,
    marginVertical: 6,
  },
  statusMetaRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  statusMetaLabel: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  statusMetaValue: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "600",
    fontFamily: theme.fontSans,
  },
  statusFooter: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginTop: 8,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  statusFooterItem: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
  },
  statusFooterText: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontSans,
  },
  tokenHint: {
    color: theme.textSoft,
    fontSize: 10,
    fontFamily: theme.fontMono,
    marginTop: 4,
  },
});
