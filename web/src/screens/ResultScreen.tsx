import { useNavigation, useRoute, type RouteProp } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import { Linking, ScrollView, StyleSheet, Text, View } from "react-native";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import type { RunStatus } from "../api/types";
import { useSession } from "../store/session";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Result">;
type Rt = RouteProp<RootStackParamList, "Result">;

export const ResultScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const route = useRoute<Rt>();
  const { api } = useSession();
  const [run, setRun] = useState<RunStatus | null>(null);

  useEffect(() => {
    (async () => {
      try {
        setRun(await api.getRun(route.params.runId));
      } catch {
        // ignore
      }
    })();
  }, []);

  const failed = run?.failed ?? false;
  const headline = failed ? "Entrega falhou" : "Sprint entregue 🎉";

  return (
    <Screen
      title={headline}
      subtitle={
        run?.summary ??
        `run_id ${route.params.runId} · ${run?.state ?? "carregando…"}`
      }
      footer={
        <View style={{ gap: 10 }}>
          {run?.pr_url ? (
            <Button title="Abrir PR" onPress={() => Linking.openURL(run.pr_url!)} icon="↗" />
          ) : null}
          <Button title="Voltar pra lista" variant="secondary" onPress={() => nav.popToTop()} />
        </View>
      }
    >
      <ScrollView contentContainerStyle={{ gap: 12 }}>
        <Card>
          <Text style={styles.label}>RESUMO</Text>
          <Text style={styles.value}>{run?.summary ?? "—"}</Text>
        </Card>
        <Card>
          <Text style={styles.label}>STATUS</Text>
          <Text
            style={[
              styles.value,
              { color: failed ? theme.danger : theme.success },
            ]}
          >
            {run?.state ?? "—"}
          </Text>
        </Card>
        {run?.pr_url ? (
          <Card>
            <Text style={styles.label}>PULL REQUEST</Text>
            <Text style={[styles.value, styles.mono]}>{run.pr_url}</Text>
          </Card>
        ) : null}
        <Card>
          <Text style={styles.label}>METADADOS</Text>
          <Text style={[styles.value, styles.mono]}>
            sprint: {run?.sprint_id ?? "—"}
          </Text>
          <Text style={[styles.value, styles.mono]}>
            provider: {run?.provider ?? "—"}
          </Text>
          <Text style={[styles.value, styles.mono]}>
            iniciado: {run?.started_at?.slice(0, 19) ?? "—"}
          </Text>
          <Text style={[styles.value, styles.mono]}>
            terminado: {run?.finished_at?.slice(0, 19) ?? "—"}
          </Text>
        </Card>
      </ScrollView>
    </Screen>
  );
};

const styles = StyleSheet.create({
  label: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
  },
  value: { color: theme.text, fontSize: 16, fontWeight: "600", marginTop: 4 },
  mono: { fontFamily: theme.fontMono, fontSize: 13, fontWeight: "400" },
});
