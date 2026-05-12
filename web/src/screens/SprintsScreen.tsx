import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useState } from "react";
import {
  ActivityIndicator,
  Alert,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import type { ImportStatus, SprintSummary } from "../api/types";
import { theme } from "../theme";

type Nav = NativeStackNavigationProp<RootStackParamList, "Sprints">;

export const SprintsScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session } = useSession();
  const [sprints, setSprints] = useState<SprintSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [importJob, setImportJob] = useState<{ id: string; status?: ImportStatus } | null>(null);

  const provider = session.provider ?? "jira";

  const load = async () => {
    setLoading(true);
    try {
      const list = await api.listSprints(provider, {
        board_id: session.jiraBoardId ?? undefined,
        team_path: session.adoTeamPath ?? undefined,
      });
      setSprints(list);
    } catch (e) {
      Alert.alert("Falha ao listar", String((e as Error).message ?? e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [provider]);

  useEffect(() => {
    if (!importJob) return;
    const id = setInterval(async () => {
      try {
        const s = await api.importStatus(importJob.id);
        setImportJob({ id: importJob.id, status: s });
        if (s.state !== "running") clearInterval(id);
      } catch {
        clearInterval(id);
      }
    }, 1500);
    return () => clearInterval(id);
  }, [importJob?.id]);

  const handleImportAll = async () => {
    try {
      const job = await api.importSprints(provider, {
        board_id: session.jiraBoardId ?? undefined,
        team_path: session.adoTeamPath ?? undefined,
      });
      setImportJob({ id: job.job_id });
    } catch (e) {
      Alert.alert("Falha", String((e as Error).message ?? e));
    }
  };

  return (
    <Screen
      title="Sprints ativas"
      subtitle={`Provedor: ${provider}${session.account ? ` · ${session.account}` : ""}`}
      footer={
        <Button
          title={
            importJob?.status?.state === "running"
              ? `Importando… ${importJob.status?.fetched ?? 0}/${importJob.status?.total ?? "?"}`
              : "Importar todas em background"
          }
          onPress={handleImportAll}
          variant="secondary"
          loading={importJob?.status?.state === "running"}
        />
      }
    >
      {loading ? (
        <ActivityIndicator color={theme.primary} style={{ marginTop: 32 }} />
      ) : sprints.length === 0 ? (
        <Text style={styles.empty}>Nenhuma sprint ativa encontrada.</Text>
      ) : (
        <ScrollView
          refreshControl={<RefreshControl refreshing={loading} onRefresh={load} tintColor={theme.primary} />}
        >
          {sprints.map((s) => (
            <Card
              key={s.id}
              onPress={() => nav.navigate("SprintDetail", { sprintId: s.id })}
              style={{ marginBottom: 12 }}
            >
              <View style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.name}>{s.name}</Text>
                  {s.goal ? <Text style={styles.goal}>"{s.goal}"</Text> : null}
                  <View style={styles.meta}>
                    {s.item_count != null ? (
                      <Text style={styles.metaText}>📋 {s.item_count} itens</Text>
                    ) : null}
                    {s.start_date ? (
                      <Text style={styles.metaText}>
                        📅 {String(s.start_date).slice(0, 10)}
                      </Text>
                    ) : null}
                    <View style={styles.badge}>
                      <Text style={styles.badgeText}>{s.state}</Text>
                    </View>
                  </View>
                </View>
                <Text style={styles.chev}>›</Text>
              </View>
            </Card>
          ))}
        </ScrollView>
      )}
    </Screen>
  );
};

const styles = StyleSheet.create({
  empty: { color: theme.textMuted, textAlign: "center", marginTop: 40 },
  row: { flexDirection: "row", alignItems: "center", gap: 10 },
  name: { color: theme.text, fontSize: 16, fontWeight: "700" },
  goal: { color: theme.primarySoft, fontSize: 13, fontStyle: "italic", marginTop: 2 },
  meta: { flexDirection: "row", flexWrap: "wrap", gap: 10, marginTop: 8, alignItems: "center" },
  metaText: { color: theme.textMuted, fontSize: 12 },
  badge: {
    backgroundColor: "rgba(52, 211, 153, 0.18)",
    paddingHorizontal: 8,
    paddingVertical: 2,
    borderRadius: 999,
  },
  badgeText: { color: theme.success, fontSize: 11, fontWeight: "700", textTransform: "uppercase" },
  chev: { color: theme.primarySoft, fontSize: 28, fontWeight: "300" },
});
