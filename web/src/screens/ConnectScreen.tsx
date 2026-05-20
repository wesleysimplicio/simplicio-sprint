import { CommonActions, useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, StyleSheet, Text, View } from "react-native";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Screen } from "../components/Screen";
import type { AuthStatus, Provider } from "../api/types";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Connect">;

export const ConnectScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session, setAccount, setAdoTeamPath, setBackendUrl, setProvider } = useSession();
  const [url, setUrl] = useState(session.backendUrl);
  const [busy, setBusy] = useState(false);
  const [booting, setBooting] = useState(true);
  const [pinged, setPinged] = useState<{ ok: boolean; version?: string } | null>(null);
  const redirected = useRef(false);

  useEffect(() => {
    void bootstrap();
  }, []);

  const resolveConfiguredProvider = (status: AuthStatus): Provider | null => {
    if (status.default_provider === "azuredevops" && status.azuredevops_configured) {
      return "azuredevops";
    }
    if (status.default_provider === "jira" && status.jira_configured) {
      return "jira";
    }
    if (status.azuredevops_configured) return "azuredevops";
    if (status.jira_configured) return "jira";
    return null;
  };

  const applyKnownSession = async (status: AuthStatus, provider: Provider) => {
    await setProvider(provider);
    if (provider === "azuredevops") {
      await setAccount(status.providers.azuredevops.account ?? null);
      await setAdoTeamPath(status.providers.azuredevops.team_path ?? null);
      return;
    }
    await setAccount(status.providers.jira.account ?? null);
    await setAdoTeamPath(null);
  };

  const goDashboard = () => {
    nav.dispatch(
      CommonActions.reset({
        index: 0,
        routes: [{ name: "Dashboard" }],
      }),
    );
  };

  const bootstrap = async () => {
    try {
      api.setBaseUrl(url);
      const health = await api.health();
      setPinged({ ok: health.ok, version: health.version });
      const status = await api.authStatus();
      const provider = resolveConfiguredProvider(status);
      if (provider && !redirected.current) {
        redirected.current = true;
        await applyKnownSession(status, provider);
        goDashboard();
      }
    } catch {
      setPinged({ ok: false });
    } finally {
      setBooting(false);
    }
  };

  const handleConnect = async () => {
    setBusy(true);
    try {
      await setBackendUrl(url);
      api.setBaseUrl(url);
      const health = await api.health();
      setPinged({ ok: health.ok, version: health.version });
      const status = await api.authStatus();
      const provider = resolveConfiguredProvider(status);
      if (provider) {
        await applyKnownSession(status, provider);
        goDashboard();
        return;
      }
      nav.navigate("Provider");
    } catch (e) {
      Alert.alert("Conexao falhou", String((e as Error).message ?? e));
      setPinged({ ok: false });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen
      title="SendSprint local"
      subtitle="Se o CLI ja deixou o backend autenticado, o painel entra direto logado. Caso contrario, conecte ao endpoint local e escolha o provider."
    >
      <View style={styles.hero}>
        <Text style={styles.brand}>SendSprint</Text>
        <Text style={styles.brandSub}>control plane local da sprint</Text>
      </View>

      <Input
        label="URL do backend"
        value={url}
        onChangeText={setUrl}
        placeholder="http://127.0.0.1:8765"
        keyboardType="url"
        autoCapitalize="none"
        monospace
      />

      <Button title="Conectar" onPress={handleConnect} loading={busy} disabled={booting} />

      {booting ? (
        <View style={styles.bootRow}>
          <ActivityIndicator color={theme.primary} />
          <Text style={styles.bootText}>Verificando backend e sessao persistida...</Text>
        </View>
      ) : null}

      {pinged?.ok ? <Text style={styles.ok}>Backend v{pinged.version} OK</Text> : null}
      {pinged && !pinged.ok ? <Text style={styles.fail}>Backend nao respondeu</Text> : null}

      <Text style={styles.tip}>
        Preferencia local: http://127.0.0.1:8765. Em outro dispositivo, use o IP da maquina na
        mesma rede.
      </Text>
    </Screen>
  );
};

const styles = StyleSheet.create({
  hero: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 28,
    alignItems: "center",
    borderWidth: 1,
    borderColor: theme.border,
    marginBottom: 12,
    shadowColor: "#91b4dc",
    shadowOpacity: 0.12,
    shadowRadius: 18,
    shadowOffset: { width: 0, height: 10 },
    elevation: 4,
  },
  brand: {
    color: theme.text,
    fontSize: 36,
    fontWeight: "900",
    letterSpacing: -1,
  },
  brandSub: {
    color: theme.primarySoft,
    fontSize: 14,
    marginTop: 4,
  },
  bootRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
  },
  bootText: {
    color: theme.textMuted,
    fontSize: 13,
  },
  ok: { color: theme.success, fontSize: 14 },
  fail: { color: theme.danger, fontSize: 14 },
  tip: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 18,
    fontFamily: theme.fontMono,
  },
});
