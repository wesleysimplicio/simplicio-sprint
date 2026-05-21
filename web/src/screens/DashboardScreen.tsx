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
  review: { label: "Review", hint: "PR, evidencias e aprovacao" },
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

  const currentSprintMeta = [
    session.currentSprint?.portfolioName,
    session.currentSprint?.projectName,
    session.currentSprint?.teamName,
  ]
    .filter(Boolean)
    .join(" / ");

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

  if (loading) {
    return (
      <Screen chrome="app" eyebrow="Web 02 · Shell" title="SendSprint" subtitle="Carregando shell operacional local...">
        <ActivityIndicator color={theme.primary} style={{ marginTop: 48 }} />
      </Screen>
    );
  }

  if (!session.currentSprint) {
    return (
      <Screen
        chrome="app"
        eyebrow="Web 02 · Shell Pos-login"
        title="Pronto para orquestrar seu proximo sprint"
        subtitle="Conecte um provider, importe a sprint e depois aponte ao menos um repositorio local para liberar execucao."
      >
        <Card style={styles.centerHero}>
          <View style={styles.heroOrb}>
            <Text style={styles.heroOrbText}>{">"}</Text>
          </View>
          <Text style={styles.centerHeroTitle}>Nenhuma sprint ativa no shell web ainda</Text>
          <Text style={styles.centerHeroText}>
            O login do app ja foi validado. O proximo passo e escolher Jira ou Azure DevOps,
            importar a sprint e abrir o backlog interno do SendSprint.
          </Text>
          <Button title="Iniciar" onPress={() => nav.navigate("Provider")} icon=">" />
        </Card>

        <View style={styles.quickGrid}>
          <Card style={styles.quickCard} onPress={() => nav.navigate("ProjectSetup")}>
            <Text style={styles.quickLabel}>Configurar projeto</Text>
            <Text style={styles.quickValue}>Repositorios, papeis e branches</Text>
            <Text style={styles.quickLink}>Configurar agora</Text>
          </Card>
          <Card style={styles.quickCard} onPress={() => nav.navigate("Settings")}>
            <Text style={styles.quickLabel}>Conexoes</Text>
            <Text style={styles.quickValue}>Jira, Azure DevOps e GitHub</Text>
            <Text style={styles.quickLink}>Abrir conexoes</Text>
          </Card>
        </View>

        <View style={styles.statRow}>
          <StatPill label="Auth" value={session.appUser?.displayName ?? session.appUser?.email ?? "Operador local"} />
          <StatPill label="Provider padrao" value={providerLabel} />
          <StatPill label="Repositorios" value={String(session.projectSetup.repositories.length)} />
        </View>
      </Screen>
    );
  }

  return (
    <Screen
      chrome="app"
      eyebrow="Web 07 · Kanban / Web 09 · Live Run"
      title={session.currentSprint.sprintName}
      subtitle={
        currentSprintMeta
          ? `${currentSprintMeta} · backlog importado e pronto para despacho`
          : "Sprint importada e pronta para despacho"
      }
      scroll={false}
      actions={
        <View style={styles.headerPanel}>
          <Text style={styles.headerPanelValue}>{totals.running} running</Text>
          <Text style={styles.headerPanelMeta}>{providerLabel}</Text>
        </View>
      }
      footer={
        <View style={{ gap: 10 }}>
          <Button
            title="Abrir backlog"
            onPress={() => nav.navigate("SprintDetail", { sprintId: session.currentSprint?.sprintId ?? "" })}
          />
          <Button title="Configurar projeto" variant="secondary" onPress={() => nav.navigate("ProjectSetup")} />
          <Button title="Parametros e conexoes" variant="secondary" onPress={() => nav.navigate("Settings")} />
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
        <Card style={styles.activeHero}>
          <View style={{ flex: 1 }}>
            <Text style={styles.kicker}>ACTIVE DELIVERY CONTEXT</Text>
            <Text style={styles.activeHeroTitle}>{session.currentSprint.sprintName}</Text>
            <Text style={styles.activeHeroText}>
              {providerLabel}
              {currentSprintMeta ? ` · ${currentSprintMeta}` : ""}
            </Text>
          </View>
          <View style={styles.activeHeroRight}>
            <Text style={styles.activeHeroNumber}>{totals.total}</Text>
            <Text style={styles.activeHeroLabel}>runs mapeados</Text>
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
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.board}>
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
                        <Text style={styles.taskTitle}>{run.task ?? run.summary ?? "Task sem titulo"}</Text>
                        <Text style={styles.taskMeta}>{run.provider} · {run.autonomy_level}</Text>
                        <View style={styles.progressTrack}>
                          <View
                            style={[
                              styles.progressFill,
                              { width: `${Math.max(8, Math.round((run.progress ?? 0.1) * 100))}%` },
                            ]}
                          />
                        </View>
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

const MetricCard: React.FC<{
  label: string;
  value: string;
  accent?: "default" | "primary" | "success" | "danger";
}> = ({ label, value, accent = "default" }) => (
  <Card style={styles.metricCard}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text
      style={[
        styles.metricValue,
        accent === "primary" && { color: theme.primary },
        accent === "success" && { color: theme.success },
        accent === "danger" && { color: theme.danger },
      ]}
    >
      {value}
    </Text>
  </Card>
);

const StatPill: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.statPill}>
    <Text style={styles.statPillLabel}>{label}</Text>
    <Text style={styles.statPillValue}>{value}</Text>
  </View>
);

const StatusChip: React.FC<{
  text: string;
  tone: "default" | "success" | "danger";
}> = ({ text, tone }) => (
  <View
    style={[
      styles.statusChip,
      tone === "success" && styles.statusChipSuccess,
      tone === "danger" && styles.statusChipDanger,
    ]}
  >
    <Text
      style={[
        styles.statusChipText,
        tone === "success" && { color: theme.success },
        tone === "danger" && { color: theme.danger },
      ]}
    >
      {text}
    </Text>
  </View>
);

const RunDetailModal: React.FC<{
  detail: ControlPlaneRunDetail | null;
  onClose: () => void;
}> = ({ detail, onClose }) => (
  <Modal visible={Boolean(detail)} transparent animationType="fade" onRequestClose={onClose}>
    <View style={styles.modalBackdrop}>
      <View style={styles.modalCard}>
        <View style={styles.modalHead}>
          <View style={{ flex: 1 }}>
            <Text style={styles.modalTitle}>{detail?.run.task ?? detail?.run.run_id ?? "Run"}</Text>
            <Text style={styles.modalSubtitle}>{detail?.run.summary ?? "Sem resumo"}</Text>
          </View>
          <Button title="Fechar" variant="ghost" onPress={onClose} />
        </View>

        <ScrollView style={{ maxHeight: 480 }} showsVerticalScrollIndicator={false}>
          <Card style={styles.modalSection}>
            <Text style={styles.sectionLabel}>RUN</Text>
            <Text style={styles.modalBody}>Estado: {detail?.run.state ?? "-"}</Text>
            <Text style={styles.modalBody}>Provider: {detail?.run.provider ?? "-"}</Text>
            <Text style={styles.modalBody}>Branch: {detail?.run.branch ?? "-"}</Text>
          </Card>

          <Card style={styles.modalSection}>
            <Text style={styles.sectionLabel}>LOGS</Text>
            {(detail?.logs ?? []).length === 0 ? (
              <Text style={styles.modalBody}>Sem logs capturados.</Text>
            ) : (
              detail?.logs.map((line, index) => (
                <Text key={`${index}-${line}`} style={styles.modalMono}>
                  {line}
                </Text>
              ))
            )}
          </Card>
        </ScrollView>
      </View>
    </View>
  </Modal>
);

const resolveColumn = (run: ControlPlaneRunSummary): ColumnKey => {
  if (run.failed || run.state === "failed") return "blocked";
  if (run.state === "done") return "done";
  if ((run.last_step ?? 0) >= 8 || run.readiness_verdict === "needs_human_approval") return "review";
  if ((run.last_step ?? 0) >= 4) return "validate";
  if ((run.last_step ?? 0) >= 1 || run.state === "running") return "build";
  return "queued";
};

const chipTone = (run: ControlPlaneRunSummary): "default" | "success" | "danger" => {
  if (run.failed || run.state === "failed") return "danger";
  if (run.state === "done") return "success";
  return "default";
};

const styles = StyleSheet.create({
  centerHero: {
    minHeight: 180,
    alignItems: "center",
    justifyContent: "center",
    gap: 10,
    paddingVertical: 26,
  },
  heroOrb: {
    width: 50,
    height: 50,
    borderRadius: 25,
    backgroundColor: "rgba(44,107,237,0.10)",
    borderWidth: 1,
    borderColor: "rgba(44,107,237,0.18)",
    alignItems: "center",
    justifyContent: "center",
  },
  heroOrbText: {
    color: theme.primary,
    fontSize: 19,
    fontWeight: "800",
  },
  centerHeroTitle: {
    color: theme.text,
    fontSize: 17,
    lineHeight: 22,
    fontWeight: "800",
    textAlign: "center",
  },
  centerHeroText: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 17,
    textAlign: "center",
    maxWidth: 620,
  },
  quickGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 14,
  },
  quickCard: {
    flex: 1,
    minWidth: 280,
    minHeight: 76,
  },
  quickLabel: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "700",
  },
  quickValue: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 17,
    marginTop: 4,
  },
  quickLink: {
    color: theme.primary,
    fontSize: 13,
    fontWeight: "700",
    marginTop: 12,
  },
  statRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  statPill: {
    paddingHorizontal: 12,
    paddingVertical: 10,
    borderRadius: theme.radius,
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
    minWidth: 180,
  },
  statPillLabel: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  statPillValue: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
    marginTop: 6,
  },
  headerPanel: {
    paddingHorizontal: 14,
    paddingVertical: 12,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: "rgba(255,255,255,0.84)",
    minWidth: 140,
    alignItems: "flex-end",
  },
  headerPanelValue: {
    color: theme.primary,
    fontSize: 22,
    fontWeight: "800",
  },
  headerPanelMeta: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  activeHero: {
    backgroundColor: "#eef5ff",
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
  },
  kicker: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
  },
  activeHeroTitle: {
    color: theme.text,
    fontSize: 26,
    fontWeight: "800",
    marginTop: 4,
  },
  activeHeroText: {
    color: theme.textMuted,
    fontSize: 14,
    marginTop: 6,
  },
  activeHeroRight: {
    width: 140,
    alignItems: "flex-end",
  },
  activeHeroNumber: {
    color: theme.primary,
    fontSize: 32,
    fontWeight: "800",
  },
  activeHeroLabel: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 2,
  },
  metricGrid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    marginTop: 16,
  },
  metricCard: {
    flex: 1,
    minWidth: 180,
  },
  metricLabel: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 1.5,
    textTransform: "uppercase",
  },
  metricValue: {
    color: theme.text,
    fontSize: 26,
    fontWeight: "800",
    marginTop: 6,
  },
  sectionLabel: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "700",
    marginBottom: 6,
  },
  laneRow: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingVertical: 10,
  },
  laneTitle: {
    color: theme.text,
    fontSize: 12,
    fontWeight: "800",
  },
  laneText: {
    color: theme.textMuted,
    fontSize: 12,
    marginTop: 4,
  },
  barTrack: {
    width: 180,
    height: 8,
    borderRadius: 999,
    backgroundColor: "rgba(44,107,237,0.10)",
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
    gap: 12,
    paddingBottom: 8,
  },
  column: {
    width: 280,
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
    justifyContent: "space-between",
    alignItems: "center",
    gap: 10,
  },
  taskSprint: {
    color: theme.primary,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  taskTitle: {
    color: theme.text,
    fontSize: 14,
    fontWeight: "700",
    lineHeight: 20,
  },
  taskMeta: {
    color: theme.textMuted,
    fontSize: 12,
  },
  progressTrack: {
    height: 6,
    borderRadius: 999,
    backgroundColor: "rgba(44,107,237,0.10)",
    overflow: "hidden",
    marginTop: 2,
  },
  progressFill: {
    height: "100%",
    borderRadius: 999,
    backgroundColor: theme.primary,
  },
  statusChip: {
    paddingHorizontal: 10,
    paddingVertical: 4,
    borderRadius: 999,
    backgroundColor: "rgba(44,107,237,0.10)",
  },
  statusChipSuccess: {
    backgroundColor: "rgba(30,169,124,0.10)",
  },
  statusChipDanger: {
    backgroundColor: "rgba(207,81,97,0.10)",
  },
  statusChipText: {
    color: theme.primary,
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
  modalBody: {
    color: theme.text,
    fontSize: 13,
    lineHeight: 20,
  },
  modalMono: {
    color: theme.text,
    fontSize: 12,
    lineHeight: 18,
    fontFamily: theme.fontMono,
  },
});
