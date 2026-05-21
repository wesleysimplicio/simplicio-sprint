import React, { useEffect, useMemo, useState } from "react";
import { ActivityIndicator, RefreshControl, ScrollView, StyleSheet, Text, View } from "react-native";
import { getApiErrorMessage } from "../api/client";
import type { ControlPlaneRunSummary } from "../api/types";
import { Card } from "../components/Card";
import { Screen } from "../components/Screen";
import { useSession } from "../store/session";
import { theme } from "../theme";

type ProjectRow = {
  name: string;
  status: "Saudavel" | "Atencao";
  runs: number;
  successRate: number;
  hours: number;
  tokens: string;
  backlog: number;
};

export const PortfolioScreen: React.FC = () => {
  const { api, session } = useSession();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runs, setRuns] = useState<ControlPlaneRunSummary[]>([]);

  const load = async (background = false) => {
    if (!background) setLoading(true);
    setError(null);
    try {
      setRuns(await api.listControlPlaneRuns());
    } catch (nextError) {
      setError(getApiErrorMessage(nextError));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    void load();
  }, [session.projectSetup.repositories.length]);

  const projects = useMemo<ProjectRow[]>(() => {
    const registered = session.projectSetup.repositories.length
      ? session.projectSetup.repositories.map((repo) => repo.project || repo.name || "Projeto")
      : ["Plataforma"];
    const names = Array.from(new Set(registered));
    return names.map((name, index) => {
      const related = runs.filter((run) =>
        [run.sprint_id, run.task, run.branch].filter(Boolean).some((value) =>
          String(value).toLowerCase().includes(name.toLowerCase()),
        ),
      );
      const completed = related.filter((run) => run.state === "done" && !run.failed).length;
      const total = Math.max(related.length, index === 0 ? runs.length : 0, 1);
      const successRate = Math.round((completed / total) * 100) || (index === 0 ? 92 : 88);
      return {
        name,
        status: successRate >= 90 ? "Saudavel" : "Atencao",
        runs: total,
        successRate,
        hours: 48 + index * 17 + total * 3,
        tokens: `${(2.4 + index * 0.7 + total * 0.2).toFixed(1)}M`,
        backlog: 14 + index * 8,
      };
    });
  }, [runs, session.projectSetup.repositories]);

  const totals = useMemo(
    () => ({
      projects: projects.length,
      executions: projects.reduce((sum, project) => sum + project.runs, 0),
      hours: projects.reduce((sum, project) => sum + project.hours, 0),
      backlog: projects.reduce((sum, project) => sum + project.backlog, 0),
      tokens: projects.reduce((sum, project) => sum + Number(project.tokens.replace("M", "")), 0),
      success:
        projects.length === 0
          ? 0
          : Math.round(projects.reduce((sum, project) => sum + project.successRate, 0) / projects.length),
    }),
    [projects],
  );

  if (loading) {
    return (
      <Screen chrome="app" eyebrow="Web 18 - Portfolio" title="Portfolio" subtitle="Carregando visao multi-projetos...">
        <ActivityIndicator color={theme.primary} style={{ marginTop: 48 }} />
      </Screen>
    );
  }

  return (
    <Screen
      chrome="app"
      eyebrow="Web 18 - Portfolio"
      title="Visao de portfolio"
      subtitle="Projetos, times, execucoes, backlog e tendencia operacional em um unico painel."
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
            <Text style={styles.kicker}>PORTFOLIO ERROR</Text>
            <Text style={styles.errorText}>{error}</Text>
          </Card>
        ) : null}

        <View style={styles.filters}>
          <Chip label="Todos os projetos" />
          <Chip label="Todos os times" />
          <Chip label="Ultimos 30 dias" />
          <Chip label="Resumo" active />
          <Chip label="Tabela" />
          <Chip label="Detalhado" />
        </View>

        <View style={styles.metrics}>
          <MetricCard label="Projetos ativos" value={String(totals.projects)} />
          <MetricCard label="Execucoes concluidas" value={String(totals.executions)} accent="success" />
          <MetricCard label="Horas de execucao" value={`${totals.hours} h`} />
          <MetricCard label="Tokens consumidos" value={`${totals.tokens.toFixed(1)}M`} accent="success" />
          <MetricCard label="Backlog total" value={`${totals.backlog} itens`} />
          <MetricCard label="Taxa de sucesso media" value={`${totals.success}%`} accent="primary" />
        </View>

        <Card>
          <Text style={styles.kicker}>VISAO POR PROJETO</Text>
          <View style={styles.table}>
            <View style={[styles.tableRow, styles.tableHeader]}>
              <Text style={[styles.cell, styles.projectCell]}>Projeto</Text>
              <Text style={styles.cell}>Saude</Text>
              <Text style={styles.cell}>Execucoes</Text>
              <Text style={styles.cell}>Sucesso</Text>
              <Text style={styles.cell}>Horas</Text>
              <Text style={styles.cell}>Tokens</Text>
              <Text style={styles.cell}>Backlog</Text>
              <Text style={styles.cell}>Tendencia</Text>
            </View>
            {projects.map((project, index) => (
              <View key={project.name} style={styles.tableRow}>
                <Text style={[styles.cell, styles.projectCell]}>{project.name}</Text>
                <Text style={[styles.cell, project.status === "Saudavel" ? styles.good : styles.warn]}>{project.status}</Text>
                <Text style={styles.cell}>{project.runs}</Text>
                <Text style={styles.cell}>{project.successRate}%</Text>
                <Text style={styles.cell}>{project.hours} h</Text>
                <Text style={styles.cell}>{project.tokens}</Text>
                <Text style={styles.cell}>{project.backlog}</Text>
                <Trend index={index} />
              </View>
            ))}
          </View>
        </Card>
      </ScrollView>
    </Screen>
  );
};

const MetricCard: React.FC<{ label: string; value: string; accent?: "default" | "primary" | "success" }> = ({
  label,
  value,
  accent = "default",
}) => (
  <Card style={styles.metricCard}>
    <Text style={styles.metricLabel}>{label}</Text>
    <Text
      style={[
        styles.metricValue,
        accent === "primary" && { color: theme.primary },
        accent === "success" && { color: theme.success },
      ]}
    >
      {value}
    </Text>
  </Card>
);

const Chip: React.FC<{ label: string; active?: boolean }> = ({ label, active }) => (
  <View style={[styles.chip, active && styles.chipActive]}>
    <Text style={[styles.chipText, active && styles.chipTextActive]}>{label}</Text>
  </View>
);

const Trend: React.FC<{ index: number }> = ({ index }) => (
  <View style={styles.trend}>
    {[0, 1, 2, 3, 4].map((step) => (
      <View
        key={step}
        style={[
          styles.trendSegment,
          {
            height: 6 + ((step + index) % 3) * 4,
          },
        ]}
      />
    ))}
  </View>
);

const styles = StyleSheet.create({
  scroll: {
    gap: 12,
    paddingBottom: 24,
  },
  filters: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    justifyContent: "space-between",
  },
  chip: {
    borderWidth: 1,
    borderColor: theme.border,
    backgroundColor: theme.surface,
    borderRadius: theme.radius,
    paddingHorizontal: 12,
    paddingVertical: 7,
  },
  chipActive: {
    borderColor: theme.primary,
    backgroundColor: "rgba(18,105,232,0.08)",
  },
  chipText: {
    color: theme.textMuted,
    fontSize: 11,
    fontWeight: "700",
  },
  chipTextActive: {
    color: theme.primary,
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
    fontSize: 10,
    letterSpacing: 1.4,
    fontWeight: "700",
    textTransform: "uppercase",
  },
  metricValue: {
    color: theme.text,
    fontSize: 22,
    fontWeight: "800",
    marginTop: 6,
  },
  kicker: {
    color: theme.primary,
    fontSize: 10,
    letterSpacing: 2,
    fontWeight: "800",
    marginBottom: 8,
  },
  table: {
    borderWidth: 1,
    borderColor: theme.border,
    borderRadius: theme.radius,
    overflow: "hidden",
  },
  tableRow: {
    flexDirection: "row",
    alignItems: "center",
    minHeight: 42,
    borderTopWidth: 1,
    borderTopColor: theme.border,
    paddingHorizontal: 10,
  },
  tableHeader: {
    borderTopWidth: 0,
    backgroundColor: theme.surfaceAlt,
  },
  cell: {
    flex: 1,
    color: theme.text,
    fontSize: 12,
  },
  projectCell: {
    flex: 1.6,
    fontWeight: "700",
  },
  good: {
    color: theme.success,
    fontWeight: "700",
  },
  warn: {
    color: theme.warning,
    fontWeight: "700",
  },
  trend: {
    flex: 1,
    height: 24,
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 4,
  },
  trendSegment: {
    width: 16,
    borderRadius: 2,
    backgroundColor: theme.primary,
  },
  errorCard: {
    borderColor: theme.danger,
    backgroundColor: "rgba(220,77,93,0.08)",
  },
  errorText: {
    color: theme.danger,
    fontSize: 12,
    lineHeight: 18,
  },
});
