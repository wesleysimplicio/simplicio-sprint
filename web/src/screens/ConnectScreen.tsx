import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useState } from "react";
import { Alert, StyleSheet, Text, View } from "react-native";
import { Button } from "../components/Button";
import { Input } from "../components/Input";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Connect">;

export const ConnectScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { session, api, setBackendUrl } = useSession();
  const [url, setUrl] = useState(session.backendUrl);
  const [busy, setBusy] = useState(false);
  const [pinged, setPinged] = useState<{ ok: boolean; version?: string } | null>(null);

  const handleConnect = async () => {
    setBusy(true);
    try {
      await setBackendUrl(url);
      api.setBaseUrl(url);
      const h = await api.health();
      setPinged({ ok: h.ok, version: h.version });
      nav.navigate("Provider");
    } catch (e) {
      Alert.alert("Conexão falhou", String((e as Error).message ?? e));
      setPinged({ ok: false });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen
      title="Conectar ao backend"
      subtitle="Aponte o app pro endpoint do `python -m sendsprint.api` rodando no seu Mac/Linux/WSL. Use o IP da máquina + porta (default 8765)."
    >
      <View style={styles.gradient}>
        <Text style={styles.brand}>⚡ SendSprint</Text>
        <Text style={styles.brandSub}>controle remoto da sua sprint</Text>
      </View>

      <Input
        label="URL do backend"
        value={url}
        onChangeText={setUrl}
        placeholder="http://192.168.0.10:8765"
        keyboardType="url"
        autoCapitalize="none"
        monospace
      />

      <Button title="Conectar" onPress={handleConnect} loading={busy} />
      {pinged?.ok ? (
        <Text style={styles.ok}>✓ backend v{pinged.version} OK</Text>
      ) : pinged && !pinged.ok ? (
        <Text style={styles.fail}>✗ backend não respondeu</Text>
      ) : null}

      <Text style={styles.tip}>
        💡 No emulador iOS: use http://localhost:8765 — no Android/dispositivo
        físico: use http://&lt;IP-da-máquina&gt;:8765 (mesma rede Wi-Fi).
      </Text>
    </Screen>
  );
};

const styles = StyleSheet.create({
  gradient: {
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    padding: 28,
    alignItems: "center",
    borderWidth: 1,
    borderColor: theme.border,
    marginBottom: 12,
  },
  brand: { color: theme.text, fontSize: 36, fontWeight: "900", letterSpacing: -1 },
  brandSub: { color: theme.primarySoft, fontSize: 14, marginTop: 4 },
  ok: { color: theme.success, fontSize: 14 },
  fail: { color: theme.danger, fontSize: 14 },
  tip: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 18,
    fontFamily: theme.fontMono,
  },
});
