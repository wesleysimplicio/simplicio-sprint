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
  queued: { label: "Queue", hint: "Aguardando setup ou despacho" },
  build: { label: "Build", hint: "Mapeamento, planejamento e codigo" },
  validate: { label: "Validate", hint: "Lint, testes e seguranca" },
  review: { label: "Review", hint: "PR, evidencias e aprovacao humana" },
  done: { label: "Done", hint: "Prontas para deploy" },
  blocked: { label: "Blocked", hint: "Falhas ou dependencias pendentes" },
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

  const currentSprintMeta = [
    session.currentSprint?.portfolioName,
    session.currentSprint?.projectName,
    session.currentSprint?.teamName,
  ]
    .filter(Boolean)
    .join(" / ");

  if (loading) {
    return (
      <Screen title="SendSprint" subtitle="Carregando shell operacional local...">
        <ActivityIndicator color={theme.primary} style={{ marginTop: 48 }} />
      </Screen>
    );
  }

  if (!session.currentSprint) {
    return (
      <Screen
        title="SendSprint"
        subtitle="Entre, escolha a origem do trabalho e importe a sprint para liberar o backlog interno."
        footer={
          <View style={{ gap: 10 }}>
            <Button title="Iniciar" onPress={() => nav.navigate("Provider")} />
            <Button
              title="Setup do projeto"
              variant="secondary"
              onPress={() => nav.navigate("ProjectSetup")}
            />
            <Button
              title="Parametros e conexoes"
              variant="secondary"
              onPress={() => nav.navigate("Settings")}
            />
          </View>
        }
      >
        <Card style={styles.heroCard}>
          <Text style={styles.kicker}>CHAT-FIRST DELIVERY SHELL</Text>
          <Text style={styles.heroTitle}>Tudo vazio ate conectar uma sprint real</Text>
          <Text style={styles.heroText}>
            O login do app ja foi validado. A proxima etapa e escolher Jira ou Azure DevOps e
            importar a sprint para o backlog Kanban do SendSprint.
          </Text>
        </Card>

        <View style={styles.emptyGrid}>
          <Card style={styles.emptyCell}>
            <Text style={styles.emptyLabel}>AUTH</Text>
            <Text style={styles.emptyValue}>
              {session.appUser?.displayName ?? session.appUser?.email ?? "Usuario local"}
            </Text>
            <Text style={styles.emptyHint}>Todos ativos nesta fase local.</Text>
          </Card>
          <Card style={styles.emptyCell}>
            <Text style={styles.emptyLabel}>PROVIDER PADRAO</Text>
            <Text style={styles.emptyValue}>{providerLabel}</Text>
            <Text style={styles.emptyHint}>Pode ser trocado ao iniciar.</Text>
          </Card>
          <Card style={styles.emptyCell}>
            <Text style={styles.emptyLabel}>REPOSITORIOS</Text>
            <Text style={styles.emptyValue}>{session.projectSetup.repositories.length}</Text>
            <Text style={styles.emptyHint}>
              Configure paths locais para habilitar play por task.
            </Text>
          </Card>
        </View>

        <Card style={styles.todoCard}>
          <Text style={styles.todoTitle}>Fluxo esperado agora</Text>
          <Text style={styles.todoText}>1. Clique em Iniciar.</Text>
          <Text style={styles.todoText}>2. Conecte Jira ou Azure DevOps.</Text>
          <Text style={styles.todoText}>3. Importe a sprint e abra o backlog.</Text>
          <Text style={styles.todoText}>
            4. Configure o repositorio do projeto para liberar play por task ou play all.
          </Text>
        </Card>
      </Screen>
    );
  }

  return (
    <Screen
      title={session.currentSprint.sprintName}
      subtitle={
        currentSprintMeta
          ? `${currentSprintMeta} · backlog importado e pronto para despacho`
          : "Sprint importada e pronta para despacho"
      }
      footer={
        <View style={{ gap: 10 }}>
          <Button
            title="Abrir backlog"
            onPress={() =>
              nav.navigate("SprintDetail", { sprintId: session.currentSprint?.sprintId ?? "" })
            }
          />
          <Button
            title="Setup do projeto"
            variant="secondary"
            onPress={() => nav.navigate("ProjectSetup")}
          />
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
        <Card style={styles.heroCard}>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>ACTIVE DELIVERY CONTEXT</Text>
            <Text style={styles.heroTitle}>{session.currentSprint.sprintName}</Text>
            <Text style={styles.heroText}>
              {providerLabel}
              {currentSprintMeta ? ` · ${currentSprintMeta}` : ""}
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
          <MetricCard label="Prontas" value={String(totals.done)} accent="success" />
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

        <Text style={styles.boardTitle}>RUNS EM CURSO</Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={styles.board}
        >
          {(Object.keys(COLUMN_META) as ColumnKey[]).map((column) => (
            <View key={column} style={styles.column}>
              <View style={styles.columnHead}>
                <Text style={styles.columnTitle}>{COLUMN_META[column].label}</Text>
                <Text style={styles.columnHint}>{COLUMN_META[column].hint}</Text>
              </View>
              <View style={{ gap: 10 }}>
                {grouped[column].length === 0 ? (
                  <Card style={styles.emptyRunCard}>
                    <Text style={styles.emptyRunText}>Sem runs nesta etapa.</Text>
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
                              {
                                width: `${Math.max(8, Math.round((run.progress ?? 0.1) * 100))}%`,
                              },
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

      <RunDetailModal detail={selected} onClose={() => setSelected(null)} />
    </Screen>
  );
};

const resolveColumn = (run: ControlPlaneRunSummary): ColumnKey => {
  if (run.failed || run.state === "failed") return "blocked";
  if (run.state === "done") return "done";
  if ((run.last_step ?? 0) >= 9 || run.readiness_verdict === "needs_human_approval") {
    return "review";
  }
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

        <ScrollView style={{ maxHeight: 420 }} showsVerticalScrollIndicator={false}>
          {detail?.quality_gate ? (
            <Card style={styles.modalSection}>
              <Text style={styles.modalSectionTitle}>QUALITY GATE</Text>
              <Text style={styles.modalBody}>{detail.quality_gate.verdict}</Text>
              {detail.quality_gate.checks.map((check) => (
                <Text key={check.check_name} style={styles.modalList}>
                  {check.check_name}: {check.passed ? "ok" : "falhou"}
                </Text>
              ))}
            </Card>
          ) : null}

          <Card style={styles.modalSection}>
            <Text style={styles.modalSectionTitle}>LOGS</Text>
            {(detail?.logs ?? []).length === 0 ? (
              <Text style={styles.modalBody}>Sem logs capturados ainda.</Text>
            ) : (
              detail?.logs.map((log, index) => (
                <Text key={`${index}-${log}`} style={styles.modalMono}>
                  {log}
                </Text>
              ))
            )}
          </Card>
        </ScrollView>
      </View>
    </View>
  </Modal>
);

const styles = StyleSheet.create({
  heroCard: {
    backgroundColor: "#eef5ff",
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },
  kicker: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
  },
  heroTitle: {
    color: theme.text,
    fontSize: 28,
    lineHeight: 34,
    fontWeight: "800",
    marginTop: 4,
  },
  heroText: {
    color: theme.textMuted,
    fontSize: 14,
    lineHeight: 21,
    marginTop: 4,
  },
  heroBadge: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "rgba(44,107,237,0.12)",
  },
  heroBadgeText: {
    color: theme.primary,
    fontSize: 12,
    fontWeight: "700",
  },
  emptyGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  emptyCell: {
    flexBasis: "30%",
    minWidth: 180,
    gap: 4,
  },
  emptyLabel: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
  },
  emptyValue: {
    color: theme.text,
    fontSize: 18,
    fontWeight: "800",
  },
  emptyHint: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 18,
  },
  todoCard: {
    backgroundColor: theme.surfaceAlt,
  },
  todoTitle: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "800",
  },
  todoText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 20,
  },
  metricGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    marginTop: 14,
  },
  metricCard: {
    minWidth: 150,
    flex: 1,
  },
  metricLabel: {
    color: theme.textMuted,
    fontSize: 12,
  },
  metricValue: {
    fontSize: 28,
    fontWeight: "800",
  },
  sectionLabel: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: 8,
  },
  laneRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    marginTop: 8,
  },
  laneTitle: {
    color: theme.text,
    fontWeight: "700",
    fontSize: 13,
  },
  laneText: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  barTrack: {
    width: 120,
    height: 8,
    borderRadius: 999,
    backgroundColor: theme.surfaceAlt,
    overflow: "hidden",
  },
  barFill: {
    height: "100%",
    borderRadius: 999,
  },
  boardTitle: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
    marginTop: 18,
    marginBottom: 8,
  },
  board: {
    gap: 12,
    paddingBottom: 12,
  },
  column: {
    width: 272,
    gap: 10,
  },
  columnHead: {
    paddingHorizontal: 4,
  },
  columnTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "800",
  },
  columnHint: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  emptyRunCard: {
    backgroundColor: theme.surfaceAlt,
  },
  emptyRunText: {
    color: theme.textMuted,
    fontSize: 12,
  },
  taskCard: {
    gap: 8,
  },
  taskHead: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  taskSprint: {
    color: theme.primary,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  taskTitle: {
    color: theme.text,
    fontSize: 15,
    fontWeight: "700",
  },
  taskMeta: {
    color: theme.textMuted,
    fontSize: 12,
  },
  progressTrack: {
    height: 8,
    borderRadius: 999,
    backgroundColor: theme.surfaceAlt,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    backgroundColor: theme.primary,
    borderRadius: 999,
  },
  statusChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
  },
  statusChipText: {
    fontSize: 11,
    fontWeight: "800",
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: "rgba(14, 24, 36, 0.35)",
    justifyContent: "center",
    padding: 20,
  },
  modalCard: {
    backgroundColor: theme.bg,
    borderRadius: theme.radius,
    borderWidth: 1,
    borderColor: theme.border,
    padding: 16,
    gap: 12,
  },
  modalHead: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
  },
  modalTitle: {
    color: theme.text,
    fontSize: 20,
    fontWeight: "800",
  },
  modalSubtitle: {
    color: theme.textMuted,
    fontSize: 13,
    marginTop: 4,
  },
  modalSection: {
    marginBottom: 12,
  },
  modalSectionTitle: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: 4,
  },
  modalBody: {
    color: theme.text,
    fontSize: 13,
    lineHeight: 20,
  },
  modalList: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 18,
  },
  modalMono: {
    color: theme.text,
    fontSize: 12,
    lineHeight: 18,
    fontFamily: theme.fontMono,
  },
});
