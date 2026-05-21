import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  Pressable,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { getApiErrorMessage } from "../api/client";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type {
  AgentDashboardResponse,
  ColumnKey,
  ControlPlaneRunSummary,
  SprintDetail,
  SprintItem,
  ValidationDashboardResponse,
} from "../api/types";
import { useSession } from "../store/session";
import { theme } from "../theme";

type EmployeeRollup = {
  key: string;
  label: string;
  email?: string | null;
  totalItems: number;
  activeItems: number;
  reviewItems: number;
  blockedItems: number;
  latestMove?: string | null;
};

type ManagerTab = "team" | "tasks" | "runs" | "alerts";

export const ManagerScreen: React.FC = () => {
  const { api, session } = useSession();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);
  const [agents, setAgents] = useState<AgentDashboardResponse | null>(null);
  const [validations, setValidations] = useState<ValidationDashboardResponse | null>(null);
  const [detail, setDetail] = useState<SprintDetail | null>(null);
  const [tab, setTab] = useState<ManagerTab>("team");
  const [query, setQuery] = useState("");

  const load = async (background = false) => {
    if (!background) setLoading(true);
    setError(null);
    try {
      const [runList, agentState, validationState, sprintDetail] = await Promise.all([
        api.listControlPlaneRuns(),
        api.getAgentDashboard(),
        api.getValidationDashboard(),
        session.currentSprint
          ? api.getSprint(session.currentSprint.sprintId, session.currentSprint.provider, {
              include_archived: true,
            })
          : Promise.resolve(null),
      ]);
      setRuns(runList);
      setAgents(agentState);
      setValidations(validationState);
      setDetail(sprintDetail);
    } catch (nextError) {
      setError(getApiErrorMessage(nextError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
  }, [session.currentSprint?.provider, session.currentSprint?.sprintId]);

  const relevantRuns = useMemo(() => {
    if (!session.currentSprint) return runs;
    return runs.filter(
      (run) =>
        run.sprint_id === session.currentSprint?.sprintId &&
        String(run.provider) === String(session.currentSprint?.provider),
    );
  }, [runs, session.currentSprint]);

  const latestRunByItem = useMemo(() => {
    const map = new Map<string, ControlPlaneRunSummary>();
    for (const run of relevantRuns) {
      for (const key of run.item_keys ?? []) {
        const current = map.get(key);
        if (!current || compareRunAge(run, current) > 0) {
          map.set(key, run);
        }
      }
    }
    return map;
  }, [relevantRuns]);

  const employeeRows = useMemo<EmployeeRollup[]>(() => {
    const base = new Map<string, EmployeeRollup>();
    for (const item of detail?.items ?? []) {
      const label = item.assignee || item.assignee_email || "Unassigned";
      const key = (item.assignee_email || item.assignee || "unassigned").toLowerCase();
      const current =
        base.get(key) ??
        ({
          key,
          label,
          email: item.assignee_email ?? null,
          totalItems: 0,
          activeItems: 0,
          reviewItems: 0,
          blockedItems: 0,
          latestMove: item.board_updated_by ?? null,
        } satisfies EmployeeRollup);
      current.totalItems += 1;
      const column = resolveItemColumn(item, latestRunByItem.get(item.key));
      if (column === "blocked") current.blockedItems += 1;
      if (column === "review" || column === "awaiting_deploy") current.reviewItems += 1;
      if (column === "planning" || column === "programming" || column === "testing") current.activeItems += 1;
      if (item.board_updated_by) current.latestMove = item.board_updated_by;
      base.set(key, current);
    }

    if (base.size === 0 && session.appUser) {
      return [
        {
          key: session.appUser.email.toLowerCase(),
          label: session.appUser.displayName || session.appUser.email,
          email: session.appUser.email,
          totalItems: 0,
          activeItems: 0,
          reviewItems: 0,
          blockedItems: 0,
          latestMove: "Nenhum item importado nesta sprint",
        },
      ];
    }

    const normalizedQuery = query.trim().toLowerCase();
    return Array.from(base.values())
      .filter((row) =>
        !normalizedQuery
          ? true
          : [row.label, row.email, row.latestMove].filter(Boolean).some((value) =>
              String(value).toLowerCase().includes(normalizedQuery),
            ),
      )
      .sort((left, right) => right.totalItems - left.totalItems);
  }, [detail?.items, latestRunByItem, query, session.appUser]);

  const approvalsPending = useMemo(
    () =>
      (detail?.items ?? []).filter((item) => {
        const column = resolveItemColumn(item, latestRunByItem.get(item.key));
        return column === "review" || column === "awaiting_deploy";
      }).length,
    [detail?.items, latestRunByItem],
  );

  const blockedItems = useMemo(
    () =>
      (detail?.items ?? []).filter(
        (item) => resolveItemColumn(item, latestRunByItem.get(item.key)) === "blocked",
      ).length,
    [detail?.items, latestRunByItem],
  );

  const alertItems = useMemo(() => {
    const list: string[] = [];
    if (blockedItems > 0) list.push(`${blockedItems} item(ns) bloqueados aguardando remocao de impedimento.`);
    if (approvalsPending > 0) list.push(`${approvalsPending} item(ns) aguardando review humana ou deploy.`);
    if ((validations?.lanes ?? []).some((lane) => lane.status === "failed")) {
      list.push("Uma ou mais validation lanes terminaram em failed.");
    }
    if ((agents?.total_active_runs ?? 0) > 3) list.push("Mais de 3 runs ativas no workspace local.");
    return list;
  }, [agents?.total_active_runs, approvalsPending, blockedItems, validations?.lanes]);

  if (loading) {
    return (
      <Screen
        chrome="app"
        eyebrow="Web 13 - Manager Console"
        title="Manager console"
        subtitle="Carregando atividade de operadores, runs e validacoes..."
      >
        <ActivityIndicator color={theme.primary} style={{ marginTop: 48 }} />
      </Screen>
    );
  }

  return (
    <Screen
      chrome="app"
      eyebrow="Web 13 - Manager Console"
      title="Visao do gerente"
      subtitle="Panorama do sprint ativo, operadores locais, lanes de validacao e aprovacoes pendentes."
      scroll={false}
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
        contentContainerStyle={styles.scroll}
      >
        {error ? (
          <Card style={styles.errorCard}>
            <Text style={styles.kicker}>MANAGER SIGNAL</Text>
            <Text style={styles.errorText}>{error}</Text>
          </Card>
        ) : null}

        <View style={styles.toolbar}>
          <View style={styles.tabRow}>
            {[
              ["team", "Minha equipe"],
              ["tasks", "Status das tarefas"],
              ["runs", "Execucoes recentes"],
              ["alerts", "Alertas"],
            ].map(([value, label]) => (
              <Pressable
                key={value}
                onPress={() => setTab(value as ManagerTab)}
                style={[styles.tab, tab === value && styles.tabActive]}
              >
                <Text style={[styles.tabText, tab === value && styles.tabTextActive]}>{label}</Text>
              </Pressable>
            ))}
          </View>
          <TextInput
            value={query}
            onChangeText={setQuery}
            placeholder="Buscar colaborador ou sinal"
            placeholderTextColor={theme.textMuted}
            style={styles.searchInput}
          />
        </View>

        <View style={styles.metrics}>
          <MetricCard label="Operadores visiveis" value={String(employeeRows.length)} />
          <MetricCard
            label="Runs ativas"
            value={String(relevantRuns.filter((run) => run.state === "running").length)}
            accent="primary"
          />
          <MetricCard label="Aprovacoes pendentes" value={String(approvalsPending)} accent="warning" />
          <MetricCard label="Itens bloqueados" value={String(blockedItems)} accent="danger" />
        </View>

        {tab === "team" || tab === "tasks" ? (
          <View style={styles.split}>
            <Card style={styles.primaryPanel}>
              <Text style={styles.kicker}>
                {tab === "team" ? "TEAM ACTIVITY" : "TASK OWNERSHIP"}
              </Text>
              {employeeRows.map((row) => (
                <View key={row.key} style={styles.employeeRow}>
                  <View style={{ flex: 1 }}>
                    <Text style={styles.employeeName}>{row.label}</Text>
                    <Text style={styles.employeeMeta}>
                      {row.email ?? "sem email"} - ultima alteracao {row.latestMove ?? "nao registrada"}
                    </Text>
                  </View>
                  <View style={styles.employeeStats}>
                    <Text style={styles.employeeStat}>{row.totalItems} itens</Text>
                    <Text style={styles.employeeStat}>{row.activeItems} ativos</Text>
                    <Text style={styles.employeeStat}>{row.reviewItems} review/deploy</Text>
                    <Text style={[styles.employeeStat, row.blockedItems > 0 && { color: theme.danger }]}>
                      {row.blockedItems} bloqueados
                    </Text>
                  </View>
                </View>
              ))}
            </Card>

            <View style={styles.sideStack}>
              <Card>
                <Text style={styles.kicker}>VALIDATION LANES</Text>
                {(validations?.lanes ?? []).map((lane) => (
                  <View key={lane.lane} style={styles.inlineRow}>
                    <Text style={styles.inlineLabel}>{lane.lane.toUpperCase()}</Text>
                    <Text style={styles.inlineValue}>
                      {lane.status} - {lane.events_count} eventos
                    </Text>
                  </View>
                ))}
              </Card>

              <Card>
                <Text style={styles.kicker}>AGENT RUNTIMES</Text>
                {(agents?.agents ?? []).slice(0, 5).map((agent) => (
                  <View key={agent.key} style={styles.inlineRow}>
                    <Text style={styles.inlineLabel}>{agent.name}</Text>
                    <Text style={styles.inlineValue}>
                      {agent.runtime} - {agent.capabilities.length} capacidades
                    </Text>
                  </View>
                ))}
              </Card>
            </View>
          </View>
        ) : null}

        {tab === "runs" ? (
          <Card>
            <Text style={styles.kicker}>RECENT RUNS</Text>
            {relevantRuns.slice(0, 10).map((run) => (
              <View key={run.run_id} style={styles.inlineRow}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.inlineLabel}>{run.run_id.slice(0, 12)}</Text>
                  <Text style={styles.employeeMeta}>
                    {run.state} - step {run.last_step ?? 0} - {run.item_keys.length} itens
                  </Text>
                </View>
                <Text style={styles.inlineValue}>{run.started_at?.slice(0, 19) ?? "-"}</Text>
              </View>
            ))}
          </Card>
        ) : null}

        {tab === "alerts" ? (
          <Card>
            <Text style={styles.kicker}>ALERT FEED</Text>
            {alertItems.length === 0 ? (
              <Text style={styles.emptyText}>Nenhum alerta operacional forte no momento.</Text>
            ) : (
              alertItems.map((item) => (
                <Text key={item} style={styles.alertText}>
                  - {item}
                </Text>
              ))
            )}
          </Card>
        ) : null}
      </ScrollView>
    </Screen>
  );
};

const compareRunAge = (left: ControlPlaneRunSummary, right: ControlPlaneRunSummary): number => {
  const leftValue = left.finished_at ?? left.started_at ?? "";
  const rightValue = right.finished_at ?? right.started_at ?? "";
  return leftValue.localeCompare(rightValue);
};

const resolveRunColumn = (run?: ControlPlaneRunSummary): ColumnKey | null => {
  if (!run) return null;
  if (run.failed || run.state === "failed") return "blocked";
  if (run.state === "done") return "awaiting_deploy";
  if ((run.last_step ?? 0) >= 8 || run.readiness_verdict === "needs_human_approval") return "review";
  if ((run.last_step ?? 0) >= 4) return "testing";
  if ((run.last_step ?? 0) >= 3) return "programming";
  if ((run.last_step ?? 0) >= 1 || run.state === "running") return "planning";
  return null;
};

const resolveItemColumn = (item: SprintItem, run?: ControlPlaneRunSummary): ColumnKey => {
  const runColumn = resolveRunColumn(run);
  if (runColumn) return runColumn;
  if (item.board_column) return item.board_column;
  const status = item.status.toLowerCase();
  if (status.includes("block")) return "blocked";
  if (status.includes("review") || status.includes("qa")) return "review";
  if (status.includes("test")) return "testing";
  if (status.includes("progress") || status.includes("doing") || status.includes("coding")) return "programming";
  if (status.includes("plan") || status.includes("analysis")) return "planning";
  if (status.includes("deploy") || status.includes("ready")) return "awaiting_deploy";
  return "backlog";
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  accent?: "default" | "primary" | "warning" | "danger";
}> = ({ label, value, accent = "default" }) => (
  <Card style={styles.metricCard}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text
      style={[
        styles.metricValue,
        accent === "primary" && { color: theme.primary },
        accent === "warning" && { color: theme.warning },
        accent === "danger" && { color: theme.danger },
      ]}
    >
      {value}
    </Text>
  </Card>
);

const styles = StyleSheet.create({
  scroll: {
    gap: 12,
    paddingBottom: 24,
  },
  toolbar: {
    gap: 10,
  },
  tabRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  tab: {
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surfaceAlt,
  },
  tabActive: {
    backgroundColor: "rgba(44,107,237,0.10)",
    borderColor: "rgba(44,107,237,0.24)",
  },
  tabText: {
    color: theme.textMuted,
    fontSize: 12,
    fontWeight: "700",
  },
  tabTextActive: {
    color: theme.primary,
  },
  searchInput: {
    backgroundColor: theme.surface,
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radius,
    paddingHorizontal: 14,
    paddingVertical: 12,
    color: theme.text,
    fontSize: 14,
  },
  metrics: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  metricCard: {
    flex: 1,
    minWidth: 180,
  },
  metricLabel: {
    color: theme.textMuted,
    fontSize: 11,
    letterSpacing: 2,
    textTransform: "uppercase",
  },
  metricValue: {
    color: theme.text,
    fontSize: 28,
    fontWeight: "800",
    marginTop: 6,
  },
  split: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  primaryPanel: {
    flex: 1,
    minWidth: 420,
  },
  sideStack: {
    width: 360,
    minWidth: 320,
    gap: 12,
  },
  kicker: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
    marginBottom: 8,
  },
  employeeRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 12,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  employeeName: {
    color: theme.text,
    fontSize: 16,
    fontWeight: "700",
  },
  employeeMeta: {
    color: theme.textMuted,
    fontSize: 12,
    lineHeight: 18,
    marginTop: 4,
  },
  employeeStats: {
    alignItems: "flex-end",
    gap: 4,
  },
  employeeStat: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  inlineRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  inlineLabel: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
  },
  inlineValue: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  errorCard: {
    backgroundColor: "rgba(207,81,97,0.08)",
    borderColor: "rgba(207,81,97,0.22)",
  },
  errorText: {
    color: theme.danger,
    fontSize: 13,
    lineHeight: 20,
  },
  emptyText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 20,
  },
  alertText: {
    color: theme.text,
    fontSize: 13,
    lineHeight: 20,
    marginTop: 4,
  },
});
