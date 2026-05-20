import { useNavigation } from "@react-navigation/native";
import type { NativeStackNavigationProp } from "@react-navigation/native-stack";
import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { Button } from "../components/Button";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type {
  AuthStatus,
  ControlPlaneRunDetail,
  ControlPlaneRunSummary,
  ValidationDashboardResponse,
} from "../api/types";
import type { RootStackParamList } from "../navigation";
import { useSession } from "../store/session";
import { theme } from "../theme";

type ColumnKey = "queued" | "build" | "validate" | "review" | "done" | "blocked";
type Nav = NativeStackNavigationProp<RootStackParamList, "Dashboard">;

const COLUMN_META: Record<ColumnKey, { label: string; hint: string }> = {
  queued: { label: "Queue", hint: "Aguardando entrada ou preparacao" },
  build: { label: "Build", hint: "Execucao inicial e contexto" },
  validate: { label: "Validate", hint: "Lint, testes e seguranca" },
  review: { label: "Review", hint: "PR, evidencias e aprovacao" },
  done: { label: "Done", hint: "Entregas concluidas" },
  blocked: { label: "Blocked", hint: "Falhas e retrabalho" },
};

export const DashboardScreen: React.FC = () => {
  const nav = useNavigation<Nav>();
  const { api, session } = useSession();
  const [auth, setAuth] = useState<AuthStatus | null>(null);
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);
  const [validation, setValidation] = useState<ValidationDashboardResponse | null>(null);
  const [selected, setSelected] = useState<ControlPlaneRunDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = async (background = false) => {
    if (!background) setLoading(true);
    try {
      const [authStatus, runList, validationState] = await Promise.all([
        api.authStatus(),
        api.listControlPlaneRuns(),
        api.getValidationDashboard(),
      ]);
      setAuth(authStatus);
      setRuns(runList);
      setValidation(validationState);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const grouped = useMemo(() => {
    const base: Record<ColumnKey, ControlPlaneRunSummary[]> = {
      queued: [],
      build: [],
      validate: [],
      review: [],
      done: [],
      blocked: [],
    };
    for (const run of runs) base[resolveColumn(run)].push(run);
    return base;
  }, [runs]);

  const totals = useMemo(() => {
    const total = runs.length;
    const running = runs.filter((run) => run.state === "running").length;
    const blocked = runs.filter((run) => resolveColumn(run) === "blocked").length;
    const done = runs.filter((run) => resolveColumn(run) === "done").length;
    return { total, running, blocked, done };
  }, [runs]);

  const openDetail = async (runId: string) => {
    setSelected(await api.getControlPlaneRun(runId));
  };

  const providerLabel =
    session.provider === "azuredevops"
      ? "Azure DevOps"
      : session.provider === "jira"
        ? "Jira"
        : auth?.default_provider === "azuredevops"
          ? "Azure DevOps"
          : "Jira";

  return (
    <Screen
      title="SendSprint Dashboard"
      subtitle="Kanban operacional, relatorios por task e lanes de validacao em um layout leve."
      footer={
        <View style={{ gap: 10 }}>
          <Button title="Ver sprints" variant="secondary" onPress={() => nav.navigate("Sprints")} />
          <Button
            title="Parametros e conexoes"
            variant="secondary"
            onPress={() => nav.navigate("Settings")}
          />
          <Button
            title="Atualizar painel"
            variant="secondary"
            onPress={() => {
              setRefreshing(true);
              void load(true);
            }}
            icon="R"
          />
        </View>
      }
    >
      {loading ? (
        <ActivityIndicator color={theme.primary} style={{ marginTop: 48 }} />
      ) : (
        <ScrollView
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                void load(true);
              }}
              tintColor={theme.primary}
            />
          }
          showsVerticalScrollIndicator={false}
        >
          <Card style={styles.hero}>
            <View style={{ flex: 1 }}>
              <Text style={styles.kicker}>LOCAL CONTROL PLANE</Text>
              <Text style={styles.heroTitle}>Logado e pronto para operar</Text>
              <Text style={styles.heroText}>
                {providerLabel}
                {session.account ? ` · ${session.account}` : ""}
                {auth?.providers.azuredevops.team_path
                  ? ` · ${auth.providers.azuredevops.team_path}`
                  : ""}
              </Text>
            </View>
            <View style={styles.heroBadge}>
              <Text style={styles.heroBadgeText}>{totals.running} running</Text>
            </View>
          </Card>

          <View style={styles.metricGrid}>
            <MetricCard label="Runs totais" value={String(totals.total)} />
            <MetricCard label="Em execucao" value={String(totals.running)} accent="primary" />
            <MetricCard label="Bloqueadas" value={String(totals.blocked)} accent="danger" />
            <MetricCard label="Concluidas" value={String(totals.done)} accent="success" />
          </View>

          <Card>
            <Text style={styles.sectionLabel}>VALIDATION LANES</Text>
            {(validation?.lanes ?? []).map((lane) => (
              <View key={lane.lane} style={styles.laneRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.laneTitle}>{lane.lane.toUpperCase()}</Text>
                  <Text style={styles.laneText}>
                    {lane.last_result ?? lane.status} · {lane.events_count} eventos
                  </Text>
                </View>
                <View style={styles.barTrack}>
                  <View
                    style={[
                      styles.barFill,
                      {
                        width: `${Math.min(100, lane.events_count * 12)}%`,
                        backgroundColor: lane.status === "failed" ? theme.danger : theme.primary,
                      },
                    ]}
                  />
                </View>
              </View>
            ))}
          </Card>

          <Text style={styles.boardTitle}>KANBAN DE TASKS</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.board}>
            {(Object.keys(COLUMN_META) as ColumnKey[]).map((column) => (
              <View key={column} style={styles.column}>
                <View style={styles.columnHead}>
                  <Text style={styles.columnTitle}>{COLUMN_META[column].label}</Text>
                  <Text style={styles.columnHint}>{COLUMN_META[column].hint}</Text>
                </View>
                <View style={{ gap: 10 }}>
                  {grouped[column].length === 0 ? (
                    <Card style={styles.emptyCard}>
                      <Text style={styles.emptyText}>Sem cards nesta etapa.</Text>
                    </Card>
                  ) : (
                    grouped[column].map((run) => (
                      <Pressable key={run.run_id} onPress={() => void openDetail(run.run_id)}>
                        <Card style={styles.taskCard}>
                          <View style={styles.taskHead}>
                            <Text style={styles.taskSprint}>{run.sprint_id}</Text>
                            <StatusChip text={run.state} tone={chipTone(run)} />
                          </View>
                          <Text style={styles.taskTitle}>
                            {run.task ?? run.summary ?? "Task sem titulo"}
                          </Text>
                          <Text style={styles.taskMeta}>{run.provider} · {run.autonomy_level}</Text>
                          <View style={styles.progressTrack}>
                            <View
                              style={[
                                styles.progressFill,
                                { width: `${Math.max(8, Math.round((run.progress ?? 0.1) * 100))}%` },
                              ]}
                            />
                          </View>
                          <Text style={styles.taskMeta}>
                            readiness {Math.round(run.readiness_score ?? 0)} ·{" "}
                            {run.readiness_verdict ?? "pending"}
                          </Text>
                        </Card>
                      </Pressable>
                    ))
                  )}
                </View>
              </View>
            ))}
          </ScrollView>
        </ScrollView>
      )}

      <RunDetailModal detail={selected} onClose={() => setSelected(null)} />
    </Screen>
  );
};

const resolveColumn = (run: ControlPlaneRunSummary): ColumnKey => {
  if (run.failed || run.state === "failed") return "blocked";
  if (run.state === "done") return "done";
  if ((run.last_step ?? 0) >= 9 || run.readiness_verdict === "needs_human_approval") return "review";
  if ((run.last_step ?? 0) >= 4) return "validate";
  if ((run.last_step ?? 0) >= 1 || run.state === "running") return "build";
  return "queued";
};

const chipTone = (run: ControlPlaneRunSummary): "primary" | "danger" | "success" | "neutral" => {
  if (run.failed || run.state === "failed") return "danger";
  if (run.state === "done") return "success";
  if (run.state === "running") return "primary";
  return "neutral";
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  accent?: "primary" | "success" | "danger";
}> = ({ label, value, accent = "primary" }) => {
  const color =
    accent === "success" ? theme.success : accent === "danger" ? theme.danger : theme.primary;
  return (
    <Card style={styles.metricCard}>
      <Text style={styles.metricLabel}>{label}</Text>
      <Text style={[styles.metricValue, { color }]}>{value}</Text>
    </Card>
  );
};

const StatusChip: React.FC<{
  text: string;
  tone: "primary" | "danger" | "success" | "neutral";
}> = ({ text, tone }) => {
  const backgroundColor =
    tone === "success"
      ? "rgba(30,169,124,0.12)"
      : tone === "danger"
        ? "rgba(207,81,97,0.12)"
        : tone === "primary"
          ? "rgba(44,107,237,0.12)"
          : "rgba(108,134,163,0.14)";
  const color =
    tone === "success"
      ? theme.success
      : tone === "danger"
        ? theme.danger
        : tone === "primary"
          ? theme.primary
          : theme.textMuted;
  return (
    <View style={[styles.statusChip, { backgroundColor }]}>
      <Text style={[styles.statusChipText, { color }]}>{text}</Text>
    </View>
  );
};

const RunDetailModal: React.FC<{
  detail: ControlPlaneRunDetail | null;
  onClose: () => void;
}> = ({ detail, onClose }) => (
  <Modal visible={Boolean(detail)} transparent animationType="fade" onRequestClose={onClose}>
    <View style={styles.modalBackdrop}>
      <View style={styles.modalCard}>
        <View style={styles.modalHead}>
          <View style={{ flex: 1 }}>
            <Text style={styles.modalTitle}>{detail?.run.sprint_id ?? "Task"}</Text>
            <Text style={styles.modalSubtitle}>
              {detail?.run.summary ?? detail?.run.task ?? "Sem resumo"}
            </Text>
          </View>
          <Button title="Fechar" variant="ghost" onPress={onClose} />
        </View>
        <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={{ gap: 14 }}>
          <Card>
            <Text style={styles.sectionLabel}>QUALIDADE</Text>
            <Text style={styles.modalText}>verdict: {detail?.quality_gate?.verdict ?? "pending"}</Text>
            {(detail?.quality_gate?.checks ?? []).slice(0, 5).map((check) => (
              <Text key={check.check_name} style={styles.modalText}>
                {check.passed ? "OK" : "FAIL"} {check.check_name} · {check.details || check.severity}
              </Text>
            ))}
          </Card>

          <Card>
            <Text style={styles.sectionLabel}>EVIDENCIAS</Text>
            <Text style={styles.modalText}>
              {(detail?.evidence?.total_items ?? 0)} item(s) · finalizado{" "}
              {detail?.evidence?.finalized ? "sim" : "nao"}
            </Text>
            {(detail?.evidence?.items ?? []).slice(0, 6).map((item) => (
              <Text key={`${item.path}-${item.label}`} style={styles.modalText}>
                {item.label} · {item.path}
              </Text>
            ))}
          </Card>

          <Card>
            <Text style={styles.sectionLabel}>LOGS</Text>
            {(detail?.logs ?? []).slice(-8).map((log, index) => (
              <Text key={`${index}-${log}`} style={styles.modalMono}>
                {log}
              </Text>
            ))}
          </Card>

          <Card>
            <Text style={styles.sectionLabel}>TIMELINE</Text>
            {(detail?.timeline ?? []).slice(-10).map((entry, index) => (
              <Text key={String(index)} style={styles.modalMono}>
                {String(entry.type ?? "event")} · {String(entry.name ?? entry.message ?? "")}
              </Text>
            ))}
          </Card>
        </ScrollView>
      </View>
    </View>
  </Modal>
);

const styles = StyleSheet.create({
  hero: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 14,
    backgroundColor: "#f1f7ff",
  },
  kicker: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  heroTitle: {
    color: theme.text,
    fontSize: 26,
    fontWeight: "800",
    marginTop: 6,
  },
  heroText: {
    color: theme.textMuted,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 4,
  },
  heroBadge: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 999,
    backgroundColor: "rgba(44,107,237,0.12)",
  },
  heroBadgeText: {
    color: theme.primary,
    fontWeight: "700",
  },
  metricGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    marginTop: 14,
  },
  metricCard: {
    minWidth: 150,
    flexGrow: 1,
  },
  metricLabel: {
    color: theme.textMuted,
    fontSize: 12,
  },
  metricValue: {
    fontSize: 28,
    fontWeight: "800",
    marginTop: 8,
  },
  sectionLabel: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  laneRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    marginTop: 12,
  },
  laneTitle: {
    color: theme.text,
    fontWeight: "700",
  },
  laneText: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  barTrack: {
    width: 160,
    height: 10,
    borderRadius: 999,
    backgroundColor: theme.bgDeep,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 999,
  },
  boardTitle: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "800",
    marginTop: 18,
    marginBottom: 10,
  },
  board: {
    gap: 14,
    paddingBottom: 6,
  },
  column: {
    width: 300,
    gap: 10,
  },
  columnHead: {
    paddingHorizontal: 2,
  },
  columnTitle: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "800",
  },
  columnHint: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  emptyCard: {
    backgroundColor: "rgba(255,255,255,0.72)",
  },
  emptyText: {
    color: theme.textMuted,
  },
  taskCard: {
    gap: 8,
  },
  taskHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  },
  taskSprint: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: "700",
  },
  taskTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "700",
    lineHeight: 20,
  },
  taskMeta: {
    color: theme.textMuted,
    fontSize: 12,
  },
  progressTrack: {
    height: 8,
    borderRadius: 999,
    backgroundColor: theme.bgDeep,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: theme.primary,
  },
  statusChip: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 999,
  },
  statusChipText: {
    fontSize: 11,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(16,34,58,0.18)",
    justifyContent: "center",
    padding: 20,
  },
  modalCard: {
    maxHeight: "88%",
    borderRadius: 24,
    backgroundColor: "#ffffff",
    padding: 18,
    gap: 14,
  },
  modalHead: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },
  modalTitle: {
    color: theme.text,
    fontSize: 24,
    fontWeight: "800",
  },
  modalSubtitle: {
    color: theme.textMuted,
    fontSize: 14,
    lineHeight: 20,
    marginTop: 4,
  },
  modalText: {
    color: theme.text,
    fontSize: 13,
    lineHeight: 19,
    marginTop: 6,
  },
  modalMono: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 18,
    fontFamily: theme.fontMono,
    marginTop: 6,
  },
});
