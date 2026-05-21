import React, { useEffect, useMemo, useState } from "react";
import {
  ActivityIndicator,
  RefreshControl,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { getApiErrorMessage } from "../api/client";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import type {
  ControlPlaneRunSummary,
  SprintDetail,
  TupleDashboardResponse,
  ValidationDashboardResponse,
  YoolDashboardResponse,
} from "../api/types";
import { useSession } from "../store/session";
import { theme } from "../theme";

export const ReportsScreen: React.FC = () => {
  const { api, session } = useSession();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);
  const [tuples, setTuples] = useState<TupleDashboardResponse | null>(null);
  const [yools, setYools] = useState<YoolDashboardResponse | null>(null);
  const [validations, setValidations] = useState<ValidationDashboardResponse | null>(null);
  const [detail, setDetail] = useState<SprintDetail | null>(null);

  const load = async (background = false) => {
    if (!background) setLoading(true);
    setError(null);
    try {
      const [runList, tupleState, yoolState, validationState, sprintDetail] = await Promise.all([
        api.listControlPlaneRuns(),
        api.getTupleDashboard(),
        api.getYoolDashboard(),
        api.getValidationDashboard(),
        session.currentSprint
          ? api.getSprint(session.currentSprint.sprintId, session.currentSprint.provider, {
              include_archived: true,
            })
          : Promise.resolve(null),
      ]);
      setRuns(runList);
      setTuples(tupleState);
      setYools(yoolState);
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
  }, [session.currentSprint?.sprintId, session.currentSprint?.provider]);

  const relevantRuns = useMemo(() => {
    if (!session.currentSprint) return runs;
    return runs.filter(
      (run) =>
        run.sprint_id === session.currentSprint?.sprintId &&
        String(run.provider) === String(session.currentSprint?.provider),
    );
  }, [runs, session.currentSprint]);

  const funnel = useMemo(() => {
    const counts: Record<string, number> = {
      backlog: 0,
      planning: 0,
      programming: 0,
      testing: 0,
      review: 0,
      awaiting_deploy: 0,
      blocked: 0,
    };
    for (const item of detail?.items ?? []) {
      const key = item.board_column ?? "backlog";
      counts[key] = (counts[key] ?? 0) + 1;
    }
    return counts;
  }, [detail?.items]);

  const topYools = useMemo(
    () =>
      [...(yools?.yools ?? [])]
        .sort((left, right) => right.total_invocations - left.total_invocations)
        .slice(0, 6),
    [yools?.yools],
  );

  if (loading) {
    return (
      <Screen
        chrome="app"
        eyebrow="Web 17 · Reports"
        title="Reports"
        subtitle="Carregando sinais de throughput, tuple activity e yool usage..."
      >
        <ActivityIndicator color={theme.primary} style={{ marginTop: 48 }} />
      </Screen>
    );
  }

  return (
    <Screen
      chrome="app"
      eyebrow="Web 17 · Reports"
      title="Relatorios operacionais"
      subtitle="Throughput da sprint, atividade de tuples, validacoes e uso dos yools que sustentam o shell local."
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
        contentContainerStyle={styles.scroll}
        showsVerticalScrollIndicator={false}
      >
        {error ? (
          <Card style={styles.errorCard}>
            <Text style={styles.kicker}>REPORT ERROR</Text>
            <Text style={styles.errorText}>{error}</Text>
          </Card>
        ) : null}

        <View style={styles.metrics}>
          <MetricCard label="Itens importados" value={String(detail?.items.length ?? 0)} />
          <MetricCard label="Arquivados" value={String(detail?.archived_count ?? 0)} accent="warning" />
          <MetricCard
            label="Runs concluidas"
            value={String(relevantRuns.filter((run) => run.state === "done").length)}
            accent="success"
          />
          <MetricCard
            label="Runs falhas"
            value={String(relevantRuns.filter((run) => run.failed).length)}
            accent="danger"
          />
        </View>

        <View style={styles.grid}>
          <Card style={styles.panel}>
            <Text style={styles.kicker}>DELIVERY FUNNEL</Text>
            {Object.entries(funnel).map(([label, value]) => (
              <View key={label} style={styles.row}>
                <Text style={styles.rowLabel}>{label}</Text>
                <Text style={styles.rowValue}>{String(value)}</Text>
              </View>
            ))}
          </Card>

          <Card style={styles.panel}>
            <Text style={styles.kicker}>TUPLE ACTIVITY</Text>
            <ReportRow label="Total tuples" value={String(tuples?.total_runs ?? 0)} />
            <ReportRow label="Active runs" value={String(tuples?.active_runs ?? 0)} />
            <ReportRow label="Failed runs" value={String(tuples?.failed_runs ?? 0)} />
            <ReportRow label="Validation events" value={String(validations?.total_events ?? 0)} />
            <ReportRow label="Registered contracts" value={String(yools?.registered_contracts ?? 0)} />
          </Card>
        </View>

        <Card>
          <Text style={styles.kicker}>TOP YOOLS</Text>
          {topYools.length === 0 ? (
            <Text style={styles.bodyText}>Nenhuma estatistica de yool foi registrada ainda.</Text>
          ) : (
            topYools.map((entry) => (
              <View key={entry.yool_id} style={styles.row}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.rowLabel}>{entry.yool_id}</Text>
                  <Text style={styles.bodyText}>
                    invocacoes={entry.total_invocations} · cache={Math.round(entry.cache_hit_rate * 100)}% · retries={entry.total_retries}
                  </Text>
                </View>
                <Text style={styles.rowValue}>{Math.round(entry.avg_duration_ms)} ms</Text>
              </View>
            ))
          )}
        </Card>

        <Card>
          <Text style={styles.kicker}>TELEMETRY NOTES</Text>
          <Text style={styles.bodyText}>
            Este slice Console + Web ja expone tuples, runs, validations e invocacoes de yool.
            Tokens, horas gastas e custo por modelo ainda nao estao instrumentados na telemetria local.
          </Text>
        </Card>
      </ScrollView>
    </Screen>
  );
};

const MetricCard: React.FC<{
  label: string;
  value: string;
  accent?: "default" | "success" | "warning" | "danger";
}> = ({ label, value, accent = "default" }) => (
  <Card style={styles.metricCard}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text
      style={[
        styles.metricValue,
        accent === "success" && { color: theme.success },
        accent === "warning" && { color: theme.warning },
        accent === "danger" && { color: theme.danger },
      ]}
    >
      {value}
    </Text>
  </Card>
);

const ReportRow: React.FC<{ label: string; value: string }> = ({ label, value }) => (
  <View style={styles.row}>
    <Text style={styles.rowLabel}>{label}</Text>
    <Text style={styles.rowValue}>{value}</Text>
  </View>
);

const styles = StyleSheet.create({
  scroll: {
    gap: 12,
    paddingBottom: 24,
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
  grid: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
  },
  panel: {
    flex: 1,
    minWidth: 320,
  },
  kicker: {
    color: theme.primary,
    fontSize: 11,
    letterSpacing: 2,
    fontWeight: "800",
    marginBottom: 8,
  },
  row: {
    flexDirection: "row",
    justifyContent: "space-between",
    gap: 12,
    paddingVertical: 10,
    borderTopWidth: 1,
    borderTopColor: theme.border,
  },
  rowLabel: {
    color: theme.text,
    fontSize: 13,
    fontWeight: "700",
  },
  rowValue: {
    color: theme.textMuted,
    fontSize: 12,
    fontFamily: theme.fontMono,
  },
  bodyText: {
    color: theme.textMuted,
    fontSize: 13,
    lineHeight: 20,
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
});
